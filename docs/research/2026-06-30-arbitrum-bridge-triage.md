# Arbitrum bridge/gateway triage log - 2026-06-30

Status: **DRAFT / NOT A VALIDATED BOUNTY FINDING**

This note records manual triage and platform improvements from local-only Arbitrum
bridge/gateway research. It is not an Immunefi report and must not be submitted as a
validated vulnerability without confirmed scope, impact mapping, and a local PoC or
equivalent strong evidence.

## Runs reviewed

- Semgrep + internal run:
  `artifacts/runs/arbitrum-20260630T210645Z-a408545a`
- Slither + internal run:
  `artifacts/runs/arbitrum-20260630T211533Z-a408545a`
- Latest Semgrep + internal regression run after detector-noise reduction:
  `artifacts/runs/arbitrum-20260701T083736722887Z-26c7eb30`
  - Semgrep completed for both selected Arbitrum repositories.
  - Internal detectors completed.
  - Review queue was reduced to 3 non-promoted findings: the known optional metadata
    issue plus two low-confidence counterpart-gated liveness loops.
- Latest Slither degraded-mode run:
  `artifacts/runs/arbitrum-20260701T084153351457Z-26c7eb30`
  - Slither timed out on the selected upstream repositories and returned structured
    analyzer failures instead of aborting the whole pipeline.
  - Internal detectors continued and produced the same 3 review-only findings.
- Live scope attestation:
  `artifacts/scope/arbitrum/20260630T222143Z.json`
  - 181 smart-contract asset rows
  - 13 in-scope impacts
  - exact reviewed snapshot match
  - scope hash:
    `e22d5a917fa11afcd863cc070a994a640856bf66d82245c97c884d08f542d6ce`

## Tooling result

- Upstream `OffchainLabs/token-bridge-contracts` dependencies were installed in the
  ignored cache with `yarn install --frozen-lockfile --ignore-scripts`.
- `hardhat compile` succeeded for `OffchainLabs/token-bridge-contracts` after passing
  a command-local Git `safe.directory` setting.
- Slither 0.11.5 produced JSON for `OffchainLabs/token-bridge-contracts`.
- Slither returned a silent `exit 1` for `OffchainLabs/nitro-contracts`; no JSON,
  stdout, or stderr was produced. Treat Nitro Slither coverage as degraded for this
  run.
- The target mapping originally selected only 12 token-bridge files even though the
  live bridge scope contains 43 paths in `OffchainLabs/token-bridge-contracts`.
  The reviewed bridge profile now selects all 43 token-bridge paths plus 15
  bridge-focused Nitro paths.
- Source acquisition now fails closed if even one configured reviewed path is missing;
  it no longer silently analyzes a partial subset.
- Local CI-style verification was green after the toy bridge invariant stabilization:
  Ruff, mypy, pytest, Semgrep rule validation, and Foundry fixture tests passed locally.
  The current GitHub Actions run for commit `80efd62` also completed successfully.

## Internal detector refinement

The first Arbitrum run produced noisy cross-chain and gateway-mapping signals because
the textual guard detector did not recognize `onlyCounterpartGateway`.

The detector was refined to recognize counterpart/cross-domain guard markers such as:

- `onlyCounterpartGateway`
- bridge/outbox sender checks
- address alias helper checks

After this, the Arbitrum Semgrep + internal run dropped from 9 review findings to 6.
The remaining internal findings are low-confidence review items rather than validated
bugs.

The analyzer evidence path was also corrected so Slither/Semgrep findings are admitted
only when their source location exactly matches a selected path for that repository.
This prevents whole-repository compilation from importing out-of-profile findings.

Follow-up noise-reduction changes added explicit handling for:

- revert-only bridge-token stubs, so abstract placeholder `bridgeMint` / `bridgeBurn`
  methods are not treated as reachable missing-access-control bugs;
- typed `AlreadyInit` / non-zero bridge initializer guards;
- known Arbitrum guarded initializer chains such as `TokenGateway._initialize`,
  `L1ArbitrumGateway._initialize`, `L2ArbitrumGateway._initialize`,
  `GatewayRouter._initialize`, and `L2GatewayToken._initialize`;
- internal/private/admin-only loop paths, so they are not elevated to public
  user-controlled gas-griefing signals;
- matching Semgrep exclusions for revert-only stubs and already-initialized guards.

## Manual triage notes

### Known issue reproduced: optional ERC20 metadata revert data locks the first deposit

Status: **technically reproduced, but rejected as a new bounty candidate because it is
publicly documented as Trail of Bits finding `TOB-ARBGOV-15`**.

#### Root cause

The standard bridge attempts to support ERC20 metadata compatibility, including absent
getters and legacy `bytes32` metadata. The following cross-chain sequence is unsafe:

1. `L1ERC20Gateway.callStatic` performs a metadata `staticcall` but discards its
   success flag and returns the raw bytes for both success and failure.
2. `getOutboundCalldata` embeds those raw bytes for `name()`, `symbol()` and
   `decimals()` in the retryable payload.
3. An otherwise valid ERC20 can omit the optional `name()` getter and revert with an
   ordinary reason string for an unknown selector.
4. The failed L1 call therefore contributes non-empty ABI `Error(string)` bytes,
   beginning with selector `0x08c379a0`, rather than empty "getter unavailable" data.
5. On L2, `StandardArbERC20.bridgeInit` passes those bytes to
   `BytesParser.toString`.
6. `BytesParser.toString` executes `abi.decode(input, (string))`, which reverts for
   the `Error(string)` payload.
7. `L2ERC20Gateway.handleNoContract` cannot complete proxy initialization, so the
   CREATE2 deployment rolls back and the retryable remains unexecutable.
8. The successful L1 deposit transaction already escrowed the user's tokens and
   cannot be rolled back by the later L2 failure.

Relevant live-scope paths:

- `contracts/tokenbridge/ethereum/gateway/L1ERC20Gateway.sol`
- `contracts/tokenbridge/arbitrum/gateway/L2ERC20Gateway.sol`
- `contracts/tokenbridge/arbitrum/StandardArbERC20.sol`
- `contracts/tokenbridge/libraries/BytesParser.sol`
- `contracts/tokenbridge/libraries/ClonableBeaconProxy.sol`

