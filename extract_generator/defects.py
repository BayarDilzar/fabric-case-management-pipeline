from datetime import date, datetime, timedelta

from extract_generator.reference import KEYS
from extract_generator.state import TABLES

DEFECT_COLUMNS = [
    "defect_id",
    "extract_date",
    "file_name",
    "record_key",
    "field",
    "defect_type",
    "injected_value",
    "expected_outcome",
    "expected_value",
    "expected_reason",
]

# (defect type, table, field, count), applied in this order.
HISTORY_PLAN = [
    ("DUP_EXACT", "clients", "", 20),
    ("DUP_EXACT", "episodes", "", 15),
    ("DUP_EXACT", "interventions", "", 25),
    ("DUP_EXACT", "reviews", "", 30),
    ("DUP_VERSION", "episodes", "", 10),
    ("DUP_VERSION", "interventions", "", 10),
    ("MISSING_REQUIRED", "episodes", "referral_date", 8),
    ("MISSING_REQUIRED", "interventions", "start_date", 10),
    ("MISSING_REQUIRED", "reviews", "review_date", 12),
    ("DATE_FORMAT", "episodes", "referral_date", 15),
    ("DATE_FORMAT", "episodes", "discharge_date", 15),
    ("DATE_FORMAT", "interventions", "start_date", 15),
    ("DATE_FORMAT", "reviews", "review_date", 15),
    ("CODE_CASE", "clients", "sex", 10),
    ("CODE_CASE", "episodes", "referral_source", 15),
    ("CODE_CASE", "interventions", "intervention_type", 10),
    ("CODE_UNKNOWN", "episodes", "primary_substance", 8),
    ("CODE_UNKNOWN", "episodes", "service_code", 4),
    ("CODE_UNKNOWN", "interventions", "intervention_type", 6),
    ("ORPHAN", "episodes", "client_id", 6),
    ("ORPHAN", "interventions", "episode_id", 12),
    ("ORPHAN", "reviews", "episode_id", 15),
    ("RULE_DISCHARGE_BEFORE_REFERRAL", "episodes", "discharge_date", 6),
    ("RULE_END_BEFORE_START", "interventions", "end_date", 8),
    ("RULE_DAYS_RANGE", "reviews", "days_used_last_28", 7),
    ("RULE_FUTURE_DATE", "reviews", "review_date", 5),
]
# Believable mistakes: a drug name typed as a code, a near-miss code, a service that does not exist.
UNKNOWN_CODES = {"primary_substance": "HEROIN", "intervention_type": "PHARMACY", "service_code": "S07"}
# UK day-first order and the NDTMS compact format. Never month-first, which cannot be told apart.
OTHER_DATE_FORMATS = ["%d/%m/%Y", "%Y%m%d"]
WEEK_TARGETS = {
    "MISSING_REQUIRED": [("episodes", "referral_date"), ("interventions", "start_date"), ("reviews", "review_date")],
    "DATE_FORMAT": [
        ("episodes", "referral_date"),
        ("episodes", "discharge_date"),
        ("interventions", "start_date"),
        ("reviews", "review_date"),
    ],
    "CODE_CASE": [("clients", "sex"), ("episodes", "referral_source"), ("interventions", "intervention_type")],
    "CODE_UNKNOWN": [("episodes", "primary_substance"), ("episodes", "service_code"), ("interventions", "intervention_type")],
    "ORPHAN": [("episodes", "client_id"), ("interventions", "episode_id"), ("reviews", "episode_id")],
}
WEEK_RULES = [
    ("RULE_DISCHARGE_BEFORE_REFERRAL", "episodes", "discharge_date"),
    ("RULE_END_BEFORE_START", "interventions", "end_date"),
    ("RULE_DAYS_RANGE", "reviews", "days_used_last_28"),
]


def week_plan(number):
    """About 14 defects a week. Targets rotate by week so three weeks cover every field."""
    turn = number - 1

    def one(defect_type):
        targets = WEEK_TARGETS[defect_type]
        return [(defect_type, *targets[turn % len(targets)], 1)]

    def all_but_one(defect_type):
        targets = WEEK_TARGETS[defect_type]
        skipped = targets[turn % len(targets)]
        return [(defect_type, table, field, 1) for table, field in targets if (table, field) != skipped]

    return (
        [("DUP_EXACT", table, "", 1) for table in ("episodes", "interventions", "reviews")]
        + [("DUP_VERSION", "episodes", "", 1)]
        + one("MISSING_REQUIRED")
        + all_but_one("DATE_FORMAT")
        + all_but_one("CODE_CASE")
        + one("CODE_UNKNOWN")
        + all_but_one("ORPHAN")
        + [(*WEEK_RULES[turn], 1)]
        # The source's overlap window sends some rows again; a merge must leave them alone.
        + ([("RESENT_UNCHANGED", "reviews", "", 5)] if number == 2 else [])
    )


