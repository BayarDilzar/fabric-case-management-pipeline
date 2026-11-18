from dataclasses import dataclass
from random import Random

from extract_generator.defects import HISTORY_PLAN, inject, week_plan
from extract_generator.history import build_history
from extract_generator.reference import COLUMNS, CUTOFFS
from extract_generator.state import TABLES, snapshot
from extract_generator.weekly import run_week

WEEKS = 3


@dataclass
class Extract:
    cutoff: object
    columns: dict
    files: dict
    defects: list
    # The source system after this extract, so tests can check the files rebuild it.
    snapshot: dict


def extract_rng(seed, number):
    # One generator per extract: code added for later extracts cannot shift earlier files.
    return Random(seed * 1000 + number)


def freeze(state, defects):
    for line in defects:
        if line["expected_outcome"] != "QUARANTINED":
            continue
        table = line["file_name"][: -len(".csv")]
        key = line["record_key"]
        episode_id = key if table == "episodes" else state.table(table)[key]["episode_id"]
        state.frozen_episodes.add(episode_id)
        state.blocked_clients.add(state.episodes[episode_id]["client_id"])


def build(seed):
    rng = extract_rng(seed, 0)
    state = build_history(rng)
    view = snapshot(state)
    files = {f"{table}.csv": [dict(row) for row in view[table].values()] for table in TABLES}
    columns = {f"{table}.csv": COLUMNS[table] for table in TABLES}
    history = Extract(CUTOFFS[0], columns, files, [], view)
    every_key = {table: set(state.table(table)) for table in TABLES}
    history.defects = inject(history, rng, HISTORY_PLAN, state, every_key)
    freeze(state, history.defects)
    extracts = [history]
    for number in range(1, WEEKS + 1):
        rng = extract_rng(seed, number)
        touched, new = run_week(state, rng, CUTOFFS[number - 1], CUTOFFS[number])
        view = snapshot(state)
        # A weekly extract carries only the rows created or changed in its week.
        files = {f"{table}.csv": [dict(view[table][key]) for key in sorted(touched[table])] for table in TABLES}
        week = Extract(CUTOFFS[number], columns, files, [], view)
        week.defects = inject(week, rng, week_plan(number), state, new, weekly=True)
        freeze(state, week.defects)
        extracts.append(week)
    return extracts