#### Local proof

Committed PoC:

`pocs/arbitrum/optional-metadata-revert-lock/`

The PoC deploys the real upstream L1/L2 gateways, inbox mock, beacon, proxy factory and
standard L2 token logic. Its L1 token implements the required ERC20 surface, exposes
valid `symbol()` and `decimals()`, omits optional `name()`, and uses a normal
reason-string revert for unknown selectors.

Observed assertions:

- L1 deposit succeeds.
- L1 gateway balance increases by the full deposited amount.
- Retryable metadata contains `Error(string)` selector `0x08c379a0`.
- The exact retryable calldata reverts on two independent execution attempts.
- The expected CREATE2 L2 token address remains code-free.
- L1 escrow remains unchanged after both L2 failures.

Local result:

```text
Research: optional metadata revert data
  1 passing
```

#### Read-only deployed-path verification

No transaction was sent. Read-only RPC and verified-source checks showed:

- Ethereum block `25433482`:
  - L1 standard gateway proxy:
    `0xa3A7B6F88361F48403514059F1F16C8E78d60EeC`
  - active implementation:
    `0xb4299A1F5f26fF6a98B7BA35572290C359fde900`
  - counterpart:
    `0x09e9222E96E7B4AE2a407B98d48e330053351EEe`
  - L2 beacon proxy factory:
    `0x3fE38087A94903A9D946fa1915e1772fe611000f`
- Arbitrum One block `479067245`:
  - L2 standard gateway:
    `0x09e9222E96E7B4AE2a407B98d48e330053351EEe`
  - beacon:
    `0xE72ba9418b5f2Ce0A6a40501Fe77c6839Aa37333`
  - active standard-token implementation:
    `0x3f770Ac673856F105b586bb393d122721265aD46`

The verified deployed L1 source contains the success-discarding `callStatic` logic, and
the verified deployed standard-token source contains the same reverting
`BytesParser.toString` path.

#### Impact and remaining rejection risk

The technical impact is a first-deposit lock for a token whose optional string metadata
getter is absent/reverting with data: tokens remain in L1 escrow while the associated
L2 finalization cannot deploy or initialize the standard representation. Recovery
requires a gateway/token-logic upgrade or another privileged intervention.

This is stronger than a deliberately malformed return-value example because ERC20
`name`, `symbol`, and `decimals` are optional metadata methods.

Duplicate/known-issue review found an exact public match:

- Audit:
  `audits/trail_of_bits_governance_report_1_6_2023.pdf`
- Finding:
  `TOB-ARBGOV-15 - Lack of contract existence checks in the gateway may not detect
  failed execution`
- Printed pages:
  47-48 (PDF pages 48-49)
- The report explicitly states that failed parsing can leave tokens stuck in
  `L1ERC20Gateway` and reproduces the same `callStatic` and `bridgeInit` paths.

Current decision: **do not submit**. Keep the PoC as a regression fixture and keep the
detector as a known-pattern signal, but exclude this issue from the novel-candidate
queue.

### Cross-chain sender validation and gateway mapping

Initial alarms around:

- `L1ArbitrumGateway.finalizeInboundTransfer`
- `L2ArbitrumGateway.finalizeInboundTransfer`
- `L2GatewayRouter.setGateway`

were not promoted. The relevant functions are guarded by `onlyCounterpartGateway`.
On L1 this validates the bridge caller and L2-to-L1 sender. On L2 this validates the
aliased L1 counterpart gateway.

Current status: **rejected as current bug candidates**.

### Known issue reproduced: reverse-gateway nested withdrawal over-accounting

Status: **technically reproduced, but rejected as a new bounty candidate because
the reentrancy/accounting root cause is already public**.

The current upstream `L2ReverseCustomGateway` measures its own token balance,
calls `safeTransferFrom`, and then returns the full balance delta. It does not
use a reentrancy guard. A callback-capable token can notify the sender before
the outer transfer mutates balances. The sender then starts a nested withdrawal.

Local proof:

`pocs/arbitrum/reverse-gateway-reentrancy-regression/`

Observed assertions:

- The holder supplies 140 L2 tokens in total.
- The nested withdrawal emits 40.
- The outer withdrawal emits 140 because its initial balance snapshot predates
  the nested transfer.
- The L2 gateway therefore escrows 140 while L2-to-L1 messages encode 180.
- Processing both local messages mints 180 L1 representation tokens.

Duplicate review found the same vulnerability class and nearly identical
numeric example in:

- ConsenSys Diligence, *Arbitrum Smart Contracts*, issue 5.1, PDF pages 14-16.
  It describes callback reentrancy causing 100 escrowed tokens to mint 150 and
  explicitly recommends L1 and L2 reentrancy guards.
- Trail of Bits, `TOB-ARBGOV-13`, PDF pages 42-45. It documents callback-driven
  reverse/custom gateway over-accounting and recommends tracking the gateway
  balance as one possible remediation.

Read-only deployment checks found that Arbitrum One reverse gateway proxy
`0xCaD7828a19b363A2B44717AFB1786B5196974D8E` currently points to verified
`L2ReverseCustomGateway` implementation
`0x5d96786d3eb13cad05c9fd7d0f7bb9560b4e5056`, whose source still has the
unguarded balance-delta sequence. Its observed `TokenSet` history contains one
mapping, from L1 ARB to L2 ARB. That ordinary ERC20 path does not expose the
callback used by this PoC.

Current decision: **do not submit**. Preserve it as a regression fixture and a
high-signal detector case, but exclude it from the novel-candidate queue.

### Known behavior: ERC20 Inbox prefunded native-token balance can fund a later deposit

Status: **rejected as a new bounty candidate because the behavior is explicitly
implemented, commented, and covered by upstream tests**.

The ERC20-native Orbit inbox checks its own native-token balance before pulling tokens
from the caller:

- `src/bridge/ERC20Inbox.sol`
- `_deliverToBridge(...)`
- if the inbox already holds at least `tokenAmount`, no `safeTransferFrom(msg.sender, ...)`
  is performed;
