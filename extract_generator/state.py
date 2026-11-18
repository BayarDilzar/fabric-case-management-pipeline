from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta

from extract_generator.reference import COLUMNS

TABLES = ("clients", "episodes", "interventions", "reviews")


@dataclass
class State:
    """The source system as it stands after the last extract: typed rows keyed by id."""

    clients: dict = field(default_factory=dict)
    episodes: dict = field(default_factory=dict)
    interventions: dict = field(default_factory=dict)
    reviews: dict = field(default_factory=dict)
    client_service: dict = field(default_factory=dict)
    allocators: dict = field(default_factory=dict)
    # Episodes with a quarantined row: Silver holds an older version of that row or none, so no week may build on them.
    frozen_episodes: set = field(default_factory=set)
    blocked_clients: set = field(default_factory=set)

    def table(self, name):
        return getattr(self, name)


def weighted(rng, shares):
    codes = [code for code, _ in shares]
    weights = [weight for _, weight in shares]
    return rng.choices(codes, weights=weights)[0]


def stamp(rng, day):
    # Office hours keep every stamp well inside its day, so it never crosses a cut-off.
    return datetime.combine(day, time()) + timedelta(seconds=rng.randint(8 * 3600, 18 * 3600 - 1))


def format_value(value):
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def render(table, row):
    return {column: format_value(row[column]) for column in COLUMNS[table]}


def snapshot(state):
    return {table: {key: render(table, row) for key, row in sorted(state.table(table).items())} for table in TABLES}
