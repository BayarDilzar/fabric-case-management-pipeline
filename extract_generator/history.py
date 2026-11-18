from datetime import timedelta

from extract_generator.ids import IdAllocator
from extract_generator.reference import (
    CUTOFFS,
    REFERRAL_SOURCE_SHARES,
    SERVICE_DISTRICT,
    SERVICE_SHARES,
    SEX_SHARES,
    START_DATE,
    SUBSTANCE_SHARES,
    TREATED_DISCHARGE_SHARES,
)
from extract_generator.state import State, weighted

CUTOFF = CUTOFFS[0]
EPISODE_COUNTS = [1] * 1500 + [2] * 400 + [3] * 100
# A client's next referral comes at least this long after the previous one,
# so every earlier episode has room to close first.
MIN_GAP_DAYS = 120


def draw_age(rng):
    roll = rng.random()
    if roll < 0.8:
        return rng.randint(25, 55)
    if roll < 0.9:
        return rng.randint(18, 24)
    # 76 at most, so a client referred again three years later is still 79.
    return rng.randint(56, 76)


def home_district(rng, service):
    roll = rng.random()
    own = SERVICE_DISTRICT[service]
    if roll < 0.92:
        return own
    if roll < 0.98:
        return rng.choice(sorted(d for d in SERVICE_DISTRICT.values() if d != own))
    return ""


def referral_dates(rng, count):
    span = (CUTOFF - START_DATE).days - MIN_GAP_DAYS * (count - 1)
    offsets = sorted(rng.randint(0, span) for _ in range(count))
    return [START_DATE + timedelta(days=offset + MIN_GAP_DAYS * i) for i, offset in enumerate(offsets)]


def new_episode(rng, service, referral, must_close_by):
    """Build one episode. must_close_by is set when the client has a later episode."""
    episode = {
        "service_code": service,
        "referral_date": referral,
        "referral_source": weighted(rng, REFERRAL_SOURCE_SHARES),
        "primary_substance": weighted(rng, SUBSTANCE_SHARES),
        "triage_date": None,
        "discharge_date": None,
        "discharge_reason": None,
        "last_modified_at": None,
        "_start": None,
    }
    limit = must_close_by or CUTOFF
    triage = referral + timedelta(days=rng.randint(0, 28))
    if triage > CUTOFF:
        return episode
    episode["triage_date"] = triage
    if rng.random() < 0.05:
        discharge = triage + timedelta(days=rng.randint(0, 14))
        if discharge <= limit:
            episode["discharge_date"] = discharge
            episode["discharge_reason"] = "DECLINED"
        return episode
    start = triage + timedelta(days=rng.randint(0, 42))
    if start > CUTOFF:
        return episode
    episode["_start"] = start
    days = rng.randint(90, 1000) if episode["primary_substance"] == "OPIATE" else rng.randint(30, 300)
    end = start + timedelta(days=days)
    if must_close_by:
        end = min(end, must_close_by)
    if end <= CUTOFF:
        shares = TREATED_DISCHARGE_SHARES
        if must_close_by:
            shares = [share for share in shares if share[0] != "DIED"]
        episode["discharge_date"] = end
        episode["discharge_reason"] = weighted(rng, shares)
    return episode


INTERVENTION_TYPES = ["PHARMA", "PSYCHO", "RECOVERY"]