# The broken extract carries no row defects: its load must fail before any row is read.
BROKEN_PLAN = [("SCHEMA_MISSING_COLUMN", "interventions", "end_date", 1)]

# The fields an older version did not have yet.
LATER_FIELDS = {"episodes": ["discharge_date", "discharge_reason"], "interventions": ["end_date"]}
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


class Injector:
    """Adds defects to one extract's rendered rows and records each one for the manifest."""

    def __init__(self, extract, rng, state, new_keys, weekly):
        self.extract = extract
        self.files = extract.files
        self.snapshot = extract.snapshot
        self.new_keys = new_keys
        self.weekly = weekly
        self.state = state
        # Episodes that have interventions or reviews in the source system, loaded or not.
        self.parents = {row["episode_id"] for name in ("interventions", "reviews") for row in state.table(name).values()}
        self.cutoff = extract.cutoff
        self.rng = rng
        self.rows = {table: {row[KEYS[table]]: row for row in self.files[f"{table}.csv"]} for table in TABLES}
        self.used = {table: set() for table in TABLES}
        self.lines = []
        self.inserts = []

    def run(self, plan):
        for defect_type, table, field, count in plan:
            if defect_type == "RESENT_UNCHANGED":
                self.resend(table, count)
                continue
            if defect_type == "SCHEMA_MISSING_COLUMN":
                self.drop_column(table, field)
                continue
            pool = [
                key
                for key in sorted(self.rows[table])
                if key not in self.used[table] and self.eligible(defect_type, table, self.rows[table][key], field)
            ]
            for key in self.rng.sample(pool, min(count, len(pool))):
                # One defect per row, so a test can tell which check should catch it.
                self.used[table].add(key)
                getattr(self, defect_type.lower())(table, field, key)
        self.place_inserts()
        return self.lines

    def rejectable(self, table, key):
        # A rejected row must have no children, so one defect means one quarantined row and nothing cascades.
        is_leaf = table != "episodes" or key not in self.parents
        return key in self.new_keys[table] and is_leaf

    def eligible(self, defect_type, table, row, field):
        key = row[KEYS[table]]
        if defect_type == "DATE_FORMAT":
            return bool(row[field])
        if defect_type in ("MISSING_REQUIRED", "CODE_UNKNOWN", "ORPHAN", "RULE_DAYS_RANGE", "RULE_FUTURE_DATE"):
            return self.rejectable(table, key)
        if defect_type == "RULE_DISCHARGE_BEFORE_REFERRAL":
            # Only an episode that never started treatment can be closed and have no children.
            return row["discharge_reason"] == "DECLINED" and key not in self.parents
        if defect_type == "RULE_END_BEFORE_START":
            # Room between referral and start keeps the bad end date inside the episode, so only R08 breaks.
            # In a week the episode must still be open: Silver keeps the open version of the intervention.
            still_open = not self.weekly or self.state.episodes[row["episode_id"]]["discharge_date"] is None
            return bool(row["end_date"]) and self.days_after_referral(row) >= 1 and still_open
        if defect_type == "DUP_VERSION":
            if table == "episodes":
                # The older version is stamped an hour earlier, so it must still fall after its last date.
                earlier = max(value for value in (row["referral_date"], row["triage_date"]) if value)
                return bool(row["discharge_date"]) and row["discharge_date"] > earlier
            return bool(row["end_date"]) and row["end_date"] > row["start_date"]
        return True

    def days_after_referral(self, intervention):
        episode = self.state.episodes[intervention["episode_id"]]
        return (date.fromisoformat(intervention["start_date"]) - episode["referral_date"]).days

    def record(self, table, key, field, defect_type, injected, outcome, expected="", reason=""):
        number = len(self.lines) + 1
        self.lines.append(
            {
                "defect_id": f"D-{self.cutoff:%Y%m%d}-{number:04d}",
                "extract_date": self.cutoff.isoformat(),
                "file_name": f"{table}.csv",
                "record_key": key,
                "field": field,
                "defect_type": defect_type,
                "injected_value": injected,
                "expected_outcome": outcome,
                "expected_value": expected,
                "expected_reason": reason,
            }
        )

    def dup_exact(self, table, field, key):
        self.inserts.append((table, dict(self.rows[table][key]), None))
        self.record(table, key, "", "DUP_EXACT", "", "REMOVED")

    def dup_version(self, table, field, key):
        newer = self.rows[table][key]
        older = dict(newer)
        for column in LATER_FIELDS[table]:
            older[column] = ""
        stamp = datetime.strptime(newer["last_modified_at"], TIMESTAMP_FORMAT) - timedelta(hours=1)
        older["last_modified_at"] = stamp.strftime(TIMESTAMP_FORMAT)
        self.inserts.append((table, older, newer))
        self.record(table, key, "", "DUP_VERSION", older["last_modified_at"], "REMOVED")

    def missing_required(self, table, field, key):
        self.rows[table][key][field] = ""
        self.record(table, key, field, "MISSING_REQUIRED", "", "QUARANTINED", reason="MISSING_REQUIRED")

    def date_format(self, table, field, key):
        row = self.rows[table][key]
        clean = row[field]
        row[field] = date.fromisoformat(clean).strftime(self.rng.choice(OTHER_DATE_FORMATS))
        self.record(table, key, field, "DATE_FORMAT", row[field], "CORRECTED", expected=clean)

    def code_case(self, table, field, key):
        row = self.rows[table][key]
        code = row[field]
        row[field] = self.rng.choice([code.lower(), " " + code, code + " "])
        self.record(table, key, field, "CODE_CASE", row[field], "CORRECTED", expected=code)

    def code_unknown(self, table, field, key):
        self.rows[table][key][field] = UNKNOWN_CODES[field]
        self.record(table, key, field, "CODE_UNKNOWN", UNKNOWN_CODES[field], "QUARANTINED", reason="INVALID_CODE")

    def orphan(self, table, field, key):
        parent = "clients" if field == "client_id" else "episodes"
        # A held-back id looks normal but is never issued, so the parent can never turn up later.
        missing = self.rng.choice(self.state.allocators[parent].held_back)
        self.rows[table][key][field] = missing
        self.record(table, key, field, "ORPHAN", missing, "QUARANTINED", reason="ORPHAN")

    def shift(self, table, key, field, base, days, defect_type, reason):
        row = self.rows[table][key]
        row[field] = (date.fromisoformat(base) + timedelta(days=days)).isoformat()
        self.record(table, key, field, defect_type, row[field], "QUARANTINED", reason=reason)

    def rule_discharge_before_referral(self, table, field, key):
        referral = self.rows[table][key]["referral_date"]
        self.shift(table, key, field, referral, -self.rng.randint(1, 60), "RULE_DISCHARGE_BEFORE_REFERRAL", "RULE_R07")

    def rule_end_before_start(self, table, field, key):
        row = self.rows[table][key]
        days = self.rng.randint(1, min(30, self.days_after_referral(row)))
        self.shift(table, key, field, row["start_date"], -days, "RULE_END_BEFORE_START", "RULE_R08")

    def rule_days_range(self, table, field, key):
        value = str(self.rng.randint(29, 40))
        self.rows[table][key][field] = value
        self.record(table, key, field, "RULE_DAYS_RANGE", value, "QUARANTINED", reason="RULE_R09")

    def rule_future_date(self, table, field, key):
        cutoff = self.cutoff.isoformat()
        self.shift(table, key, field, cutoff, self.rng.randint(1, 90), "RULE_FUTURE_DATE", "RULE_R10")

    def resend(self, table, count):
        # Untouched rows outside frozen episodes are exactly what Silver already holds.
        pool = [
            key
            for key in sorted(self.snapshot[table])
            if key not in self.rows[table] and self.snapshot[table][key]["episode_id"] not in self.state.frozen_episodes
        ]
        for key in self.rng.sample(pool, min(count, len(pool))):
            self.inserts.append((table, dict(self.snapshot[table][key]), None))
            self.record(table, key, "", "RESENT_UNCHANGED", "", "UNCHANGED")

    def drop_column(self, table, field):
        name = f"{table}.csv"
        # A new dict: the column lists are shared with the other extracts.
        self.extract.columns = {**self.extract.columns, name: [c for c in self.extract.columns[name] if c != field]}
        for row in self.files[name]:
            del row[field]
        self.record(table, "", field, "SCHEMA_MISSING_COLUMN", "", "LOAD_FAILED")

    def place_inserts(self):
        for table, row, anchor in self.inserts:
            rows = self.files[f"{table}.csv"]
            if anchor is None:
                rows.insert(self.rng.randint(0, len(rows)), row)
                continue
            # Before or after at random, so file order cannot tell old from new.
            position = next(i for i, candidate in enumerate(rows) if candidate is anchor)
            rows.insert(position if self.rng.random() < 0.5 else position + 1, row)


def inject(extract, rng, plan, state, new_keys, weekly=False):
    return Injector(extract, rng, state, new_keys, weekly).run(plan)
