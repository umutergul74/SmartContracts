from pathlib import Path

import httpx
import pytest

from scbounty.config.loader import load_target
from scbounty.config.models import ScopeSnapshot
from scbounty.config.scope_gate import (
    KNOWN_ARBITRUM_IMPACTS,
    ScopeGate,
    ScopeVerificationError,
)
from scbounty.utils.hashing import sha256_text
from scbounty.utils.serialization import write_model


def _configured_scope(tmp_path: Path) -> tuple[object, str]:
    target = load_target("arbitrum")
    target.target_id = "test"
    target.authorization.scope_url = "https://example.test/scope"
    target.scope_snapshot_file = "scope.json"
    assets = sorted(["https://github.com/example/repo/blob/main/A.sol"])
    impacts = sorted(f"{severity}|{title}" for severity, title in KNOWN_ARBITRUM_IMPACTS)
    markers = [
        "Any testing on mainnet or public testnet deployed code",
        "all testing should be done on local-forks",
        "Public disclosure of an unpatched vulnerability",
    ]
    body = "\n".join([*assets, *(title for _, title in KNOWN_ARBITRUM_IMPACTS), *markers])
    snapshot = ScopeSnapshot(
        target_id="test",
        captured_at_utc="2026-06-30T00:00:00Z",
        source_url="https://example.test/scope",
        program_last_updated="today",
        asset_count=1,
        asset_urls_sha256=sha256_text("\n".join(assets)),
        impact_count=13,
        impacts_sha256=sha256_text("\n".join(impacts)),
        seed_assets=["A.sol"],
        repositories=["https://github.com/example/repo"],
        prohibited_activity_markers=markers,
    )
    write_model(tmp_path / "targets" / "test" / "scope.json", snapshot)
    return target, body


def test_scope_gate_writes_attestation_for_exact_live_page(tmp_path: Path) -> None:
    target, body = _configured_scope(tmp_path)
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=body))
    output = tmp_path / "attestation.json"

    with httpx.Client(transport=transport) as client:
        attestation = ScopeGate(client).verify(
            target,  # type: ignore[arg-type]
            root=tmp_path,
            output_path=output,
        )

    assert attestation.diff.passed is True
    assert output.is_file()


def test_scope_gate_fails_closed_on_network_error(tmp_path: Path) -> None:
    target, _ = _configured_scope(tmp_path)

    def fail(request):
        raise httpx.ConnectError("offline", request=request)

    with httpx.Client(transport=httpx.MockTransport(fail)) as client:
        with pytest.raises(ScopeVerificationError, match="analysis is refused"):
            ScopeGate(client).verify(target, root=tmp_path)  # type: ignore[arg-type]
