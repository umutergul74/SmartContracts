# Arbitrum target

This directory contains reviewed seed metadata for the Arbitrum Immunefi program. The seed is
never treated as permanently current. Run `scbounty scope check arbitrum` immediately before
every real-target analysis.

The current analysis profile covers bridge, gateway, cross-domain messaging, accounting,
governance, and fund-distribution paths that map to the live scope and exist in the pinned source
checkout. Compiling a repository for dependency resolution does not place every file in bounty
scope; findings are admitted only when their source path maps to the live scope.

Some live-scope inventory remains outside the fetch profile when the scoped path is absent from the
current upstream `main` checkout or belongs to the next Nitro rollup/challenge/staking vertical.