- the bridge then pulls the approved inbox balance and enqueues the delayed message.

This initially looked like a possible ambient-balance consumption bug: if a third party
or previous flow leaves native tokens on the inbox, a later caller can submit
`depositERC20(amount)` without their own tokens being transferred.

Manual review found that this is intentional for ERC20-native retryable flows. The
source comment states that the inbox may have been pre-funded in a prior call as part of
token bridging. Upstream Foundry test
`test/foundry/ERC20Inbox.t.sol::test_depositERC20_FromEOA_InboxPrefunded` explicitly
mints native tokens to the inbox, calls `depositERC20` as a user, and asserts the user's
token balance is unchanged while the bridge balance increases.

Current decision: **do not submit** unless a later, separate proof shows that an
ordinary protocol path can leave another user's pre-funded balance available across
transactions without that being merely a direct token donation or intended gateway
prefunding.

### Known public dispute/report: delay-buffer accounting differs for force inclusion

Status: **technically reproduced locally, but rejected as a new bounty candidate because
the same force-inclusion delay-buffer inconsistency is already public in the 2024
Code4rena Arbitrum Foundation findings**.

A targeted local Hardhat regression showed that force-including delayed messages can
anchor delay-buffer updates differently from the normal delayed-message proof path:

- normal delay-proof logic anchors on the first unread delayed message in the batch;
- the force-inclusion path can anchor on the force-included message being appended;
- the result preserves more delay buffer than the normal path for an equivalent batch.

Read-only deployment checks showed Arbitrum One and Nova sequencer inbox proxies both
pointing to implementation `0x98a58ADAb0f8A66A1BF4544d804bc0475dff32c7`, with
`isDelayBufferable() == true` and a live maximum buffer of 14,400 blocks.

Duplicate review found Code4rena issue `#55`, selected as medium issue `M-01`, titled
“Inconsistent sequencer unexpected delay in DelayBuffer may harm users calling
forceInclusion()”. The sponsor disputed it publicly, but it is still not a novel
private bounty candidate.

Current decision: **do not submit**. Keep the local regression as a research note and
possible future platform fixture, not as a report candidate.

### Initializer review

Remaining initializer findings are low-confidence because the public initializer entry
points delegate to internal initializer functions instead of using an OpenZeppelin
`initializer` modifier directly.

Observed guard path:

- `L2ERC20Gateway.initialize`
- `L2CustomGateway.initialize`
- `L2WethGateway.initialize`
- `L2GatewayRouter.initialize`
- internal path reaches `TokenGateway._initialize`
- `TokenGateway._initialize` requires `counterpartGateway == address(0)` and reverts
  with `ALREADY_INIT` once initialized.

Current status: **needs deployed-proxy initialization verification, not a validated
code vulnerability**.

#### Rollup initializer follow-up

Status: **reviewed, not promoted as a bounty candidate**.

A scoped Semgrep pass over Nitro rollup/challenge/assertion/state sources produced three
initializer-review signals:

- `src/rollup/RollupCore.sol::initializeCore`
- `src/rollup/RollupProxy.sol::initializeProxy`
- `src/rollup/RollupUserLogic.sol::initialize`

Manual review:

- `initializeCore` is an internal helper invoked by admin initialization, not a public
  reinitializer surface by itself.
- `RollupProxy.initializeProxy` only performs the initial proxy setup when admin, primary
  implementation, and secondary implementation slots are all empty; otherwise it falls through
  to normal proxy dispatch.
- `RollupUserLogic.initialize` is `external view onlyProxy` and only validates that the stake
  token is non-zero. It does not mutate storage and is paired with admin initialization.
- Targeted upstream Foundry checks for `RollupTest::testSuccessFastConfirmNewAssertion` and
  `RollupTest::testPartialDepositCanWithdraw` passed under `FOUNDRY_PROFILE=test`, confirming
  the local checkout can execute the reviewed Rollup test harness for these paths.

Current decision: **do not submit**. Keep these as tool-noise calibration cases for the
upgradeability detector unless deployed proxy metadata later shows an unexpected initialization
state mismatch.

### Gas/liveness collection loops

Remaining low-confidence gas/liveness signals:

- `L2GatewayRouter.setGateway`
- `L2CustomGateway.registerTokenFromL1`

Manual L1 source review found that ordinary trustless user paths encode a single
token/gateway pair. Bulk array paths are owner-controlled:

- `L1GatewayRouter.setGateway(...)` creates arrays of length 1 for trustless token
  self-registration.
- `L1CustomGateway.registerTokenToL2(...)` creates arrays of length 1 for trustless
  custom token registration.
- bulk `setGateways` / `forceRegisterTokenToL2` style paths are owner-only.

Current status: **low-priority liveness review, not a strong bounty candidate**.

### Slither numeric rounding signal

Slither flagged `_getScaledAmount` in `L1AtomicTokenBridgeCreator` as
divide-before-multiply. Manual review shows the code intentionally rounds up after
division when token decimals are below 18.

Current status: **rejected as a current bug candidate**.

### Slither USDC mint unused-return signal

Slither flagged `L2USDCGateway.inboundEscrowTransfer` for ignoring the bool returned by
`IFiatToken.mint`.

Manual dependency review of `@offchainlabs/stablecoin-evm` shows the referenced FiatToken
implementation enforces success with `require` checks and returns `true` after minting.
The ignored bool is therefore not enough for an exploit claim against the bundled
implementation.

Current status: **not promoted; keep as compatibility-hardening note only**.

### Slither retryable / arbitrary send signals

Retryable and arbitrary-send findings in `L1AtomicTokenBridgeCreator` and
`L1TokenBridgeRetryableSender` were emitted because Slither compiled the whole
repository. Those paths were not in the selected bridge profile. The pipeline now
filters analyzer output to exact selected paths, so these signals are no longer admitted
as profile findings. Manual read also showed that the value transfers are expected
retryable funding/deployer refund flows and that the sender contract is `onlyOwner`
gated.

Current status: **rejected for this profile unless the selected live-scope mapping is
explicitly expanded**.

## Next research steps

1. Completed on 2026-07-02: add deployed-proxy metadata verification to the platform
   using read-only RPC manifests rather than ad hoc research commands.
