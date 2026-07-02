# BOLD staking pool excess-withdrawal loss-shift note

Status: **DRAFT / NOT A VALIDATED BOUNTY FINDING**

This note records a local-only review of `AbsBoldStakingPool` excess-withdrawal
semantics. It is not an Immunefi submission.

## Observation

`AbsBoldStakingPool` records per-depositor balances, but stake is sent to the rollup or
challenge manager as a single pool-level token balance. Upstream tests intentionally allow
an excess depositor to withdraw available pool balance after a protocol move has already
used the required stake.

If the protocol move later loses its stake, the excess depositor has recovered their
excess while the required-stake contributors remain unpaid. This is consistent with the
documented "excess stake can be withdrawn early" behavior, but it means pool shares are
not loss-socialized.

## Local reproduction shape

The local test model uses:

- `stakerA = 6 ether`
- `stakerB = 4 ether`
- `excessStaker = 1 ether`
- required stake = `10 ether`

After the pool sends the required stake out, `excessStaker` withdraws the remaining
`1 ether`. If the required stake is then treated as lost, `stakerA` and `stakerB` still
have accounting balances but the pool has no tokens left to pay them.

## Duplicate / rejection risk

This area is already public:

- Code4rena validation issue `#64` discusses `AbsBoldStakingPool.withdrawFromPool`.
- Code4rena findings issue `#49` discusses stake amount/token changes causing pool/user
  fund loss and mentions `withdrawFromPool` failures.

Current decision: **do not submit** unless a separate, non-public path is proven where an
untrusted actor can force another participant into this pool-risk state without consent.
