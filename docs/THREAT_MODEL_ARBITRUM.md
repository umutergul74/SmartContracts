# Arbitrum bridge/gateway threat model

## Assets

- Canonical L1 escrow.
- L2 minted representation and burn accounting.
- Token-to-gateway and router-to-gateway mappings.
- Cross-domain messages, retryable tickets, and withdrawal state.
- WETH/native-token conversion.
- Upgrade and emergency authorities.

## Trust boundaries

- L1 caller versus authenticated L2 counterpart.
- L2 caller versus aliased L1 sender.
- Router versus direct gateway calls.
- Canonical versus custom gateways.
- Source repository versus deployed bytecode.
- Arbitrum One versus Nova configuration and data-availability assumptions.

## Core invariants

1. Outstanding representation must not exceed canonical escrow after accounting for in-flight
   messages.
2. Only the canonical counterpart may finalize a cross-domain transfer.
3. Only the authorized gateway may mint or burn bridge representation.
4. Token-to-gateway mapping changes require the intended governance/owner path.
5. A message cannot be finalized twice.
6. Failed or refunded retryables must not create supply or permanently orphan escrow.
7. WETH unwrap/wrap paths preserve value and destination identity.

## Failure modes

- direct theft or unbacked minting;
- permanent or upgrade-recoverable freezing;
- insolvency;
- fast-withdrawal damage;
- replay or duplicate finalization;
- unsafe refund receiver;
- non-standard ERC-20 accounting;
- network-wide DoS or unbounded finalization gas.

Low-impact style findings, documentation differences, ordinary gas optimization, privileged
behavior without an additional privilege escalation, and off-chain infrastructure are not initial
research priorities.