def new_interventions(rng, episode):
    start = episode["_start"]
    if start is None:
        return []
    count = weighted(rng, [(1, 50), (2, 35), (3, 15)])
    opiate = episode["primary_substance"] == "OPIATE"
    first = "PHARMA" if opiate and rng.random() < 0.8 else "PSYCHO"
    others = [kind for kind in INTERVENTION_TYPES if kind != first]
    rng.shuffle(others)
    closed = episode["discharge_date"]
    last_day = closed or CUTOFF
    rows = []
    for i, kind in enumerate([first] + others[: count - 1]):
        begin = start if i == 0 else start + timedelta(days=rng.randint(0, (last_day - start).days // 2))
        if closed:
            # The first treatment runs to discharge; nothing may outlive the episode.
            end = closed if i == 0 else begin + timedelta(days=rng.randint(0, (closed - begin).days))
        elif i == 0 or rng.random() < 0.5:
            end = None
        else:
            end = begin + timedelta(days=rng.randint(0, (CUTOFF - begin).days))
        rows.append(
            {"intervention_type": kind, "start_date": begin, "end_date": end, "last_modified_at": None, "_episode": episode}
        )
    return rows


REVIEW_INTERVAL = timedelta(days=182)


def review_row(rng, kind, day, days_used, quality):
    return {
        "review_date": day,
        "review_type": kind,
        "days_used_last_28": None if rng.random() < 0.08 else days_used,
        "quality_of_life": None if rng.random() < 0.08 else quality,
        "last_modified_at": None,
    }


def later_scores(rng, days_used, quality):
    # Use tends to fall and quality of life to rise as treatment goes on.
    return max(0, days_used - rng.randint(0, 8)), min(20, quality + rng.randint(0, 4))


def new_reviews(rng, episode):
    start = episode["_start"]
    if start is None:
        return []
    closed = episode["discharge_date"]
    first = start + timedelta(days=rng.randint(0, 14))
    if first > (closed or CUTOFF):
        return []
    days_used, quality = rng.randint(10, 28), rng.randint(4, 12)
    rows = [review_row(rng, "START", first, days_used, quality)]
    day = first + REVIEW_INTERVAL
    while day <= CUTOFF and (closed is None or day < closed):
        days_used, quality = later_scores(rng, days_used, quality)
        rows.append(review_row(rng, "REVIEW", day, days_used, quality))
        day += REVIEW_INTERVAL
    if closed and episode["discharge_reason"] in ("COMPLETED", "TRANSFERRED"):
        days_used, quality = later_scores(rng, days_used, quality)
        rows.append(review_row(rng, "EXIT", closed, days_used, quality))
    return rows


def build_history(rng):
    counts = list(EPISODE_COUNTS)
    rng.shuffle(counts)
    clients, episodes, interventions, reviews = [], [], [], []
    for count in counts:
        service = weighted(rng, SERVICE_SHARES)
        dates = referral_dates(rng, count)
        client = {
            "birth_year": dates[0].year - draw_age(rng),
            "sex": weighted(rng, SEX_SHARES),
            "local_authority_code": home_district(rng, service),
            "last_modified_at": None,
            "_first_referral": dates[0],
            "_service": service,
        }
        clients.append(client)
        for i, referral in enumerate(dates):
            must_close_by = dates[i + 1] - timedelta(days=1) if i + 1 < count else None
            episode = new_episode(rng, service, referral, must_close_by)
            episode["_client"] = client
            episodes.append(episode)
            interventions.extend(new_interventions(rng, episode))
            for review in new_reviews(rng, episode):
                review["_episode"] = episode
                reviews.append(review)

    state = State()
    # Ids follow creation order: clients by first referral, episodes by referral.
    clients.sort(key=lambda row: row["_first_referral"])
    episodes.sort(key=lambda row: row["referral_date"])
    interventions.sort(key=lambda row: row["start_date"])
    reviews.sort(key=lambda row: row["review_date"])
    state.allocators["clients"] = IdAllocator("C", rng, len(clients))
    state.allocators["episodes"] = IdAllocator("E", rng, len(episodes))
    state.allocators["interventions"] = IdAllocator("I", rng, len(interventions))
    state.allocators["reviews"] = IdAllocator("R", rng, len(reviews))
    for client, client_id in zip(clients, state.allocators["clients"].history_ids()):
        client["client_id"] = client_id
        state.client_service[client_id] = client.pop("_service")
        client.pop("_first_referral")
        state.clients[client_id] = client
    for episode, episode_id in zip(episodes, state.allocators["episodes"].history_ids()):
        episode["episode_id"] = episode_id
        episode["client_id"] = episode.pop("_client")["client_id"]
        episode.pop("_start")
        state.episodes[episode_id] = episode
    for intervention, intervention_id in zip(interventions, state.allocators["interventions"].history_ids()):
        intervention["intervention_id"] = intervention_id
        intervention["episode_id"] = intervention.pop("_episode")["episode_id"]
        state.interventions[intervention_id] = intervention
    for review, review_id in zip(reviews, state.allocators["reviews"].history_ids()):
        review["review_id"] = review_id
        review["episode_id"] = review.pop("_episode")["episode_id"]
        state.reviews[review_id] = review
    return state
