from collections import Counter
from datetime import date
from random import Random

import pytest

from extract_generator.history import build_history
from extract_generator.state import snapshot
from tests.support import SPEC_SERVICES, check_rules

HISTORY_CUTOFF = date(2026, 10, 25)


@pytest.fixture(scope="module")
def history():
    return snapshot(build_history(Random(2026 * 1000)))


def share(rows, predicate):
    return sum(1 for row in rows if predicate(row)) / len(rows)


def test_history_has_2000_clients_split_1500_400_100_by_episode_count(history):
    per_client = Counter(row["client_id"] for row in history["episodes"].values())

    assert len(history["clients"]) == 2000
    assert len(history["episodes"]) == 2600
    assert sorted(Counter(per_client.values()).items()) == [(1, 1500), (2, 400), (3, 100)]


def test_history_obeys_every_rule(history):
    assert check_rules(history, HISTORY_CUTOFF) == []


def test_history_sex_shares_are_close_to_the_spec(history):
    clients = list(history["clients"].values())

    assert abs(share(clients, lambda c: c["sex"] == "M") - 0.64) < 0.03
    assert abs(share(clients, lambda c: c["sex"] == "F") - 0.34) < 0.03
    assert abs(share(clients, lambda c: c["sex"] == "U") - 0.02) < 0.01


def test_history_clients_mostly_live_in_their_service_district(history):
    service_of = {row["client_id"]: row["service_code"] for row in history["episodes"].values()}
    clients = list(history["clients"].values())

    home = share(clients, lambda c: c["local_authority_code"] == SPEC_SERVICES[service_of[c["client_id"]]])
    unknown = share(clients, lambda c: c["local_authority_code"] == "")

    assert abs(home - 0.92) < 0.03
    assert abs(unknown - 0.02) < 0.01
    assert {c["local_authority_code"] for c in clients} <= set(SPEC_SERVICES.values()) | {""}


def test_history_has_open_untriaged_declined_and_died_episodes(history):
    episodes = list(history["episodes"].values())
    reasons = Counter(row["discharge_reason"] for row in episodes)

    assert any(not row["triage_date"] for row in episodes)
    # The spec's treatment lengths leave about a fifth open, not the third its summary estimates.
    assert 0.15 < reasons[""] / len(episodes) < 0.45
    assert reasons["DECLINED"] > 0
    assert reasons["DIED"] > 0


def test_history_treated_episodes_have_one_to_three_interventions_in_spec_shares(history):
    per_episode = Counter(row["episode_id"] for row in history["interventions"].values())
    shares = Counter(per_episode.values())
    treated = sum(shares.values())

    assert set(shares) == {1, 2, 3}
    assert abs(shares[1] / treated - 0.50) < 0.04
    assert abs(shares[2] / treated - 0.35) < 0.04
    assert abs(shares[3] / treated - 0.15) < 0.04


def test_history_reviews_have_some_missing_scores_and_use_falls_by_exit(history):
    reviews = list(history["reviews"].values())

    def mean_days(kind):
        values = [int(r["days_used_last_28"]) for r in reviews if r["review_type"] == kind and r["days_used_last_28"]]
        return sum(values) / len(values)

    assert 5000 < len(reviews) < 7000
    assert abs(share(reviews, lambda r: r["days_used_last_28"] == "") - 0.08) < 0.02
    assert abs(share(reviews, lambda r: r["quality_of_life"] == "") - 0.08) < 0.02
    assert mean_days("EXIT") < mean_days("START")
