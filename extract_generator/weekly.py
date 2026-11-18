from collections import defaultdict
from datetime import timedelta

from extract_generator.history import draw_age, home_district, later_scores, review_row
from extract_generator.reference import (
    REFERRAL_SOURCE_SHARES,
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


class Week:
    """One week of activity in the source system, between two cut-offs."""

    def __init__(self, state, rng, previous_cutoff, cutoff):
        self.state = state
        self.rng = rng
        self.previous_cutoff = previous_cutoff
        self.cutoff = cutoff
        self.days = [previous_cutoff + timedelta(days=n) for n in range(1, (cutoff - previous_cutoff).days + 1)]
        self.touched = {table: set() for table in TABLES}
        self.new = {table: set() for table in TABLES}

    def day(self):
        return self.rng.choice(self.days)

    def add(self, table, key, row):
        self.state.table(table)[key] = row
        self.touched[table].add(key)
        self.new[table].add(key)

    def change(self, table, key, day, **values):
        row = self.state.table(table)[key]
        row.update(values)
        row["last_modified_at"] = stamp(self.rng, day)
        self.touched[table].add(key)

    def children(self, table, episode_id):
        rows = [row for _, row in sorted(self.state.table(table).items()) if row["episode_id"] == episode_id]
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

    def exit_review(self, episode_id, day):
        reviews = self.children("reviews", episode_id)
        if not reviews:
            # An EXIT with no START before it would break the review pattern.
            return
        last = reviews[-1]
        days_used = last["days_used_last_28"] if last["days_used_last_28"] is not None else self.rng.randint(10, 28)
        quality = last["quality_of_life"] if last["quality_of_life"] is not None else self.rng.randint(4, 12)
        review = review_row(self.rng, "EXIT", day, *later_scores(self.rng, days_used, quality))
        review_id = self.state.allocators["reviews"].new_id()
        review.update(review_id=review_id, episode_id=episode_id, last_modified_at=stamp(self.rng, day))
        self.add("reviews", review_id, review)

    def discharge(self):
        open_keys = self.open_episodes()
        treated = {row["episode_id"] for row in self.state.interventions.values()}
        untreated = [key for key in open_keys if self.state.episodes[key]["triage_date"] and key not in treated]
        declined = self.rng.sample(untreated, min(DECLINED, len(untreated)))
        in_treatment = [key for key in open_keys if key in treated]
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


def run_week(state, rng, previous_cutoff, cutoff):
    week = Week(state, rng, previous_cutoff, cutoff)
    week.new_clients()
    week.returning_clients()
    week.triage()
    week.discharge()
    return week.touched, week.new
