"""Actual GenVM SDK storage/ABI, with controlled web/model inputs (no live LLM claims)."""
import hashlib
import json
from datetime import datetime, timezone

import pytest

PATH = "contracts/source_quorum.py"
SOURCES = [
    {"origin": f"https://{name}.example.org", "publisher": name, "ownership_note": f"Independently operated by {name}"}
    for name in ("official", "reporter", "research")
]


def ts(value):
    return int(datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp())


def warp(vm, value):
    vm.warp(value)


def state(c):
    return json.loads(c.get_claim("mainnet"))


@pytest.fixture
def setup(direct_vm, direct_deploy):
    direct_vm.check_pickling = True
    warp(direct_vm, "2026-11-09T12:00:00Z")
    c = direct_deploy(PATH, sdk_version="v0.2.16")
    c.create_claim("mainnet", "Did XYZ launch mainnet by Nov 10?", "Public production mainnet, excluding testnets.",
                   ts("2026-11-10T23:59:59Z"), ts("2026-11-11T00:00:00Z"), 2, 60)
    c.register_sources("mainnet", json.dumps(SOURCES))
    return c, direct_vm


def record(index, suffix="launch", body=None):
    body = body or f"Source {index} {suffix}. Published November 8 2026. XYZ production mainnet is live."
    original = SOURCES[index]["origin"] + "/" + suffix
    archive = "https://web.archive.org/web/20261109000000id_/" + original
    return ("mainnet", index, original, archive, hashlib.sha256(body.encode()).hexdigest()), body


def web(vm, args, body, status=200, capture="Mon, 09 Nov 2026 00:00:00 GMT"):
    import re
    vm.mock_web(re.escape(args[3]) + "$", {"method": "GET", "response": {"status": status, "body": body.encode(),
                  "headers": {"memento-datetime": capture.encode(), "content-type": b"text/plain; charset=utf-8"}}})


def model(vm, stances, related=None, dates=None):
    vm.mock_llm(r"SourceQuorum evidence classification", json.dumps({
        "rows": [{"index": i, "stance": s, "published_at": (dates or {}).get(i, "2026-11-08T23:59:59Z")}
                 for i, s in enumerate(stances) if s is not None], "related": related or []}))


def initial(c, vm, stances, related=None, dates=None):
    for i in range(len(stances)):
        args, body = record(i)
        c.submit_evidence(*args)
        web(vm, args, body)
    model(vm, stances, related, dates)
    warp(vm, "2026-11-11T00:00:00Z")
    c.verify_claim("mainnet")
    return state(c)


@pytest.mark.parametrize("labels,verdict", [
    (["SUPPORTS", "SUPPORTS", "UNKNOWN"], "VERIFIED"),
    (["REFUTES", "REFUTES", "UNKNOWN"], "REFUTED"),
    (["SUPPORTS", "REFUTES", "UNKNOWN"], "CONTESTED"),
    (["SUPPORTS", "UNKNOWN", "UNKNOWN"], "INSUFFICIENT"),
    (["UNKNOWN", "UNKNOWN", "UNKNOWN"], "INSUFFICIENT"),
])
def test_verdicts(setup, labels, verdict):
    c, vm = setup
    assert initial(c, vm, labels)["verdict"] == verdict
    assert vm.run_validator() is True


def test_no_evidence_is_not_false(setup):
    c, vm = setup
    warp(vm, "2026-11-11T00:00:00Z")
    c.verify_claim("mainnet")
    assert state(c)["verdict"] == "INSUFFICIENT"


def test_semantic_syndication_collapses_sources(setup):
    c, vm = setup
    s = initial(c, vm, ["SUPPORTS", "SUPPORTS", "UNKNOWN"], [[0, 1]])
    assert s["verdict"] == "INSUFFICIENT"
    assert s["history"][0]["result"]["supporting_groups"] == [0]


def test_independence_transitive(setup):
    c, vm = setup
    s = initial(c, vm, ["SUPPORTS"] * 3, [[0, 1], [1, 2]])
    assert s["verdict"] == "INSUFFICIENT"
    assert s["history"][0]["result"]["source_groups"] == [0, 0, 0]


