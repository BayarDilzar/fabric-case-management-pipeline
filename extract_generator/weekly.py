from collections import defaultdict
from datetime import timedelta

from extract_generator.history import draw_age, home_district
from extract_generator.reference import REFERRAL_SOURCE_SHARES, SERVICE_SHARES, SEX_SHARES, SUBSTANCE_SHARES
from extract_generator.state import TABLES, stamp, weighted

NEW_CLIENTS = 30
RETURNING_CLIENTS = 10


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
        pool = [client_id for client_id in sorted(grouped) if self.can_return(client_id, grouped[client_id])]
        for client_id in self.rng.sample(pool, min(RETURNING_CLIENTS, len(pool))):
            self.refer(client_id, self.state.client_service[client_id])


def run_week(state, rng, previous_cutoff, cutoff):
    week = Week(state, rng, previous_cutoff, cutoff)
    week.new_clients()
    week.returning_clients()
    return week.touched, week.new
