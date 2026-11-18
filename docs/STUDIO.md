# Deploy and demonstrate in GenLayer Studio

1. Open [GenLayer Studio](https://studio.genlayer.com/contracts).
2. Use its built-in account. An external wallet extension is not required for the Studio simulator.
3. Import `contracts/source_quorum.py` using the upload icon. When replacing an existing import, use a distinct filename or verify its text; Studio may keep an older same-name entry.
4. Open Run & Debug, choose the imported SourceQuorum contract, and deploy. Constructor takes no arguments.
5. Save the returned transaction hash, status, contract address, built-in account, and source-body SHA-256 in `deployments/studio.json`. Simulator deployments are not testnet deployments.
6. Invoke `create_claim` with a future submission deadline. All numeric times are Unix UTC seconds. Use a challenge duration of 60 seconds for a short demo.
7. Invoke `register_sources` with exactly three vetted sources as a JSON string. Registry is immutable immediately afterward.
8. Prepare real eligible archived evidence using `scripts/prepare_evidence.py`, then submit its argument values with `submit_evidence`. Capture must be no later than the cutoff and already in the past.
9. Wait until submission deadline and invoke `verify_claim`. Read `get_claim` to inspect accepted evidence labels, independence groups, and audit history.
10. Optionally submit a valid contradictory archive with `challenge_verdict` before the challenge deadline.
11. Once that window ends, invoke `finalize_claim`. Read `get_verdict` and confirm `final: true`.

To demonstrate availability failure honestly, submit no evidence and verify after deadline. The verdict must be `INSUFFICIENT`. This shows a working state transition; it does not show live semantic corroboration. The offline demo and tests exercise semantic cases with mocked external inputs and are explicitly labeled that way.

For an actual live semantic demonstration, choose three authentic accessible pre-cutoff archives whose full UTF-8 bodies are at most 80 KB, run the evidence preparation tool, and record the live receipt. If archival retrieval is blocked or a model disagrees, report that outcome rather than claiming a successful verification.

Applications should consume only finalized results with matching expected policy and source hashes. Check protocol finality separately from the claim's application phase.