def test_byte_identical_articles_cannot_vote_twice(setup):
    c, vm = setup
    for i in range(2):
        args, body = record(i, body="Same syndicated article")
        c.submit_evidence(*args)
        web(vm, args, body)
    model(vm, ["SUPPORTS", "SUPPORTS"])
    warp(vm, "2026-11-11T00:00:00Z")
    c.verify_claim("mainnet")
    assert state(c)["verdict"] == "INSUFFICIENT"


def test_publication_after_capture_excluded(setup):
    c, vm = setup
    s = initial(c, vm, ["SUPPORTS", "SUPPORTS"], dates={1: "2026-11-10T01:00:00Z"})
    assert s["verdict"] == "INSUFFICIENT"
    assert s["history"][0]["result"]["rows"][1]["reason"] == "OUTDATED_OR_LATE"


def test_undated_excluded(setup):
    c, vm = setup
    assert initial(c, vm, ["SUPPORTS", "SUPPORTS"], dates={1: ""})["verdict"] == "INSUFFICIENT"


@pytest.mark.parametrize("failure", ["hash", "http", "capture", "oversize", "mime"])
def test_unreliable_archive_is_insufficient(setup, failure):
    c, vm = setup
    for i in range(2):
        args, body = record(i)
        c.submit_evidence(*args)
        if failure == "mime":
            import re
            vm.mock_web(re.escape(args[3]), {"method": "GET", "response": {"status": 200, "body": body.encode(),
                        "headers": {"memento-datetime": b"Mon, 09 Nov 2026 00:00:00 GMT", "content-type": b"image/png"}}})
        else:
            web(vm, args, "tampered" if failure == "hash" else "x" * 80001 if failure == "oversize" else body,
                503 if failure == "http" else 200,
                "Tue, 10 Nov 2026 00:00:00 GMT" if failure == "capture" else "Mon, 09 Nov 2026 00:00:00 GMT")
    warp(vm, "2026-11-11T00:00:00Z")
    c.verify_claim("mainnet")
    assert state(c)["verdict"] == "INSUFFICIENT"
    assert vm.run_validator() is True


@pytest.mark.parametrize("answer", ["not json", '{"rows":[],"related":[]}',
                                      '{"rows":[{"index":0,"stance":"VERIFIED","published_at":""}],"related":[]}'])
def test_malformed_model_fails_closed(setup, answer):
    c, vm = setup
    args, body = record(0)
    c.submit_evidence(*args)
    web(vm, args, body)
    vm.mock_llm(r".*", answer)
    warp(vm, "2026-11-11T00:00:00Z")
    c.verify_claim("mainnet")
    assert state(c)["verdict"] == "INSUFFICIENT"
    assert state(c)["history"][0]["result"]["rows"][0]["reason"] == "ASSESSMENT_FAILED"


def test_validator_rejects_different_stance(setup):
    c, vm = setup
    initial(c, vm, ["SUPPORTS", "SUPPORTS"])
    vm.clear_mocks()
    for i in range(2):
        args, body = record(i)
        web(vm, args, body)
    model(vm, ["REFUTES", "REFUTES"])
    assert vm.run_validator() is False


def test_validator_rejects_different_independence(setup):
    c, vm = setup
    initial(c, vm, ["SUPPORTS", "SUPPORTS"])
    vm.clear_mocks()
    for i in range(2):
        args, body = record(i)
        web(vm, args, body)
    model(vm, ["SUPPORTS", "SUPPORTS"], [[0, 1]])
    assert vm.run_validator() is False


def test_challenge_and_exact_finalization_boundary(setup, direct_bob):
    c, vm = setup
    before = initial(c, vm, ["SUPPORTS", "SUPPORTS"])
    vm.clear_mocks()
    for i in range(2):
        args, body = record(i)
        web(vm, args, body)
    args, body = record(2, "correction")
    web(vm, args, body)
    model(vm, ["SUPPORTS", "SUPPORTS", "REFUTES"])
    with vm.prank(direct_bob):
        c.challenge_verdict(*args)
    s = state(c)
    assert s["verdict"] == "CONTESTED"
    assert len(s["history"]) == 2
    assert s["policy_hash"] == before["policy_hash"]
    assert s["sources_hash"] == before["sources_hash"]
    assert s["challenge_deadline"] == before["challenge_deadline"]
    with vm.expect_revert("Not ready for finalization"):
        c.finalize_claim("mainnet")
    warp(vm, "2026-11-11T00:01:00Z")
    with vm.expect_revert("Challenge window closed"):
        c.challenge_verdict(*args)
    with vm.prank(direct_bob):
        c.finalize_claim("mainnet")
    assert json.loads(c.get_verdict("mainnet"))["final"] is True
    with vm.expect_revert():
        c.verify_claim("mainnet")
    with vm.expect_revert():
        c.finalize_claim("mainnet")


