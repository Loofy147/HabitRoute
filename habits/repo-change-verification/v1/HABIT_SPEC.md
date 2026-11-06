# Repo Change Verification — Hand-Designed Habit v1

**Habit ID:** `repo-change-verification`  
**Version:** `1.0.0`  
**Status:** HAND_DESIGNED / NOT YET RUNTIME-ENFORCED  
**Owner:** HabitRoute  
**Execution mode:** read-only inspection and validation; no repository mutation  
**Mining status:** prohibited until the evidence and promotion gates in this specification are met

This is the first manually authored habit. Its purpose is to establish intent and non-negotiable behavior before any trace-mining system is allowed to propose optimizations. The machine-readable flow is in [flow.json](flow.json). The JSON Schemas under `shared/contracts/v0.1/` define the trace, decision, decision-outcome and verdict records.

## 1. Intent

Verify a proposed repository change completely and reproducibly by inspecting its full affected scope, running or justifiably reusing every required validation, preserving evidence, and refusing a success claim unless constraints and independent checks hold.

## 2. Scope and exclusions

### In scope

- A repository change presented for review or verification.
- Tracked, untracked, added, modified, deleted, renamed, binary, generated and submodule paths.
- Related source files, interfaces, tests, configuration, build metadata, dependency lockfiles and workflow configuration needed to determine impact.
- Local validation and later CI validation tied to the same immutable source snapshot.
- Read-only observation, testing, evidence collection and reporting.

### Explicitly out of scope

- Editing source files, formatting files, generating code, applying patches or repairing failures.
- Committing, pushing, merging, releasing, deploying, deleting, resetting, rebasing or changing branches.
- Installing or upgrading dependencies unless a separate authorized flow explicitly permits it.
- Credential discovery, printing, copying or changing.
- Treating a successful command exit as semantic proof without checking what it actually validated.
- Mining or activating a new habit from one run or from unverified chat/log text.

This first version is deliberately a verifier, not an implementation agent. A failed check produces a finding or a blocked outcome; it does not authorize an automatic repair.

## 3. Non-negotiable invariants

1. **Inspect before validating.** The full change inventory and affected context are captured before test selection or execution.
2. **No changed path disappears.** Every changed path has an inventory record, a file classification, an inspection disposition and an applicable validation disposition. Unsupported or unreadable paths block completion.
3. **Validation follows the change.** Each changed path is covered by a suitable test, static validator, build check, documentation check or an explicit finding that no adequate validator exists. Code and behavior changes require relevant tests.
4. **Evidence is attached to the exact target.** Commands, exit states, logs, test identifiers, source digests, tool versions and verifier results refer to the same immutable revision or captured working-tree snapshot.
5. **Skipping is per validation target, never global by convenience.** A validation may be skipped only under the complete fingerprint rule below.
6. **Unknown is not pass.** Missing evidence, unavailable budget measurement, ambiguous source state, unknown side-effect outcome or unobservable intervention state cannot be converted to success.
7. **Constraints are authoritative.** The habit cannot expand its permissions, edit the repository, suppress a failure, lower a required validation level or approve its own exception.
8. **No hidden rescue.** Every human intervention, manual command, external write and approval is recorded. An unobservable intervention channel prevents an autonomous-success claim.
9. **No hindsight rewriting.** Decision records preserve the options and evidence available when the decision was made. Later outcomes are appended separately.
10. **Historical records are immutable.** Corrections, invalidations and revalidation results are new events, not edits to past traces or decisions.

## 4. Preconditions

The run must bind all of the following before inspecting files:

- Canonical repository identity and workspace root.
- Base revision and target revision, or an explicitly captured working-tree snapshot.
- The requested change objective and acceptance criteria.
- Applicable constraint-policy ID, immutable version and digest.
- Read-only capability profile and permitted validation commands.
- Required budgets and their measurement methods: tokens, elapsed time, tool calls, retries and any configured resource/external-cost ceiling.
- Validation environment identity: operating system/runtime, test runner and relevant tool versions, dependency/lockfile state, and relevant non-secret configuration.
- Evidence destination and retention policy.
- Whether later CI or another independent validation source is available.

If the baseline, target, workspace root, policy version or required budget contract cannot be established, the run is BLOCKED before validation.