2. Investigate retryable refund receiver flows specifically:
   - excess fee refund address
   - call value refund address
   - resend / expired retryable recovery
3. Continue with Nitro using either a fixed Slither invocation or targeted Foundry/Hardhat
   harnesses, since Slither produced no JSON for Nitro in this run.
4. Before promoting any future candidate, search both public issue trackers and bundled
   audit PDFs for exact source-path/root-cause matches.

## 2026-07-02 scope expansion notes

### Live scope inventory beyond the bridge pilot

A fresh live scope parse still observed 181 Solidity asset URLs. The bridge/gateway
pilot profile covers the 43 scoped `OffchainLabs/token-bridge-contracts` paths and the
bridge-focused Nitro files, but the live program also includes Nitro rollup, challenge,
assertion staking pool, governance, and fund-distribution contracts.

Two live scope URLs were not present in the current shallow `main` checkouts used for
manual review:

- `OffchainLabs/nitro-contracts/src/rollup/Node.sol`
- `ArbitrumFoundation/governance/src/UpgradeExecutor.sol`

Current platform implication: source acquisition should eventually persist the full
observed asset URL list, not only digests, so missing scoped files are easier to audit.

2026-07-02 follow-up: governance and fund-distribution paths were promoted into the
committed analysis profile where the current upstream `main` source contains the scoped file.
`ArbitrumFoundation/governance/src/UpgradeExecutor.sol` remains deliberately outside the
configured fetch profile because the fail-closed source fetcher confirmed it is not present in
the current `ArbitrumFoundation/governance` `main` commit. Treat it as a source/scope inventory
mismatch for manual tracking, not as a vulnerability signal.

2026-07-02 follow-up: Nitro rollup, challenge, assertion-staking-pool, OSP, state,
node-interface, and precompile paths that exist in the current upstream checkout were promoted
into the committed analysis profile. Current coverage from the live attestation:

- observed smart-contract asset rows: 181
- GitHub blob assets: 170
- configured exact source matches: 168
- intentionally unconfigured GitHub gaps:
  - `OffchainLabs/nitro-contracts/src/rollup/Node.sol`
  - `ArbitrumFoundation/governance/src/UpgradeExecutor.sol`

Expanded source fetch passed with 168 selected files:

- `OffchainLabs/token-bridge-contracts`: 43 files at `0746a71321cd`
- `OffchainLabs/nitro-contracts`: 94 files at `674873332025`
- `ArbitrumFoundation/governance`: 29 files at `ae6cf85b88e8`
- `OffchainLabs/fund-distribution-contracts`: 2 files at `6f2eed33e999`

Detector and Semgrep calibration reduced the expanded Semgrep/internal review queue from 10 to
5 findings by suppressing:

- Nitro `RollupAdminLogic` admin-only loops routed through `AdminFallbackProxy`;
- internal or read-only initializer-like helpers;
- `RollupProxy.initializeProxy`, which only initializes when admin, primary implementation, and
  secondary implementation slots are all empty.

Latest expanded Semgrep/internal run:

`artifacts/runs/arbitrum-20260702T123217535994Z-09cde4fe`

Latest expanded full safe run:

`artifacts/runs/arbitrum-20260702T123722341523Z-09cde4fe`

- Foundry completed for buildable upstream profiles and returned structured failures for profiles
  with unresolved upstream dependency/build state.
- Slither returned structured timeout/failure results rather than aborting the pipeline.
- Semgrep completed with the calibrated local rules.
- Optional tools remained honest structured skips when not installed.
- Final review queue remained 5 findings.

Fresh live scope re-check:

`artifacts/scope/arbitrum/20260702T125452Z.json`

- Scope gate passed.
- Scope hash remained
  `e22d5a917fa11afcd863cc070a994a640856bf66d82245c97c884d08f542d6ce`.

Remaining review-only findings:

- `SecurityCouncilMemberSyncAction.perform` public array loop - already locally modeled and
  rejected as a direct-call owner replacement path.
- `L2GatewayRouter.setGateway` and `L2CustomGateway.registerTokenFromL1` counterpart-gated array
  loops - still low-priority liveness review only.
- `L1ERC20Gateway.callStatic` optional metadata revert lock - technically reproduced but public
  duplicate.
- `EdgeChallengeManager.multiUpdateTimeCacheByChildren` public timer-cache batching loop - manually
  reviewed below and not promoted.

### Rejected / public: BOLD staking pool excess-withdrawal loss shift

Status: **technically reproduced locally, but not promoted as a new bounty candidate**.

Relevant scoped paths:

- `OffchainLabs/nitro-contracts/src/assertionStakingPool/AbsBoldStakingPool.sol`
- `OffchainLabs/nitro-contracts/src/assertionStakingPool/AssertionStakingPool.sol`
- `OffchainLabs/nitro-contracts/src/assertionStakingPool/EdgeStakingPool.sol`
- `OffchainLabs/nitro-contracts/src/challengeV2/EdgeChallengeManager.sol`

Observation:

`AbsBoldStakingPool` keeps per-depositor accounting while the actual required stake is
sent out as a pool-level token balance. Upstream tests intentionally allow an excess
depositor to withdraw available pool balance after a protocol move has already consumed
the required stake. If that required stake is later treated as lost, the excess withdrawer
has recovered while the required-stake contributors remain unpaid.

Local proof:

- Persisted note and reference test:
  `pocs/arbitrum/bold-staking-pool-loss-shift/`
- Executed cache test:
  `test/foundry/researchAbsBoldStakingPoolLossShift.t.sol`
- Command:
  `FOUNDRY_PROFILE=test forge test --root .scbounty/cache/sources/arbitrum/OffchainLabs-nitro-contracts --force --match-contract ResearchAbsBoldStakingPoolLossShiftTest -vv`
- Result:
  `1 passed`

Rejection / duplicate risk:

- The upstream `AbsBoldStakingPool.t.sol::testPartialWithdraw` already encodes early
  excess withdrawal after a protocol move as intended behavior.