def test_challenge_cannot_drop_prior_accepted_evidence(setup):
    c, vm = setup
    before = initial(c, vm, ["SUPPORTS", "REFUTES"])
    vm.clear_mocks()
    args, body = record(0)
    web(vm, args, body)
    args1, body1 = record(1)
    web(vm, args1, body1, status=503)
    args2, body2 = record(2, "new-report")
    web(vm, args2, body2)
    model(vm, ["SUPPORTS", None, "SUPPORTS"])
    with vm.expect_revert("Previously accepted evidence unavailable or changed"):
        c.challenge_verdict(*args2)
    assert state(c) == before


def test_challenge_can_build_missing_quorum(setup):
    c, vm = setup
    initial(c, vm, [])
    for i in range(2):
        vm.clear_mocks()
        for j in range(i + 1):
            args, body = record(j, "late-evidence")
            web(vm, args, body)
        model(vm, ["SUPPORTS"] * (i + 1))
        c.challenge_verdict(*record(i, "late-evidence")[0])
    assert state(c)["verdict"] == "VERIFIED"


def test_access_and_immutable_policy(setup, direct_bob):
    c, vm = setup
    args, _ = record(0)
    with vm.prank(direct_bob):
        with vm.expect_revert("Creator only"):
            c.submit_evidence(*args)
        with vm.expect_revert("Creator only"):
            c.register_sources("mainnet", json.dumps(SOURCES))
    with vm.expect_revert("Registry locked"):
        c.register_sources("mainnet", json.dumps(SOURCES))
    with vm.expect_revert("Claim already exists"):
        c.create_claim("mainnet", "new", "new", 1, ts("2026-11-11T00:00:00Z"), 2, 60)
    with vm.expect_revert("Not ready for verification"):
        c.verify_claim("mainnet")
    c.submit_evidence(*args)
    with vm.expect_revert("Initial source slot already filled"):
        c.submit_evidence(*args)
    warp(vm, "2026-11-11T00:00:00Z")
    with vm.expect_revert("Submission closed"):
        c.submit_evidence(*record(1)[0])


@pytest.mark.parametrize("mutation", ["foreign", "archive_host", "after_cutoff", "wildcard", "mismatch", "hash", "credentials"])
def test_evidence_validation(setup, mutation):
    c, vm = setup
    args, _ = record(0)
    args = list(args)
    if mutation == "foreign":
        args[2] = "https://official.example.org.evil.test/article"
    elif mutation == "archive_host":
        args[3] = args[3].replace("web.archive.org", "evil.test")
    elif mutation == "after_cutoff":
        args[3] = args[3].replace("20261109000000", "20261112000000")
    elif mutation == "wildcard":
        args[3] = args[3].replace("20261109000000", "*")
    elif mutation == "mismatch":
        args[3] += "other"
    elif mutation == "credentials":
        args[2] = "https://official.example.org@evil.test/article"
    else:
        args[4] = "bad"
    with vm.expect_revert():
        c.submit_evidence(*args)


def test_owned_domains_cannot_supply_quorum(direct_vm, direct_deploy):
    warp(direct_vm, "2026-11-09T12:00:00Z")
    c = direct_deploy(PATH, sdk_version="v0.2.16")
    c.create_claim("mainnet", "Claim", "Criteria", ts("2026-11-10T23:59:59Z"), ts("2026-11-11T00:00:00Z"), 2, 60)
    sources = [dict(s, publisher="same") for s in SOURCES]
    with direct_vm.expect_revert("Too few publisher groups"):
        c.register_sources("mainnet", json.dumps(sources))