The verifier must not copy secrets into the trace. Where a secret or sensitive environment value affects reproducibility and cannot safely be represented by a non-reversible reference/digest, that validation target is non-cacheable.

## 5. Hand-designed flow

The authoritative node order and branch conditions are in `flow.json`. In prose, the sequence is:

1. **Bind task and policy.** Record objective, acceptance criteria, repository identity, source range, constraint version, budgets and authorized read-only capabilities.
2. **Preflight.** Verify the workspace and repository state, branch/ref, base and target, dirty/untracked state, available tools and policy. Do not change anything.
3. **Inventory the complete change.** Capture tracked and untracked paths, renames, deletions, submodules, binary/generated content and relevant dependency/configuration files. Record a digest for the inventory and each content item that can be safely read.
4. **Inspect every changed path.** Read the full changed content and enough surrounding/dependency context to understand effects. Record findings and inspection coverage per path. An unreadable or unclassified file is not silently omitted.
5. **Choose validation.** Create a path-to-validation matrix. Select checks based on file type, changed behavior, affected interfaces and dependency closure. Record why each check is required.
6. **Evaluate each possible skip.** Check the complete fingerprint and matching prior evidence. Record a decision for each validation target. If any fingerprint input is unknown or mismatched, execute the validation.
7. **Run required validations.** Execute only policy-allowed commands. Capture command identity, exact arguments (with secrets redacted), environment fingerprint, start/end, exit status, logs/artifact references and measured cost. Retry only a classified transient failure when the operation is safe and the retry budget allows it.
8. **Collect and validate evidence.** Verify that every required artifact exists, is readable, matches its digest, refers to the correct source snapshot and supports the named claim. A pass status without its underlying output is incomplete evidence.
9. **Independent end check.** Recompute the relevant source/inventory fingerprint and confirm that the target under test did not change during validation. Check that no unrecorded write or human rescue occurred.
10. **Issue a provisional verdict.** Return VERIFIED_AT_END only when all immediate gates pass. Otherwise return FAILED, BLOCKED, NEEDS_ATTENTION, ASSISTED, INCOMPLETE or INVALIDATED with reasons and evidence references.
11. **Revalidate later.** When CI or another independent verifier reports on the exact same immutable source digest, append a decision-outcome/revalidation event. Only then may the run become SUCCESS_HELD and enter the mining-eligible population.

## 6. Validation selection rules

The validation plan must cover every changed path and its affected behavior. At minimum:

| Change class | Required treatment |
|---|---|
| Source or behavior code | Inspect changed code and affected call sites/interfaces; run directly relevant tests plus the required regression suite; run applicable type/lint/build checks |
| Test code | Inspect the test and fixture changes; run the changed tests and relevant suite; verify that the tests fail for the intended defect where practical |
| Dependency manifest or lockfile | Inspect dependency delta and provenance; resolve/install only under separate authorization; run import/build and affected regression checks in a clean locked environment |
| CI/workflow/build configuration | Validate syntax and policy-sensitive changes; run the closest executable workflow/build checks; verify the intended job/trigger/permission behavior |
| Schema/API/interface | Validate schema compatibility and consumers; run producer/consumer and compatibility tests |
| Documentation only | Inspect every changed document; run link/path/reference, generated-doc and schema/document consistency checks where applicable; do not claim runtime behavior was tested |
| Generated or binary asset | Verify generator/provenance or format-specific integrity, inspect metadata/content where possible, and verify the expected digest; unsupported opaque content blocks full verification |
| Deleted or renamed path | Verify references, import paths, package manifests and consumers; ensure the deletion/rename is intended and complete |
| Submodule or external source reference | Verify pinned identity/revision and availability; do not silently fetch or update it |

A validation gap must be reported as a gap. The verifier must not substitute an unrelated test merely to produce a green result.

## 7. Safe validation-skip rule

A skip is valid only when **all** conditions below hold for the specific validation target:

- The current validation fingerprint is fully computable and matches the fingerprint in a prior evidence record.
- The fingerprint covers the exact target content and its dependency closure: relevant source files, test files, fixtures, schemas, build/test configuration, dependency lockfiles, test command and arguments, relevant tool/runtime versions, environment identity and policy/constraint version.
- The prior run's evidence is immutable, complete, independently validated and has a successful result for that exact validation target.
- The prior result was produced under the same or explicitly compatible validation policy and harness contract.
- The prior evidence has not expired, been revoked, quarantined or invalidated by drift.
- The validation is deterministic enough to reuse. Tests depending on live services, changing remote state, current time, nondeterministic providers, unpinned dependencies, mutable external data or untracked secrets are non-cacheable unless their relevant inputs are captured and pinned.
- The current source snapshot and validation scope are complete; no unknown/untracked input can affect the result.