- Code4rena validation issue `#64` publicly discusses `AbsBoldStakingPool.withdrawFromPool`.
- Code4rena findings issue `#49` publicly discusses `EdgeChallengeManager` stake token /
  stake amount changes causing user/pool fund loss and mentions `withdrawFromPool`
  failure modes.

Current decision: **do not submit**. Keep as a regression/research note unless a separate,
non-public path is proven where an untrusted actor can force another participant into this
loss state without consent.

### Rejected / expected: DVP quorum delegation estimate edge cases

Status: **reviewed, not promoted as a bounty candidate**.

Relevant scoped paths:

- `ArbitrumFoundation/governance/src/L2ArbitrumToken.sol`
- `ArbitrumFoundation/governance/src/L2ArbitrumGovernor.sol`

Observation:

`L2ArbitrumToken.getTotalDelegationAt` is explicitly documented as an initially estimated
total-delegation history. `L2ArbitrumGovernor.getPastTotalDelegatedVotes` also documents
the possible `excluded > totalDvp` case and clamps that result to zero. The actual quorum
calculation then clamps the DVP-derived quorum between checkpointed minimum and maximum
quorum values.

Manual validation:

- `L2ArbitrumGovernor.t.sol::testPastCirculatingSupplyMint` checks that minting affects
  circulating supply but not the DVP quorum calculation.
- `L2ArbitrumGovernor.t.sol` also checks minimum/maximum quorum clamp behavior around the
  DVP start block.

Current decision: **do not submit**. The reviewed behavior is both documented in source and
covered by upstream tests; no untrusted path was found to lower quorum below the configured
minimum or bypass the proposal/voting snapshot model.

### Rejected / expected: BOLD edge timer and refund public entrypoints

Status: **reviewed, not promoted as a bounty candidate**.

Relevant scoped paths:

- `OffchainLabs/nitro-contracts/src/challengeV2/EdgeChallengeManager.sol`
- `OffchainLabs/nitro-contracts/src/challengeV2/libraries/EdgeChallengeManagerLib.sol`
- `OffchainLabs/nitro-contracts/src/challengeV2/libraries/ChallengeEdgeLib.sol`
- `OffchainLabs/nitro-contracts/src/assertionStakingPool/EdgeStakingPool.sol`

Observation:

`EdgeChallengeManager.refundStake` is public, but the refunded edge must first pass
`ChallengeEdgeLib.setRefunded`, which requires a confirmed layer-zero edge and rejects
double refunds. Edge confirmation by time uses the stored edge graph and confirmed-rival
tracking. One-step proof confirmation is restricted to length-one `SmallStep` edges and
checks committed before/after state roots around the one-step proof output.

Timer-cache update functions are also public, but the inherited timer values are derived
from child links or from a checked claim edge. The claim path verifies `claimId`, requires
the claiming edge origin to match the claimed edge mutual id, and requires the expected
next edge level.

Manual validation:

- Upstream `EdgeChallengeManager.t.sol` includes confirmation, timer-cache, excess-stake,
  and refund tests.
- Upstream `EdgeChallengeManagerLib.t.sol` includes direct library tests around first-rival
  tracking, time-unrivaled totals, cache sufficiency, and claim-based cache inheritance.

Current decision: **do not submit**. No path was found where an untrusted caller can inflate
timer cache through an unrelated edge, confirm a wrong rival while bypassing proof/link
checks, or refund stake before the edge reaches confirmed layer-zero status.

2026-07-02 follow-up: the expanded detector run specifically flagged
`EdgeChallengeManager.multiUpdateTimeCacheByChildren(bytes32[],uint256)` because it loops over a
caller-supplied edge list. Manual review did not find an exploit path:

- the batching helper first checks that the last edge's current timer cache is still below the
  requested maximum;
- each per-edge update derives the new cache only from `timeUnrivaledTotal`, i.e. the edge's own
  time-unrivaled plus the minimum of its stored lower/upper child timer caches;
- `confirmEdgeByTime` recomputes the total inherited time, checks the challenge-period threshold,
  requires the edge to be pending, and records a single confirmed rival for the mutual id;
- malformed or overlong arrays only affect the caller's own transaction gas and revert without
  persistent partial state if execution runs out of gas.

Current decision remains **do not submit**. Keep the signal as a public batching/liveness review
case, not as a validated bug.

### Rejected / expected: SecurityCouncilMemberSyncAction direct-call concern

Status: **locally modeled, not promoted as a bounty candidate**.

Relevant scoped path:

- `ArbitrumFoundation/governance/src/security-council-mgmt/SecurityCouncilMemberSyncAction.sol`

Observation:

`SecurityCouncilMemberSyncAction.perform(address,address[],uint256)` is an external function that
eventually calls a Gnosis Safe through `execTransactionFromModule`. This initially looked like a
possible direct-call owner replacement path because `perform` itself has no caller modifier.

Manual validation:

- Upstream unit tests deploy the Safe with `UpgradeExecutor` as the enabled module, not the action
  contract.
- The security-council deployment script also passes the configured executor as the Safe module.
- `SecurityCouncilMemberSyncAction` is documented as an action expected to be delegatecalled by an
  Upgrade Executor.
- `KeyValueStore` stores by `msg.sender`, and upstream tests assert nonce state under the
  `UpgradeExecutor` address after delegatecall execution.
- The local model at
  `pocs/arbitrum/security-council-sync-action-direct-call` confirms the intended split:
  executor delegatecall can update owners, while a direct call to the action fails because the Safe
  sees the action contract, not the enabled executor module.

Local validation:

- `forge test --root pocs/arbitrum/security-council-sync-action-direct-call -q`

Current decision: **do not submit**. Keep this as a regression note and re-check deployed Safe
module lists if read-only RPC metadata becomes available. If a live Safe were found with the action
contract itself enabled as a module, the conclusion would need to be revisited.

### Rejected / expected: RewardDistributor public distribution loop

Status: **reviewed, not promoted as a bounty candidate**.

Relevant scoped path:

- `OffchainLabs/fund-distribution-contracts/src/RewardDistributor.sol`

Observation:

`distributeRewards(address[],uint256[])` is public and loops over the supplied recipient array.
However, the supplied arrays must hash to the currently committed recipient and weight hashes.
The committed recipient set is only updated through `setRecipients`, which enforces
`MAX_RECIPIENTS = 64`, equal array lengths, and total weight equal to basis points. Arbitrary
long arrays should fail before the payout loop because their hashes do not match the committed
group.

Current decision: **do not submit**. Keep as a bounded public-maintenance function, not an
untrusted gas-griefing path.

### Reviewed / degraded build: fund-distribution reward routers

Status: **manual review completed, local upstream Foundry suite degraded due cache dependency
resolution**.

Relevant scoped paths:

- `OffchainLabs/fund-distribution-contracts/src/RewardDistributor.sol`
- `OffchainLabs/fund-distribution-contracts/src/FeeRouter/ParentToChildRewardRouter.sol`
- `OffchainLabs/fund-distribution-contracts/src/FeeRouter/ChildToParentRewardRouter.sol`
- `OffchainLabs/fund-distribution-contracts/src/FeeRouter/ArbChildToParentRewardRouter.sol`
- `OffchainLabs/fund-distribution-contracts/src/FeeRouter/OpChildToParentRewardRouter.sol`

Observation:

`RewardDistributor.distributeRewards` is intentionally public, but callers must supply the
currently committed recipient and weight arrays; mismatched hashes are rejected. Failed
native recipient sends are redirected to the owner, and ERC-20 distribution uses SafeERC20
with an explicit normal-token assumption.

The parent-to-child router sends all escrowed native funds plus the caller-supplied retryable
fee value to `unsafeCreateRetryableTicket`. It explicitly validates `msg.value ==
maxSubmissionCost + gasLimit * maxFeePerGas`, enforces minimum gas settings, aliases
contract fee-refund senders, and sets call-value refund to the intended child-chain
destination. Token routing uses the current full token balance, approves the gateway, and
routes to the fixed destination.

Local validation:

- Manual source review found no untrusted path to redirect destination funds, bypass interval
  throttling, or claim distribution with a forged recipient/weight set.
- Upstream unit tests cover recipient hash checks, owner-only recipient updates, fallback-to-owner
  native sends, interval throttling, and exact parent-to-child native retryable fee value.
- Attempted local `forge test` in the ignored cache degraded because the shallow checkout lacked
  OpenZeppelin/nitro remappings at first; a cache-only dependency attempt resolved OpenZeppelin
  but the `@arbitrum/nitro-contracts` v1.3.0 checkout hit an upstream submodule conflict around
  precompile files. This was not promoted as a platform failure because it occurred outside the
  committed source tree and did not affect the main project tests.

Current decision: **do not submit**. The reviewed public-call surfaces are intentional and
covered by existing validation; no unauthorized withdrawal, redirect, or accounting-bypass path
was found in the scoped source.

### Reviewed / not promoted: expanded Nitro public surface sweep

Status: **manual review completed for this pass; no validated bug candidate yet**.

This pass enumerated public/external mutating functions in the configured Nitro scope only. The
cache contains additional imported files such as `DeployHelper.sol`, `ValidatorWallet.sol`, and
`BOLDUpgradeAction.sol`, but those files are not currently direct live-scope/profile entries.
They were considered only where reachable through a scoped entrypoint.

Scoped surfaces reviewed:

- `src/rollup/RollupCreator.sol`
- `src/rollup/BridgeCreator.sol`
- `src/rollup/ValidatorWalletCreator.sol`
- `src/rollup/RollupUserLogic.sol`
- `src/challengeV2/EdgeChallengeManager.sol`
- `src/assertionStakingPool/*`
- scoped precompile ABI files

#### `BridgeCreator.createBridge`

`BridgeCreator.createBridge(...)` is external and permissionless. Manual review did not find a
shared-state or shared-funds exploit: it deploys fresh proxy instances using a salt derived from
`msg.data` and `msg.sender`, initializes those fresh contracts, and returns the created frame.
Direct callers can create their own bridge frames, but do not gain control over an existing
rollup's bridge contracts.

Current decision: **do not submit**. Treat it as a public factory surface, not an authorization
bypass.

#### `RollupCreator.createRollup`

`RollupCreator.createRollup(...)` is also public. A same-parameter front-run would create the same
rollup address, but the resulting `UpgradeExecutor` executor/owner is still derived from the
supplied `deployParams.config.owner`, not from the front-runner. Different owner/config values
change the CREATE2 salt and therefore the address.

The ETH factory-deployment path refunds `address(this).balance` to `msg.sender` after funding the
deterministic L2 factory retryables. This can sweep ambient ETH accidentally or forcibly sent to
`RollupCreator`, but no normal reviewed path was found where another user's escrowed or committed
funds become ambient creator balance. The custom-fee-token path intentionally prefunds the Inbox
and then relies on the ERC20 Inbox prefund behavior already reviewed above.

Current decision: **do not submit**. Keep as a factory/refund hardening note only; no concrete
program impact was proven.

#### `ValidatorWalletCreator.createWallet`

`ValidatorWalletCreator.createWallet(...)` deploys a new wallet proxy for `msg.sender`, sets the
caller as both executor and owner, and transfers the proxy admin ownership to that caller. The
created wallet can make arbitrary calls only under its own owner/executor/destination allowlist
model.

Current decision: **do not submit**. This is a self-owned wallet factory, not a cross-user or
protocol asset-control bypass in the scoped source.

#### `RollupUserLogic.fastConfirmNewAssertion`

`fastConfirmNewAssertion(...)` is intentionally powerful. The source explicitly says the protocol
trusts `anyTrustFastConfirmer` not to call it multiple times on the same predecessor because that
would break loser-stake accounting assumptions. Manual review found this is gated to exactly
`msg.sender == anyTrustFastConfirmer`; `RollupCreator` test/default configs set
`anyTrustFastConfirmer` to `address(0)` unless an AnyTrust deployment explicitly configures one.

Current decision: **do not submit** without deployed metadata proving a non-zero fast confirmer
whose own authorization/threshold logic is weak. If read-only deployment metadata later discovers
a live non-zero `anyTrustFastConfirmer`, review that contract as a separate high-priority target.

#### Scoped precompile ABI files

