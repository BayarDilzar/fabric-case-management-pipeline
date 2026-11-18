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
]


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
            pool = [key for key in sorted(self.rows[table]) if key not in self.used[table]]
            for key in self.rng.sample(pool, min(count, len(pool))):
                # One defect per row, so a test can tell which check should catch it.
                self.used[table].add(key)
                getattr(self, defect_type.lower())(table, field, key)
        self.place_inserts()
        return self.lines

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
        self.inserts.append((table, dict(self.rows[table][key])))
        self.record(table, key, "", "DUP_EXACT", "", "REMOVED")

    def place_inserts(self):
        for table, row in self.inserts:
            rows = self.files[f"{table}.csv"]
            rows.insert(self.rng.randint(0, len(rows)), row)


def inject(extract, rng, plan):
    return Injector(extract, rng).run(plan)