If one condition is false or unknown, run the validation. A cache hit is a recorded decision backed by evidence, not an optimization inferred from a matching filename or commit label.

Fingerprint format: SHA-256 over a canonical, versioned manifest of all required inputs. The manifest itself is retained as evidence. A commit SHA alone is not a sufficient test fingerprint when test configuration, environment, dependencies or external inputs can differ.

## 8. Decision points and required records

The following choices require a separate immutable decision record:

- Is the workspace/source baseline sufficiently well-defined to proceed?
- Is the change inventory complete?
- Which files and dependencies are in scope for each validation?
- Which validation level applies to each change class?
- Can a validation target be skipped under the safe-skip rule?
- Is a failure transient and safely retryable, or deterministic/unsafe?
- Is evidence complete and independent enough for VERIFIED_AT_END?
- Does later independent validation justify SUCCESS_HELD?

The record must include all materially considered options, including STOP/BLOCK and BASELINE/FULL-VALIDATION alternatives. Rationale must refer only to evidence available at decision time. Reversibility and reversal cost are mandatory. Later outcome belongs in a separate append-only outcome record.

## 9. Retry, failure and escalation

- Deterministic test, assertion, type, lint, build or policy failures are not retried just to obtain a pass.
- A transient infrastructure failure may be retried only if the command is read-only/repeatable, the failure is classified, the retry budget remains, and the same inputs and policy still apply.
- A timeout or lost acknowledgement for an operation with an uncertain external effect is NEEDS_ATTENTION, not an automatic retry.
- Missing tools, inaccessible evidence, unresolved dependencies or incomplete inspection produce BLOCKED/INCOMPLETE.
- Any unauthorized write, bypass, scope expansion, constraint weakening or unrecorded intervention invalidates the autonomous-success claim.
- The verifier must preserve failed attempts and reasons. It may not replace them with a later green run without retaining the full history.

## 10. Success contract

### VERIFIED_AT_END

This is a provisional, run-local verdict. It requires all of the following:

- Every required precondition and invariant passed.
- Every changed path and required dependency was inventoried and inspected.
- Every required validation ran or met the safe-skip rule.
- All required evidence exists, validates and is bound to the exact source snapshot.
- Independent evidence verification passed.
- Source fingerprint remained stable through the terminal check.
- No prohibited action occurred; approvals and all interventions are recorded.
- Token, time, tool-call, retry and configured resource budgets are within limits, with actual measurements or an explicit non-success/unknown state for any unobservable required dimension.
- No hidden human rescue occurred.

### SUCCESS_HELD

This is the only terminal status eligible for mining as a successful flow. It additionally requires:

- A later independent validation or CI result for the exact same immutable source digest.
- The required post-run hold/revalidation condition has been satisfied.
- No source, dependency, policy, harness or evidence drift invalidated the result.
- Any revalidation failure or subsequent correction is appended as a new event and invalidates the prior success for the affected scope.

A local test pass on a mutable working tree is not SUCCESS_HELD.

### Never-success states

`FAILED`, `BLOCKED`, `NEEDS_ATTENTION`, `ASSISTED`, `INCOMPLETE`, `INVALIDATED` and `PROVISIONAL_BUDGET_UNOBSERVABLE` are not successful outcomes and are not eligible for success-pattern mining. They remain valuable for anti-habit and failure analysis.

## 11. Trace and evidence contract

Every event records, at minimum:

- immutable flow/run/habit IDs and versions;
- source repository identity, base/target refs and content/inventory digests;
- monotonically increasing event sequence, event ID and UTC timestamp;
- event type, step/checkpoint, branch and selected decision ID where applicable;
- actor/source identity and intervention classification;
- constraint-policy ID/version/digest;
- input/output/evidence references and SHA-256 digests;
- validation target, command identity, outcome, exit state and verifier identity/version;
- observed budget/cost values with units and measurement method;
- wait/retry/approval state and reason;
- previous-event digest and current-event digest when hash chaining is enabled.