The scoped precompile Solidity files primarily describe ArbOS precompile ABIs and documented
access-control expectations. Examples include `ArbOwner` owner-only methods, `ArbDebug` debug-mode
methods, `ArbRetryableTx` retryable management, and `ArbSys` L2-to-L1 send helpers. These files
are not full ArbOS implementation source, so ABI-level public functions alone are insufficient
evidence for an exploit claim.

Current decision: **do not submit** from ABI shape alone. Future work should map any precompile
concern to actual ArbOS implementation semantics or read-only deployed behavior before promotion.

### Reviewed / not promoted: governance and Security Council election surface sweep

Status: **manual review completed for this pass; no validated bug candidate yet**.

Relevant scoped paths:

- `ArbitrumFoundation/governance/src/L2ArbitrumGovernor.sol`
- `ArbitrumFoundation/governance/src/L1ArbitrumTimelock.sol`
- `ArbitrumFoundation/governance/src/ArbitrumTimelock.sol`
- `ArbitrumFoundation/governance/src/security-council-mgmt/SecurityCouncilManager.sol`
- `ArbitrumFoundation/governance/src/security-council-mgmt/governors/SecurityCouncilNomineeElectionGovernor.sol`
- `ArbitrumFoundation/governance/src/security-council-mgmt/governors/SecurityCouncilMemberElectionGovernor.sol`
- `ArbitrumFoundation/governance/src/security-council-mgmt/governors/SecurityCouncilMemberRemovalGovernor.sol`
- `ArbitrumFoundation/governance/src/security-council-mgmt/governors/modules/*ElectionGovernor*`

#### Security Council nominee/member election flow

The nominee phase requires contenders to sign an EIP-712 `AddContenderMessage(uint256 proposalId)`
before a relayer can register them. Nominee voting lets a voter split snapshot voting power across
contenders, and only the exact amount required to reach the nomination threshold is consumed when a
candidate crosses the threshold. The member-election phase then lets voters split voting power
across compliant nominees, with weights decreasing after `fullWeightDuration`.

Reviewed candidate: member election has zero quorum and `selectTopNominees()` uses packed
`weight,index` ordering as a deterministic tie-breaker. In a no-vote or equal-vote member election,
nominee ordering can decide winners. This is not a fresh submission candidate in this pass:

- the behavior is already covered in the repository's public Code4rena report as `N-02` / tie
  handling documentation;
- `topNominees()` gas/stuck concerns are also publicly covered as `N-05`;
- the repository tests explicitly assert the packed sorting behavior;
- no new path was found for an untrusted caller to become a compliant nominee without either
  crossing the nominee threshold or being included by the trusted nominee vetter.

Current decision: **do not submit**. Keep as a known election-design/tie-break note, not a new
bounty candidate.

#### Security Council manager and removal governor

`SecurityCouncilManager` mutating operations are role-gated (`COHORT_REPLACER`,
`MEMBER_ADDER`, `MEMBER_REPLACER`, `MEMBER_ROTATOR`, `MEMBER_REMOVER`, and admin). The removal
governor restricts proposals to exactly `SecurityCouncilManager.removeMember(address)` with one
target, zero value, expected calldata length, and an existing member.

Previously disclosed governance-design concerns remain visible in source/audit history, including
security council replacement race conditions and the ability for authorized council paths to add a
previously removed member. These are public Code4rena findings/design acknowledgements rather than
new code-level exploit candidates.

Current decision: **do not submit**. No fresh untrusted role bypass or manager state-corruption
path was found in this pass.

#### Governor relay, quorum, and timelock routing

`L2ArbitrumGovernor.relay` and the Security Council governor `relay` functions are owner-only and
are part of the round-trip governance design. `L2ArbitrumGovernor.cancel` is limited to the stored
proposer and only while pending. DVP quorum is clamped between checkpointed minimum/maximum values
after `postUpgradeInit`, while pre-DVP blocks use circulating-supply quorum.

`L1ArbitrumTimelock` scheduling is limited to messages proven to originate from the L2 timelock via
the governance-chain bridge/outbox sender. The retryable-ticket branch can leave tiny surplus ETH
or route fee refunds according to the scheduled payload/caller, but this behavior is documented in
the code/audit notes and no unauthorized scheduling path was found.

Current decision: **do not submit**. Treat as privileged governance/timelock design surface unless
deployed roles or scheduled payloads show a concrete mismatch.

### Reviewed / not promoted: L1 ARB token Nova registration public entrypoint

Status: **source review plus read-only live metadata check completed**.

Relevant scoped paths:

- `ArbitrumFoundation/governance/src/L1ArbitrumToken.sol`
- `OffchainLabs/token-bridge-contracts/contracts/tokenbridge/ethereum/gateway/L1CustomGateway.sol`
- `OffchainLabs/token-bridge-contracts/contracts/tokenbridge/ethereum/gateway/L1GatewayRouter.sol`
- `OffchainLabs/token-bridge-contracts/contracts/tokenbridge/arbitrum/gateway/L2CustomGateway.sol`

Observation:

`L1ArbitrumToken.registerTokenOnL2(...)` is public and forwards caller-supplied Nova token
registration parameters to the fixed Nova custom gateway and router. A first-call race would matter
if the L1 token had no custom-gateway mapping yet, because the L1 gateway locks the initial
`l1ToL2Token[msg.sender]` address and rejects later updates to a different L2 token address.

Bridge-side review found the important guard:

- `L1CustomGateway._registerTokenToL2` checks `isArbitrumEnabled()` on `msg.sender`;
- if `l1ToL2Token[msg.sender]` is already non-zero, a different `_l2Address` reverts with
  `NO_UPDATE_TO_DIFFERENT_ADDR`;
- `L1GatewayRouter._setGatewayWithCreditBack` similarly prevents changing a non-default gateway to
  a different gateway;
- L2 registration is only accepted by `L2CustomGateway.registerTokenFromL1` from the aliased L1
  counterpart gateway.

Read-only live check on 2026-07-02 using public RPC:

