import json
from pathlib import Path

import httpx
import pytest

from scbounty.config.loader import load_target
from scbounty.harness.echidna_generator import generate_echidna_config
from scbounty.harness.foundry_generator import generate_foundry_harness
from scbounty.harness.medusa_generator import generate_medusa_config
from scbounty.source.deployed import DeployedMetadataCollector
from scbounty.source.github import github_blob_path
from scbounty.source.metadata import ContractMetadata, ReadOnlyRpcClient


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
        payload = json.loads(request.read())
        method = payload["method"]
        if method == "eth_blockNumber":
            result = "0x10"
        elif method == "eth_getCode":
            result = "0x6000"
        else:
            result = "0x" + "00" * 32
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": result})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        rpc = ReadOnlyRpcClient("https://example.test", client)
        metadata = rpc.contract_metadata("0x" + "11" * 20)
        with pytest.raises(ValueError, match="read-only allowlist"):
            rpc._call("eth_sendTransaction", [])  # noqa: SLF001

    assert len(metadata["bytecode_sha256"]) == 64
    assert metadata["bytecode_size"] == 2
    assert metadata["block_number"] == 16
    assert metadata["proxy_kind"] == "none"


def test_rpc_client_records_eip1967_implementation_at_pinned_block() -> None:
    implementation = "22" * 20
    requested_block_tags: list[str] = []

    def respond(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.read())
        method = payload["method"]
        params = payload["params"]
        if method == "eth_getCode":
            requested_block_tags.append(params[1])
            result = "0x60006000"
        elif method == "eth_getStorageAt" and "360894a1" in params[1]:
            requested_block_tags.append(params[2])
            result = "0x" + "00" * 12 + implementation
        else:
            result = "0x" + "00" * 32
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": result})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        metadata = ReadOnlyRpcClient("https://secret-token@example.test", client).contract_metadata(
            "0x" + "11" * 20,
            block_number=123,
        )

    assert metadata["proxy_kind"] == "eip1967"
    assert metadata["implementation_address"] == "0x" + implementation
    assert metadata["implementation_bytecode_size"] == 4
    assert set(requested_block_tags) == {"0x7b"}


def test_rpc_client_resolves_eip1967_beacon_implementation() -> None:
    beacon = "33" * 20
    implementation = "44" * 20

    def respond(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.read())
        method = payload["method"]
        params = payload["params"]
        if method == "eth_getStorageAt" and "a3f0ad74" in params[1]:
            result = "0x" + "00" * 12 + beacon
        elif method == "eth_call":
            assert params[0] == {
                "to": "0x" + beacon,
                "data": "0x5c60da1b",
            }
            result = "0x" + "00" * 12 + implementation
        elif method == "eth_getCode":
            result = "0x6000"
        else:
            result = "0x" + "00" * 32
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": 1, "result": result})

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        metadata = ReadOnlyRpcClient("https://example.test", client).contract_metadata(
            "0x" + "11" * 20,
            block_number=456,
        )

    assert metadata["proxy_kind"] == "eip1967_beacon"
    assert metadata["beacon_address"] == "0x" + beacon
    assert metadata["implementation_address"] == "0x" + implementation
    assert metadata["beacon_bytecode_size"] == 2
    assert metadata["implementation_bytecode_size"] == 2


def test_deployed_metadata_collector_skips_missing_rpc_without_exposing_values(
    tmp_path: Path,
) -> None:
    target = load_target("arbitrum")
    target.deployed_contracts = target.deployed_contracts[:1]
    output = tmp_path / "metadata.json"

    manifest = DeployedMetadataCollector().collect(
        target,
        environment={},
        output_path=output,
    )

    assert manifest.networks[0].status == "skipped"
    assert manifest.contracts[0].status == "skipped"
    assert target.networks["ethereum_l1"].rpc_env_var in output.read_text(encoding="utf-8")


def test_deployed_metadata_collector_pins_chain_and_redacts_rpc_url() -> None:
    target = load_target("arbitrum")
    target.deployed_contracts = target.deployed_contracts[:1]
    secret_rpc = "https://secret-token@example.test"

    class FakeRpc:
        def chain_id(self) -> int:
            return 1

        def block_number(self) -> int:
            return 123

        def contract_metadata(
            self,
            address: str,
            *,
            block_number: int | None = None,
        ) -> ContractMetadata:
            assert block_number == 123
            return {
                "address": address,
                "block_number": 123,
                "bytecode_size": 4,
                "bytecode_sha256": "a" * 64,
                "proxy_kind": "none",
                "implementation_address": None,
                "implementation_bytecode_size": None,
                "implementation_bytecode_sha256": None,
                "admin_address": None,
                "beacon_address": None,
                "beacon_bytecode_size": None,
                "beacon_bytecode_sha256": None,
            }

        def close(self) -> None:
            return None

    collector = DeployedMetadataCollector(client_factory=lambda _: FakeRpc())
    manifest = collector.collect(
        target,
        environment={"ETHEREUM_RPC_URL": secret_rpc},
    )

    rendered = manifest.model_dump_json()
    assert manifest.networks[0].observed_chain_id == 1
    assert manifest.networks[0].block_number == 123
    assert manifest.contracts[0].status == "completed"
    assert secret_rpc not in rendered