The trace is an append-only, structured observation record, not a narrative transcript. Raw prompts, credentials, tokens, private environment values and unnecessary repository content must not be copied into it. Refer to artifacts by access-controlled URI/ID and digest.

Hash chaining detects accidental or partial alteration, but without an authenticated signature or independently protected store it is not proof against an attacker able to rewrite the entire journal.

## 12. Human intervention and rescue

Record approvals, clarifications, manual command execution, manual file edits, environment repairs, reruns initiated outside the flow, credential changes and external writes.

Classify each as:
- `APPROVAL`: predeclared approval at an explicit decision gate;
- `ASSISTANCE`: a human supplies information or performs a step needed for progress;
- `RESCUE`: a human changes the target, repairs the environment, bypasses a failure or otherwise makes the run succeed;
- `UNOBSERVED`: the system cannot establish whether external intervention occurred.

Approval does not automatically mean rescue, but it must be recorded. ASSISTANCE prevents an autonomous-success claim. RESCUE or UNOBSERVED prevents SUCCESS_HELD. A separate assisted outcome may be useful, but it must not be mixed into autonomous efficiency measurements.

## 13. Mining boundary: deliberately later

No mining is part of v1 execution. Mining may begin only after a dataset contains independently verifiable structured traces and separate decision/outcome records.

A candidate pattern must demonstrate:
- recurrence across independent runs and meaningfully distinct repository/task cases;
- low variance and a measured success/reliability bound, not just a high raw pass percentage;
- complete evidence and known budgets;
- no hidden rescue, unrecorded intervention or constraint bypass;
- safe skip behavior proven against changed-input and changed-environment counterexamples;
- edge/failure handling that does not turn unknown outcomes into success;
- net savings after lookup, fingerprinting, test, evidence, revalidation and recovery overhead;
- no later rework or outcome invalidation that erases the apparent saving.

Mining outputs suggestions only. It cannot change the active habit. A human-authored v2 must state its changed intent/logic/invariants, pass the same acceptance suite, and carry a new immutable version. Failed shortcuts become anti-habit candidates and must be tested as regressions.

A recurring decision can be incorporated into a later habit only when its rationale and evidence signature recur under compatible constraints, the decision was reasonable using evidence available at the time, and later outcomes do not reveal systematic harm. Outcome luck alone is not proof of decision quality.

## 14. Acceptance tests required before runtime activation

The following are mandatory behavioral tests, not documentation checkboxes:

1. Inspection is recorded before any validation command can run.
2. Every changed path must have an inspection disposition; an unreadable/unclassified path blocks success.
3. Source changes cannot pass with only documentation checks.
4. Documentation-only changes cannot be falsely reported as runtime-tested.
5. A changed file, test, dependency, lockfile, configuration, tool version, environment or policy changes the relevant fingerprint and defeats a skip.
6. A prior passing result with missing logs, missing digest, mismatched policy or invalid verifier cannot justify a skip.
7. Live/external/nondeterministic validation cannot be skipped without pinned inputs and a declared replay contract.
8. One failed deterministic test cannot be retried into success.
9. A transient read-only infrastructure failure can be retried only within the declared budget and is preserved in the trace.
10. An unapproved mutation or hidden manual repair prevents SUCCESS_HELD.
11. Unknown token/time/tool/retry accounting prevents a fully budget-verified success claim.
12. Incomplete or invalid evidence prevents VERIFIED_AT_END.
13. CI for a different commit/digest cannot satisfy the later-hold requirement.
14. A later failed revalidation appends an invalidation and removes the run from the success-eligible set without rewriting history.
15. Replay preserves event order, decision references, evidence references, cost and intervention states.
16. Trace and decision records reject missing identity, version, time, provenance or required fields.
17. A mined shortcut cannot bypass any invariant and is not auto-activated.
18. The active habit version and constraint version used by every run are immutable and explicit.

## 15. Implementation boundary

This specification is a hand-authored design artifact, not a claim that HabitRoute currently enforces the behavior. Before activation, implement and test the trace/decision contracts, operation-level durable checkpoint protocol, evidence validation, budget measurement, intervention observability and the acceptance suite. Until those exist, this habit may be reviewed and rehearsed in read-only/manual mode only; its runs must not be mined as verified machine habits.