- L1 ARB token `0xB50721BCf8d664c30412Cfbc6cf7a15145234ad1`
- `novaGateway()` = `0x23122da8C581AA7E0d07A36Ff1f16F799650232f`
- `novaRouter()` = `0xC840838Bc438d73C16c2f8b22D2Ce3669963cD48`
- `arbOneGateway()` = `0xbbcE8aA77782F13D4202a230d978F361B011dB27`
- Nova gateway `l1ToL2Token(L1_ARB)` = `0xf823C3cD3CeBE0a1fA952ba88Dc9EEf8e0Bf46AD`
- Nova router `l1TokenToGateway(L1_ARB)` = `0x23122da8C581AA7E0d07A36Ff1f16F799650232f`
- Arb One reverse gateway `l1ToL2Token(L1_ARB)` = `0x912CE59144191C1204E64559FE8253a0e49E6548`
- Nova token `l1Address()` = `0xB50721BCf8d664c30412Cfbc6cf7a15145234ad1`

The live mappings match the repository's `files/mainnet/deployedContracts.json` and verifier
expectations. The remaining issue class is a deployment-time/ambient-ETH hardening note, not a
current exploit path: if ETH is accidentally left on the L1 token contract, a public caller could
attempt same-address re-registration with their own retryable refund receiver, but this would only
move accidental/ambient ETH and does not modify the live token mapping.

Current decision: **do not submit**. Registration mapping is already set correctly on live
contracts; no current token-hijack path was proven.

### Reviewed / not promoted: vesting wallet and TokenDistributor privileged flows

Status: **manual review completed for this pass**.

`TokenDistributor.claim`, `claimAndDelegate`, and `sweep` were rechecked. `claimAndDelegate` reverts
the claim if delegation fails, avoiding a partial claim/delegate stuck state. `sweep` is limited to
after `claimPeriodEnd` and sends leftovers to the configured sweep receiver before selfdestructing.
Recipient updates and sweep receiver changes are owner-only.

`ArbitrumFoundationVestingWallet` lets the current beneficiary or DAO owner set the beneficiary,
and only the beneficiary can release vested ETH/tokens. DAO-only migration can move all wallet
balances to a contract destination. The internal `_setBeneficiary` does not reject zero addresses,
but the callable path is limited to the current beneficiary or owner; this is a self-brick/DAO-action
risk rather than an untrusted theft path.

Current decision: **do not submit**. No unauthorized claim, release, sweep, or migration path was
found.

### Reviewed / not promoted: Classic outboxes still authorized by the current bridge

Status: **source review plus block-pinned read-only live-state verification completed**.

The current Arbitrum One bridge still authorizes three outboxes:

- current outbox `0x0B9857ae2D4A3DBe74ffE1d7DF045bb7F96E4840`;
- Classic outbox `0x667e23ABd27E623c11d4CC00ca3EC4d0bD63337a`;
- Classic outbox `0x760723CD2e632826c38Fef8CD438A4CC7E7E1A40`.

The two Classic outboxes both point to the old rollup
`0xC12BA48c781F6e392B49Db2E25Cd0c28cD77531A` while executing withdrawals through
the current bridge `0x8315177aB297bA92A06054cE80a67Ed4DBd7ed3a`. This initially looked
dangerous: if an untrusted caller could make the old rollup publish a new arbitrary root, an
allowed Classic outbox could call the current bridge with forged withdrawals.

Read-only state and verified source close that path:

- the old rollup is paused and in Nitro shutdown mode;
- `shutdownForNitroBlock()` is `15447186`;
- `latestConfirmed()` and `latestNodeCreated()` are both `3591`;
- `firstUnresolvedNode()` is `3592`, and `getNode(3592)` is the zero address;
- `stakerCount()` is zero;
- its admin facet is `0x3CcB27FD59398a015a1eb465582A934fbF318214`;
- its user facet is `0xDBE5c009095169D3de4a8D1C70E319fE647A3DBf`.

The Classic user facet permits `confirmNextNode` during Nitro shutdown, but the function requires
an unresolved node and a non-zero staker count. New stakes, movement to an existing unresolved
node, and `stakeOnNewNode` remain protected by `whenNotPaused`. The admin facet has
`forceConfirmNode` while paused, but the proxy dispatches the admin facet only when `msg.sender`
is the rollup owner; all other callers reach the user facet. Both Classic outbox implementations
also require `msg.sender == rollup` before processing outgoing messages.

Arbitrum's contract-address documentation explicitly lists the two addresses as Classic outboxes
for migrated networks, consistent with retaining them so historical Classic withdrawals remain
executable:

- `https://docs.arbitrum.io/arbitrum-essentials/reference/contract-addresses`
- `https://github.com/OffchainLabs/arbitrum-classic/blob/master/packages/arb-bridge-eth/contracts/rollup/facets/RollupAdmin.sol`
- `https://github.com/OffchainLabs/arbitrum-classic/blob/master/packages/arb-bridge-eth/contracts/rollup/facets/RollupUser.sol`

Current decision: **do not submit**. The retained authorization is an intentional migration
compatibility path, and no untrusted route to create or confirm another Classic send root was
found.

### Platform improvement: block-pinned deployed metadata manifests

The platform now provides:

```text
scbounty source metadata arbitrum
```

The command re-runs the live scope gate, verifies RPC chain IDs, pins one block per configured
network, and records deployed bytecode hashes plus EIP-1967 implementation, admin, and beacon
metadata. Missing RPC endpoints produce structured skips. The RPC client exposes only
`eth_chainId`, `eth_blockNumber`, `eth_getCode`, `eth_getStorageAt`, and `eth_call`; it has no
transaction, signing, account, or broadcast method.

The first complete live snapshot recorded:

- scope hash `e22d5a917fa11afcd863cc070a994a640856bf66d82245c97c884d08f542d6ce`;
- Ethereum block `25445242`;
- Arbitrum One block `479635727`;
- 19 completed contract observations;
- zero skipped and zero failed observations;
- artifact `artifacts/deployed/arbitrum/20260702T135202Z.json`.

The manifest contains no HTTP URL. During the first live run, the generic HTTP client's INFO
logger exposed the endpoint URL in terminal output. HTTP request logging is now disabled even in
verbose mode, with a regression test ensuring token-bearing RPC URLs cannot be printed by that
logger.
