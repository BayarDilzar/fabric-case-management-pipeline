from datetime import datetime, timedelta

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

# (defect type, table, field, count), applied in this order (spec section 6).
HISTORY_PLAN = [
    ("DUP_EXACT", "clients", "", 20),
    ("DUP_EXACT", "episodes", "", 15),
    ("DUP_EXACT", "interventions", "", 25),
    ("DUP_EXACT", "reviews", "", 30),
    ("DUP_VERSION", "episodes", "", 10),
    ("DUP_VERSION", "interventions", "", 10),
]
# The fields an older version did not have yet.
LATER_FIELDS = {"episodes": ["discharge_date", "discharge_reason"], "interventions": ["end_date"]}
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


class Injector:
    """Adds defects to one extract's rendered rows and records each one for the manifest."""

    def __init__(self, extract, rng):
        self.files = extract.files
        self.cutoff = extract.cutoff
        self.rng = rng
        self.rows = {table: {row[KEYS[table]]: row for row in self.files[f"{table}.csv"]} for table in TABLES}
        self.used = {table: set() for table in TABLES}
        self.lines = []
        self.inserts = []

    def run(self, plan):
        for defect_type, table, field, count in plan:
            pool = [
                key
                for key in sorted(self.rows[table])
                if key not in self.used[table] and self.eligible(defect_type, table, self.rows[table][key])
            ]
            for key in self.rng.sample(pool, min(count, len(pool))):
                # One defect per row, so a test can tell which check should catch it.
                self.used[table].add(key)
                getattr(self, defect_type.lower())(table, field, key)
        self.place_inserts()
        return self.lines

    def eligible(self, defect_type, table, row):
        if defect_type == "DUP_VERSION":
            if table == "episodes":
                # The older version is stamped an hour earlier, so it must still fall after its last date.
                earlier = max(value for value in (row["referral_date"], row["triage_date"]) if value)
                return bool(row["discharge_date"]) and row["discharge_date"] > earlier
            return bool(row["end_date"]) and row["end_date"] > row["start_date"]
        return True

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

    def place_inserts(self):
        for table, row, anchor in self.inserts:
            rows = self.files[f"{table}.csv"]
            if anchor is None:
                rows.insert(self.rng.randint(0, len(rows)), row)
                continue
            # Before or after at random, so file order cannot tell old from new.
            position = next(i for i, candidate in enumerate(rows) if candidate is anchor)
            rows.insert(position if self.rng.random() < 0.5 else position + 1, row)


def inject(extract, rng, plan):
    return Injector(extract, rng).run(plan)
