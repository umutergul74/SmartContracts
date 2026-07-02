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

Nitro rollup, challenge, staking, precompile, and OSP surfaces remain visible in the complete scope
fingerprint. They are tracked as explicit coverage gaps until they are promoted into a reviewed
vertical slice. A live-scope path is not added to the fetch profile when it is absent from the
current upstream `main` source checkout; that case is kept as an inventory mismatch for manual
review.

## Updating the snapshot

If the scope gate reports a mismatch:

1. stop real-target analysis;
2. review the full live asset, impact, and prohibited-activity data;
3. map additions/removals to repositories and deployed addresses;
4. update the human snapshot and machine fingerprint together;
5. add or update parser regression fixtures;
6. obtain review before committing the new snapshot.
