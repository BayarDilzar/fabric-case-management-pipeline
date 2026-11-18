from collections import defaultdict
from datetime import timedelta

from extract_generator.history import (
    INTERVENTION_TYPES,
    REVIEW_INTERVAL,
    draw_age,
    first_scores,
    home_district,
    later_scores,
    review_row,
)
from extract_generator.reference import (
    REFERRAL_SOURCE_SHARES,
    SERVICE_DISTRICT,
    SERVICE_SHARES,
    SEX_SHARES,
    SUBSTANCE_SHARES,
    TREATED_DISCHARGE_SHARES,
)
from extract_generator.state import TABLES, stamp, weighted

NEW_CLIENTS = 30
RETURNING_CLIENTS = 10
TRIAGED = 20
DISCHARGED = 25
DECLINED = 3
ENDED = 40
NEW_INTERVENTIONS = 60
CLIENT_CORRECTIONS = 5
REVIEW_CORRECTIONS = 3


class Week:
    """One week of activity in the source system, between two cut-offs."""

    def __init__(self, state, rng, previous_cutoff, cutoff):
        self.state = state
        self.rng = rng
        self.cutoff = cutoff
        self.days = [previous_cutoff + timedelta(days=n) for n in range(1, (cutoff - previous_cutoff).days + 1)]
        self.touched = {table: set() for table in TABLES}
        self.new = {table: set() for table in TABLES}
        # Children by episode, built once: scanning every row per lookup made a week take seconds.
        self.kids = {"interventions": defaultdict(list), "reviews": defaultdict(list)}
        for table, kids in self.kids.items():
            for key in sorted(state.table(table)):
                kids[state.table(table)[key]["episode_id"]].append(key)

    def day(self):
        return self.rng.choice(self.days)

    def add(self, table, key, row):
        self.state.table(table)[key] = row
        self.touched[table].add(key)
        self.new[table].add(key)
        if table in self.kids:
            self.kids[table][row["episode_id"]].append(key)

    def change(self, table, key, day, **values):
        row = self.state.table(table)[key]
        row.update(values)
        row["last_modified_at"] = stamp(self.rng, day)
        self.touched[table].add(key)

    def children(self, table, episode_id):
        rows = [self.state.table(table)[key] for key in self.kids[table][episode_id]]
        return sorted(rows, key=lambda row: row["start_date" if table == "interventions" else "review_date"])

    def open_episodes(self):
        return [
            key
            for key in sorted(self.state.episodes)
            if not self.state.episodes[key]["discharge_date"]
            and key not in self.touched["episodes"]
            and key not in self.state.frozen_episodes
        ]

    def episodes_by_client(self):
        grouped = defaultdict(list)
        for key in sorted(self.state.episodes):
            episode = self.state.episodes[key]
            grouped[episode["client_id"]].append(episode)
        return grouped

    def refer(self, client_id, service):
        referral = self.day()
        episode_id = self.state.allocators["episodes"].new_id()
        episode = {
            "episode_id": episode_id,
            "client_id": client_id,
            "service_code": service,
            "referral_date": referral,
            "referral_source": weighted(self.rng, REFERRAL_SOURCE_SHARES),
            "primary_substance": weighted(self.rng, SUBSTANCE_SHARES),
            "triage_date": None,
            "discharge_date": None,
            "discharge_reason": None,
            "last_modified_at": stamp(self.rng, referral),
        }
        self.add("episodes", episode_id, episode)
        return episode

    def new_clients(self):
        for _ in range(NEW_CLIENTS):
            service = weighted(self.rng, SERVICE_SHARES)
            client_id = self.state.allocators["clients"].new_id()
            self.state.client_service[client_id] = service
            episode = self.refer(client_id, service)
            client = {
                "client_id": client_id,
                "birth_year": episode["referral_date"].year - draw_age(self.rng),
                "sex": weighted(self.rng, SEX_SHARES),
                "local_authority_code": home_district(self.rng, service),
                "last_modified_at": episode["last_modified_at"],
            }
            self.add("clients", client_id, client)

    def can_return(self, client_id, episodes):
        last = episodes[-1]
        return (
            all(episode["discharge_date"] for episode in episodes)
            and last["discharge_date"] < self.days[0]
            and last["discharge_reason"] != "DIED"
            and self.cutoff.year - self.state.clients[client_id]["birth_year"] <= 80
        )

    def returning_clients(self):
        grouped = self.episodes_by_client()
        pool = [
            client_id
            for client_id in sorted(grouped)
            if client_id not in self.state.blocked_clients and self.can_return(client_id, grouped[client_id])
        ]
        for client_id in self.rng.sample(pool, min(RETURNING_CLIENTS, len(pool))):
            self.refer(client_id, self.state.client_service[client_id])

    def triage(self):
        pool = [key for key in self.open_episodes() if not self.state.episodes[key]["triage_date"]]
        for key in self.rng.sample(pool, min(TRIAGED, len(pool))):
            day = self.day()
            self.change("episodes", key, day, triage_date=day)

    def new_review(self, episode_id, kind, day):
        reviews = self.children("reviews", episode_id)
        scores = first_scores(self.rng)
        if reviews:
            # An unanswered score carries nothing forward, so start that one afresh.
            last = reviews[-1]
            days_used = scores[0] if last["days_used_last_28"] is None else last["days_used_last_28"]
            quality = scores[1] if last["quality_of_life"] is None else last["quality_of_life"]
            scores = later_scores(self.rng, days_used, quality)
        review = review_row(self.rng, kind, day, *scores)
        review_id = self.state.allocators["reviews"].new_id()
        review.update(review_id=review_id, episode_id=episode_id, last_modified_at=stamp(self.rng, day))
        self.add("reviews", review_id, review)

    def exit_review(self, episode_id, day):
        # An EXIT with no START before it would break the review pattern.
        if self.children("reviews", episode_id):
            self.new_review(episode_id, "EXIT", day)

    def discharge(self):
        open_keys = self.open_episodes()
        untreated = [key for key in open_keys if self.state.episodes[key]["triage_date"] and not self.kids["interventions"][key]]
        declined = self.rng.sample(untreated, min(DECLINED, len(untreated)))
        # Wait for the START review before closing treatment, so every closed treatment has one.
        in_treatment = [key for key in open_keys if self.kids["interventions"][key] and self.kids["reviews"][key]]
        for key in declined:
            day = self.day()
            self.change("episodes", key, day, discharge_date=day, discharge_reason="DECLINED")
        for key in self.rng.sample(in_treatment, min(DISCHARGED - len(declined), len(in_treatment))):
            day = self.day()
            reason = weighted(self.rng, TREATED_DISCHARGE_SHARES)
            self.change("episodes", key, day, discharge_date=day, discharge_reason=reason)
            # Nothing may outlive the episode, so running treatment ends on the discharge day.
            for intervention in self.children("interventions", key):
                if intervention["end_date"] is None:
                    self.change("interventions", intervention["intervention_id"], day, end_date=day)
            if reason in ("COMPLETED", "TRANSFERRED"):
                self.exit_review(key, day)

    def end_interventions(self):
        pool = [
            key
            for episode_id in self.open_episodes()
            for key in self.kids["interventions"][episode_id]
            if self.state.interventions[key]["end_date"] is None and key not in self.touched["interventions"]
        ]
        wanted = ENDED - len(self.touched["interventions"])
        for key in self.rng.sample(pool, max(0, min(wanted, len(pool)))):
            day = self.day()
            self.change("interventions", key, day, end_date=day)

    def new_interventions(self):
        pool = [
            key
            for key in self.open_episodes()
            if self.state.episodes[key]["triage_date"] and len(self.children("interventions", key)) < 3
        ]
        for key in self.rng.sample(pool, min(NEW_INTERVENTIONS, len(pool))):
            episode = self.state.episodes[key]
            existing = self.children("interventions", key)
            used = {row["intervention_type"] for row in existing}
            if existing:
                kind = self.rng.choice([kind for kind in INTERVENTION_TYPES if kind not in used])
            elif episode["primary_substance"] == "OPIATE" and self.rng.random() < 0.8:
                kind = "PHARMA"
            else:
                kind = "PSYCHO"
            start = self.day()
            intervention_id = self.state.allocators["interventions"].new_id()
            intervention = {
                "intervention_id": intervention_id,
                "episode_id": key,
                "intervention_type": kind,
                "start_date": start,
                "end_date": None,
                "last_modified_at": stamp(self.rng, start),
            }
            self.add("interventions", intervention_id, intervention)
            if not existing:
                self.new_review(key, "START", self.rng.choice([day for day in self.days if day >= start]))

    def new_reviews(self):
        # Six-monthly reviews fall due 182 days after the last one, so most weeks bring far fewer than 100.
        reviewed = {self.state.reviews[key]["episode_id"] for key in self.new["reviews"]}
        for key in self.open_episodes():
            reviews = self.children("reviews", key)
            if key in reviewed:
                continue
            if not reviews:
                # Treatment that began just before a cut-off may still be waiting for its START.
                if self.kids["interventions"][key]:
                    self.new_review(key, "START", self.day())
                continue
            due = reviews[-1]["review_date"] + REVIEW_INTERVAL
            if due in self.days:
                self.new_review(key, "REVIEW", due)

    def correct_clients(self):
        grouped = self.episodes_by_client()
        pool = [
            key
            for key in sorted(self.state.clients)
            if key not in self.touched["clients"] and grouped[key][-1]["discharge_reason"] != "DIED"
        ]
        for key in self.rng.sample(pool, min(CLIENT_CORRECTIONS, len(pool))):
            client = self.state.clients[key]
            home = SERVICE_DISTRICT[self.state.client_service[key]]
            if client["sex"] == "U":
                values = {"sex": self.rng.choice(["F", "M"])}
            elif not client["local_authority_code"]:
                values = {"local_authority_code": home}
            else:
                # A move to another district the provider serves.
                others = sorted(d for d in SERVICE_DISTRICT.values() if d != client["local_authority_code"])
                values = {"local_authority_code": self.rng.choice(others)}
            self.change("clients", key, self.day(), **values)

    def correct_reviews(self):
        pool = [
            key
            for key in sorted(self.state.reviews)
            if key not in self.touched["reviews"] and self.state.reviews[key]["episode_id"] not in self.state.frozen_episodes
        ]
        for key in self.rng.sample(pool, min(REVIEW_CORRECTIONS, len(pool))):
            current = self.state.reviews[key]["days_used_last_28"]
            value = self.rng.choice([n for n in range(29) if n != current])
            self.change("reviews", key, self.day(), days_used_last_28=value)


def run_week(state, rng, previous_cutoff, cutoff):
    week = Week(state, rng, previous_cutoff, cutoff)
    week.new_clients()
    week.returning_clients()
    week.triage()
    week.discharge()
    week.end_interventions()
    week.new_interventions()
    week.new_reviews()
    week.correct_clients()
    week.correct_reviews()
    return week.touched, week.new
