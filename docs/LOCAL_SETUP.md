# Local setup

## Required

- Git
- Python 3.11–3.13; Python 3.12 is canonical
- `uv` preferred, `pip` supported

## Recommended core analyzers

```powershell
# Windows PowerShell
uv tool install slither-analyzer
uv tool install semgrep

# Install the stable Foundry binaries using the official Foundry instructions,
# then restart the terminal and confirm:
forge --version
cast --version
anvil --version
```

The same `uv tool install` commands work on Linux and macOS. Optional adapters discover Aderyn,
Mythril, Echidna, Medusa, Halmos, and Solhint when installed.

## Project environment

```powershell
uv python install 3.12
uv venv --python 3.12
.venv\Scripts\Activate.ps1
uv sync --extra dev
scbounty env doctor
```

Pip fallback:

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
```

## Optional read-only RPC

Copy `.env.example` to `.env` and add only read-only endpoint URLs. `.env` is ignored. No private
key, mnemonic, keystore, wallet password, or funded account is required or supported.

Without RPC URLs, scope checking, source acquisition, static analysis, local fixtures, and report
generation remain available. Deployed metadata and local-fork tests are skipped.

Capture a safe deployed snapshot after configuring the desired endpoints:

```powershell
scbounty source metadata arbitrum
```

The command re-verifies live scope, checks each RPC chain ID, pins a block number, and records
bytecode and EIP-1967 proxy fingerprints. It exposes no transaction, signing, wallet, or broadcast
method and does not store the RPC URL.

## Quality checks

```powershell
ruff format --check .
ruff check .
mypy src
pytest --cov=scbounty --cov-report=term-missing
semgrep scan --validate --config semgrep/solidity
scbounty test arbitrum --kind invariant --local-only
```
