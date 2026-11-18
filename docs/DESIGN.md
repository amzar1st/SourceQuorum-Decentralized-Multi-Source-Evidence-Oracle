# Design and threat model

## Storage and commitments

`claims: TreeMap[str, str]` stores a canonical JSON document per unique claim ID. Nested evaluation payloads are ordinary memory data before entering nondeterministic execution; no storage proxy is captured by the closures. Using a JSON envelope avoids deployment-specific storage dataclass migrations and makes the entire bounded record easy to inspect in Studio. It trades storage efficiency for simple auditability.

`policy_hash = SHA256(canonical({version,text,criteria,cutoff,submission_deadline,minimum,challenge_seconds}))`.

`sources_hash = SHA256(canonical(three registered sources in their locked order))`.

`evidence_hash = SHA256(canonical(full append-only evidence records at that revision))`.

Canonical encoding is Python `json.dumps` with sorted keys, no separator whitespace, ASCII escapes, then UTF-8 bytes. Body SHA-256 hashes raw HTTP response bytes, without cleaning HTML or changing whitespace. Hashes are lowercase hex without `0x`. Audit history includes accepted assessments rather than unvalidated natural-language explanations.

## Temporal rules

The claim text and `criteria` define the event deadline. `cutoff` defines the latest usable archived information. These are distinct concepts and should be aligned deliberately. For a launch-before-November-30 claim, say explicitly whether November 30 itself is included; choose a cutoff that respects that rule.

Submission deadline is in the future when creating a claim, at most 30 days away, and no earlier than cutoff. Archive capture must be at/before both cutoff and submission transaction time. The document publication time must be at/before both capture and cutoff. This deliberately excludes later retrospective evidence even if it discusses an earlier event.

Initial submission: `now < submission_deadline`.
Verification: `now >= submission_deadline`.
Challenge: `now < challenge_deadline`.
Finalization: `now >= challenge_deadline`.

The challenge deadline is set once at verification transaction time plus the locked duration. Calls do not reset it. All calculations use transaction-pinned GenVM time. Studio/direct mode tests use controlled clocks; there is no caller-supplied current-time parameter.

## Independence algorithm

Three source nodes form a small dependency graph. Add edges for identical registered publisher IDs, identical committed body hashes, and model-detected copied/syndicated/derived reporting. Union-find computes transitive components with the smallest source index as canonical root. Every component counts at most once for support and once for refutation. A component that contradicts itself still creates `CONTESTED`; two conflicting articles never cancel each other into false certainty.

The source policy is part of the oracle's trust model. Similar domains alone neither establish nor disprove independent ownership. The model receives exact origins and ownership notes, but those notes are not verified corporate records. Registry review remains necessary.

## Semantic checks

Each node requests all committed snapshots itself and verifies exact body hashes and actual archive capture timestamps before presenting content to its own model. Fixed instructions classify the event, distinguish completed events from plans and testnets, demand explicit deadline-covering negative evidence, assess publication dates, and mark uncertainty `UNKNOWN`. Documents and ownership notes are untrusted data, including embedded instructions.

Extraction uses `response_format="json"`. Unexpected shape, indexes, labels, dates, or graph edges produce an all-unknown assessment. There are no prose similarity tolerances. Validators independently compute the normalized result and require exact equality of every decision-bearing field. Disagreement may produce an undetermined transaction. This is preferable to silently accepting a weaker leader answer.

## Challenges

An accepted challenge must be from one of the same three origins, historically eligible, distinct in URL and body hash, within a source's total slot limit, and semantically usable. It must change the verdict or increase an independent supporting/refuting group count. Existing eligible assessment rows must remain exactly unchanged; this prevents temporary archive failures from erasing accepted contradictions. The full candidate assessment (including new dependence edges) is independently validated.

A rejection happens before saving any state. Initial creator-only source slots prevent strangers occupying the evidence slots before verification. Accepted challenges are bounded by six total evidence slots and a fixed deadline. Unrelated or inconclusive spam reverts, but transaction/LLM costs and network congestion remain possible. The oracle provides no incentive or anti-Sybil economic mechanism.

## Threats and explicit limitations

| Threat | Mitigation | Residual risk |
| --- | --- | --- |
| Caller fabricates excerpts | Validators fetch archived bytes themselves | Archive operator remains trusted |
| Changed body / wrong snapshot | SHA-256 and exact Memento time checks | Compromised archive or forged source material |
| Multiple domains repeat one press release | Publisher, byte and semantic graph collapse | Hidden ownership / subtle shared origin |
| Post-cutoff evidence | Capture and extracted publication cutoff | Source timestamps can lie; extraction can err |
| Prompt injection in article | Untrusted-data instructions and independent validators | Models can share systematic failures |
| Neutral/absent evidence misread as false | Explicit negation requirement; UNKNOWN fallback | Semantic mistakes remain possible |
| Leader fabricates valid-shaped output | Independent fetch and extraction | Correlated validators/models |
| Challenge extends settlement indefinitely | Fixed deadline; finite evidence slots | Transactions can still be delayed by network |
| Archive outage during a challenge | Preserve prior accepted eligible rows | Challenge may fail rather than repair verdict |
| Malicious creator | Hash-pinned immutable policy/registry | Consumers must vet those hashes |
| Provisional or wrong-policy settlement | Public final flag and commitment hashes | Integrator must actually check them |

No escrow or economic settlement is included. The contract holds no application funds and exposes no payable methods. It is an educational/reusable primitive requiring independent review before consequential use.
