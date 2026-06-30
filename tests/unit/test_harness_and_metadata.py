from pathlib import Path

import httpx
import pytest

from scbounty.harness.echidna_generator import generate_echidna_config
from scbounty.harness.foundry_generator import generate_foundry_harness
from scbounty.harness.medusa_generator import generate_medusa_config
from scbounty.source.github import github_blob_path
from scbounty.source.metadata import ReadOnlyRpcClient


def test_harness_generators_write_only_to_requested_directory(tmp_path: Path) -> None:
    foundry = generate_foundry_harness("arbitrum", tmp_path / "foundry")
    echidna = generate_echidna_config("arbitrum", tmp_path / "echidna")
    medusa = generate_medusa_config("arbitrum", tmp_path / "medusa")

    assert "local-only" in foundry.read_text(encoding="utf-8")
    assert echidna.is_relative_to(tmp_path)
    assert medusa.is_relative_to(tmp_path)


def test_github_blob_path_parses_reviewed_source_url() -> None:
    parsed = github_blob_path(
        "https://github.com/OffchainLabs/nitro-contracts/blob/main/src/bridge/Bridge.sol"
    )

    assert parsed == ("OffchainLabs/nitro-contracts", "main", "src/bridge/Bridge.sol")
    assert github_blob_path("https://example.test/not-github") is None


def test_rpc_client_exposes_only_read_methods() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        method = request.read().decode()
        result = "0x6000" if "eth_getCode" in method else "0x" + "00" * 32
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": result})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        rpc = ReadOnlyRpcClient("https://example.test", client)
        metadata = rpc.contract_metadata("0x" + "11" * 20)
        with pytest.raises(ValueError, match="read-only allowlist"):
            rpc._call("eth_sendTransaction", [])  # noqa: SLF001

    assert len(metadata["bytecode_sha256"]) == 64
