import json
from pathlib import Path

import httpx
import pytest

from scbounty.config.loader import load_target
from scbounty.config.models import ReadOnlyCallConfig
from scbounty.harness.echidna_generator import generate_echidna_config
from scbounty.harness.foundry_generator import generate_foundry_harness
from scbounty.harness.medusa_generator import generate_medusa_config
from scbounty.source.deployed import (
    DeployedMetadataCollector,
    _decode_call_result,
    _normalized_expected_value,
)
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


def test_rpc_client_executes_fixed_read_only_call_at_pinned_block() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.read())
        assert payload["method"] == "eth_call"
        assert payload["params"] == [
            {"to": "0x" + "11" * 20, "data": "0x55840a58"},
            "0x7b",
        ]
        return httpx.Response(
            200,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "result": "0x" + "00" * 32,
            },
        )

    with httpx.Client(transport=httpx.MockTransport(respond)) as client:
        result = ReadOnlyRpcClient("https://example.test", client).read_only_call(
            "0x" + "11" * 20,
            "0x55840a58",
            block_number=123,
        )

    assert result == "0x" + "00" * 32


@pytest.mark.parametrize(
    ("result_type", "raw_result", "decoded"),
    [
        ("address", "0x" + "00" * 12 + "11" * 20, "0x" + "11" * 20),
        ("uint256", "0x2a", "42"),
        ("bool", "0x01", "true"),
        ("bool", "0x00", "false"),
        ("bytes32", "0xab", "0x" + "00" * 31 + "ab"),
        ("raw", "0xabc", "0x0abc"),
    ],
)
def test_fixed_read_only_call_decoding(
    result_type: str,
    raw_result: str,
    decoded: str,
) -> None:
    call = ReadOnlyCallConfig(
        name="test_call",
        calldata="0x12345678",
        result_type=result_type,
    )

    assert _decode_call_result(call, raw_result) == decoded


def test_fixed_read_only_call_rejects_malformed_results_and_expectations() -> None:
    bool_call = ReadOnlyCallConfig(
        name="bool_call",
        calldata="0x12345678",
        result_type="bool",
        expected_value="TRUE",
    )
    uint_call = ReadOnlyCallConfig(
        name="uint_call",
        calldata="0x12345678",
        result_type="uint256",
        expected_value="0x2a",
    )

    assert _normalized_expected_value(bool_call) == "true"
    assert _normalized_expected_value(uint_call) == "42"
    with pytest.raises(ValueError, match="zero or one"):
        _decode_call_result(bool_call, "0x02")
    with pytest.raises(ValueError, match="not hexadecimal"):
        _decode_call_result(bool_call, "0xzz")
    with pytest.raises(ValueError, match="must start with 0x"):
        _decode_call_result(bool_call, "00")


@pytest.mark.parametrize("calldata", ["12345678", "0x123", "0xzzzzzzzz", "0x12"])
def test_fixed_read_only_call_requires_safe_calldata(calldata: str) -> None:
    with pytest.raises(ValueError):
        ReadOnlyCallConfig(name="test_call", calldata=calldata)


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


def test_deployed_metadata_collector_records_expected_read_only_call() -> None:
    target = load_target("arbitrum")
    target.deployed_contracts = [
        contract for contract in target.deployed_contracts if contract.name == "arb_one_rollup"
    ]

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
                "proxy_kind": "eip1967",
                "implementation_address": "0x" + "22" * 20,
                "implementation_bytecode_size": 4,
                "implementation_bytecode_sha256": "b" * 64,
                "admin_address": None,
                "beacon_address": None,
                "beacon_bytecode_size": None,
                "beacon_bytecode_sha256": None,
            }

        def read_only_call(
            self,
            address: str,
            calldata: str,
            *,
            block_number: int | None = None,
        ) -> str:
            assert address == target.deployed_contracts[0].address
            assert calldata == "0x55840a58"
            assert block_number == 123
            return "0x" + "00" * 32

        def close(self) -> None:
            return None

    manifest = DeployedMetadataCollector(client_factory=lambda _: FakeRpc()).collect(
        target,
        environment={"ETHEREUM_RPC_URL": "https://example.test"},
    )

    observation = manifest.contracts[0].read_only_calls[0]
    assert observation.status == "completed"
    assert observation.decoded_value == "0x" + "00" * 20
    assert observation.matches_expected is True

    target.deployed_contracts[0].read_only_calls[0].expected_value = "0x" + "11" * 20
    mismatch = DeployedMetadataCollector(client_factory=lambda _: FakeRpc()).collect(
        target,
        environment={"ETHEREUM_RPC_URL": "https://example.test"},
    )
    mismatch_observation = mismatch.contracts[0].read_only_calls[0]
    assert mismatch.contracts[0].status == "completed"
    assert mismatch_observation.matches_expected is False
    assert "manual review required" in mismatch_observation.warnings[0]
