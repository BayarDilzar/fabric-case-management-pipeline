"""Test helpers. Expected values come from the spec, not from the generator."""

from collections import defaultdict
from datetime import date

SPEC_SERVICES = {
    "S01": "E06000009",
    "S02": "E06000002",
    "S03": "E06000043",
    "S04": "E08000035",
    "S05": "E09000023",
    "S06": "E06000052",
}


def as_date(value):
    return date.fromisoformat(value) if value else None


def episodes_by_client(view):
    grouped = defaultdict(list)
    for key in sorted(view["episodes"]):
        row = view["episodes"][key]
        grouped[row["client_id"]].append(row)
    for rows in grouped.values():
        rows.sort(key=lambda row: (row["referral_date"], row["episode_id"]))
    return grouped


def rule_r02_episode_parents(view, cutoff):
    for key in sorted(view["episodes"]):
        row = view["episodes"][key]
        if row["client_id"] not in view["clients"]:
            yield f"R02 {key}: client {row['client_id']} missing"
        if row["service_code"] not in SPEC_SERVICES:
            yield f"R02 {key}: service {row['service_code']} unknown"


def rule_r07_discharge_after_referral(view, cutoff):
    for key in sorted(view["episodes"]):
        row = view["episodes"][key]
        if row["discharge_date"] and as_date(row["discharge_date"]) < as_date(row["referral_date"]):
            yield f"R07 {key}: discharged before referral"


def rule_r11_triage_after_referral(view, cutoff):
    for key in sorted(view["episodes"]):
        row = view["episodes"][key]
        if row["triage_date"] and as_date(row["triage_date"]) < as_date(row["referral_date"]):
            yield f"R11 {key}: triaged before referral"


def rule_r13_discharge_date_and_reason_together(view, cutoff):
    for key in sorted(view["episodes"]):
        row = view["episodes"][key]
        if bool(row["discharge_date"]) != bool(row["discharge_reason"]):
            yield f"R13 {key}: discharge date and reason do not match"


def rule_r14_episodes_do_not_overlap(view, cutoff):
    for client_id, rows in sorted(episodes_by_client(view).items()):
        for earlier, later in zip(rows, rows[1:]):
            if not earlier["discharge_date"]:
                yield f"R14 {client_id}: {earlier['episode_id']} open when {later['episode_id']} starts"
            elif as_date(earlier["discharge_date"]) >= as_date(later["referral_date"]):
                yield f"R14 {client_id}: {earlier['episode_id']} overlaps {later['episode_id']}"


def rule_r15_age_at_referral(view, cutoff):
    for key in sorted(view["episodes"]):
        row = view["episodes"][key]
        client = view["clients"].get(row["client_id"])
        if client is None:
            continue
        age = as_date(row["referral_date"]).year - int(client["birth_year"])
        if not 18 <= age <= 80:
            yield f"R15 {key}: age {age} at referral"


def rule_died_is_final(view, cutoff):
    # Not in the spec's table, but a client who died cannot come back.
    for client_id, rows in sorted(episodes_by_client(view).items()):
        for row in rows[:-1]:
            if row["discharge_reason"] == "DIED":
                yield f"DIED {client_id}: episode after {row['episode_id']}"


def children(view, table):
    grouped = defaultdict(list)
    for key in sorted(view[table]):
        grouped[view[table][key]["episode_id"]].append(view[table][key])
    return grouped


def rule_r03_intervention_parent(view, cutoff):
    for key in sorted(view["interventions"]):
        if view["interventions"][key]["episode_id"] not in view["episodes"]:
            yield f"R03 {key}: episode missing"


def rule_r08_end_after_start(view, cutoff):
    for key in sorted(view["interventions"]):
        row = view["interventions"][key]
        if row["end_date"] and as_date(row["end_date"]) < as_date(row["start_date"]):
            yield f"R08 {key}: ends before it starts"


def rule_r12_interventions_inside_episode(view, cutoff):
    for key in sorted(view["interventions"]):
        row = view["interventions"][key]
        episode = view["episodes"].get(row["episode_id"])
        if episode is None:
            continue
        last_day = as_date(episode["discharge_date"]) or cutoff
        if not as_date(episode["referral_date"]) <= as_date(row["start_date"]) <= last_day:
            yield f"R12 {key}: starts outside its episode"
        if episode["discharge_date"] and not row["end_date"]:
            yield f"R12 {key}: still open in a closed episode"
        if row["end_date"] and as_date(row["end_date"]) > last_day:
            yield f"R12 {key}: ends after its episode"


def rule_treatment_matches_discharge_reason(view, cutoff):
    # DECLINED means the client never started treatment; any other closure means they did.
    treated = children(view, "interventions")
    for key in sorted(view["episodes"]):
        row = view["episodes"][key]
        if row["discharge_reason"] == "DECLINED" and treated[key]:
            yield f"TREATMENT {key}: declined but has interventions"
        if row["discharge_reason"] not in ("", "DECLINED") and not treated[key]:
            yield f"TREATMENT {key}: closed as {row['discharge_reason']} with no intervention"
        if not row["triage_date"] and treated[key]:
            yield f"TREATMENT {key}: treated before triage"
        if len(treated[key]) > 3:
            yield f"TREATMENT {key}: more than three interventions"


RULES = [
    rule_r02_episode_parents,
    rule_r03_intervention_parent,
    rule_r08_end_after_start,
    rule_r12_interventions_inside_episode,
    rule_treatment_matches_discharge_reason,
    rule_r07_discharge_after_referral,
    rule_r11_triage_after_referral,
    rule_r13_discharge_date_and_reason_together,
    rule_r14_episodes_do_not_overlap,
    rule_r15_age_at_referral,
    rule_died_is_final,
]


def check_rules(view, cutoff):
    return [problem for rule in RULES for problem in rule(view, cutoff)]
