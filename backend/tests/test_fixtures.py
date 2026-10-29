import json

import pytest

from scripts.check_fixtures import ANSWERS, check, load_doc


@pytest.fixture(scope="module")
def cot():
    return load_doc("cot")


@pytest.mark.parametrize("path", sorted(p for p in (ANSWERS / "cot").glob("q*.json")), ids=lambda p: p.name)
def test_good_fixtures_are_fully_verified(cot, path):
    results = check(path, cot)
    assert all(r["status"] == "verified" and not r["drop"] for r in results), results


def test_hand_authored_fixtures_are_marked():
    meta = json.loads((ANSWERS / "cot" / "meta.json").read_text(encoding="utf-8"))
    assert all(v["source"] in {"hand-authored", "recorded"} for v in meta.values())
    for f in (ANSWERS / "cot").glob("q*.json"):
        assert f.name in meta
