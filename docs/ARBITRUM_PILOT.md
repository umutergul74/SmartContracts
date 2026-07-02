# Arbitrum pilot

The pilot treats Arbitrum as L1/L2 smart-contract infrastructure, not as a token-price or trading
target.

## Authorization sources

- Program: <https://immunefi.com/bug-bounty/arbitrum/>
- Scope: <https://immunefi.com/bug-bounty/arbitrum/scope/>
- Information: <https://immunefi.com/bug-bounty/arbitrum/information/>

The reviewed 2026-06-30 snapshot contains a fingerprint of 181 asset rows and 13 impact rows. It is
not permanent permission. Every real analysis performs a fresh comparison.

## Current analysis profile

The current source selection emphasizes:

- L1/L2 gateways and routers;
- bridge mint/burn authorization;
- counterpart and address-alias validation;
- retryable/finalization assumptions;
- escrow, mint, burn, WETH, and token-behavior invariants.
- DAO/governance execution paths and token distribution contracts;
- scoped reward-distribution contracts.

Reviewed Nitro rollup, challenge, staking, precompile, state, node-interface, and OSP paths are now
included in the exact source profile. A live-scope path is not added when it is absent from the
current upstream `main` checkout; that case remains an inventory mismatch for manual review.

The deployed profile also tracks reviewed scalar state such as the Arbitrum One rollup's
`anyTrustFastConfirmer()` value through a block-pinned fixed `eth_call`. State drift is a
manual-review signal, not an automatically validated finding.

## Updating the snapshot

If the scope gate reports a mismatch:

1. stop real-target analysis;
2. review the full live asset, impact, and prohibited-activity data;
3. map additions/removals to repositories and deployed addresses;
4. update the human snapshot and machine fingerprint together;
5. add or update parser regression fixtures;
6. obtain review before committing the new snapshot.
