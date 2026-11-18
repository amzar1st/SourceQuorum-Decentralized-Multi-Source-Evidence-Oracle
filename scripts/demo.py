#!/usr/bin/env python3
"""Reproducible OFFLINE demo: real contract + SDK, mocked web and model decisions."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from test_source_quorum import SOURCES, initial, state, ts, warp, model, web, record
from gltest.direct import VMContext
from gltest.direct.loader import deploy_contract, create_address


def run(labels):
    vm = VMContext()
    vm.sender = create_address("demo")
    vm.check_pickling = True
    with vm.activate():
        warp(vm, "2026-11-09T12:00:00Z")
        c = deploy_contract(ROOT / "contracts/source_quorum.py", vm, sdk_version="v0.2.16")
        c.create_claim("mainnet", "Did XYZ launch its mainnet by November 10, 2026?",
                       "A public production mainnet must be operational; exclude testnet and launch plans.",
                       ts("2026-11-10T23:59:59Z"), ts("2026-11-11T00:00:00Z"), 2, 60)
        c.register_sources("mainnet", json.dumps(SOURCES))
        s = initial(c, vm, labels)
        assert vm.run_validator() is True
        warp(vm, "2026-11-11T00:01:00Z")
        c.finalize_claim("mainnet")
        return {"labels": labels, "verdict": s["verdict"], "final": json.loads(c.get_verdict("mainnet"))["final"],
                "validator_agreed": True, "assessment": s["history"][0]["result"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Compare against committed expected demo output")
    args = parser.parse_args()
    cases = [["SUPPORTS", "SUPPORTS", "UNKNOWN"], ["REFUTES", "REFUTES", "UNKNOWN"],
             ["SUPPORTS", "REFUTES", "UNKNOWN"], ["SUPPORTS", "UNKNOWN", "UNKNOWN"]]
    output = {"mode": "OFFLINE_MOCKED_NOT_LIVE_CONSENSUS", "cases": [run(labels) for labels in cases]}
    expected = ROOT / "examples/demo-output.json"
    if args.check:
        assert json.loads(expected.read_text()) == output, "Demo output differs"
        print("Four verdict scenarios match; each finalized and passed the captured validator.")
    else:
        print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
