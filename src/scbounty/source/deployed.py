from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol

from scbounty.config.models import (
    DeployedContractConfig,
    DeployedContractObservation,
    DeployedMetadataManifest,
    DeployedNetworkObservation,
    ReadOnlyCallConfig,
    ReadOnlyCallObservation,
    TargetConfig,
)
from scbounty.source.metadata import ContractMetadata, ReadOnlyRpcClient
from scbounty.utils.serialization import write_model


class RpcClient(Protocol):
    def chain_id(self) -> int: ...

    def block_number(self) -> int: ...

    def contract_metadata(
        self,
        address: str,
        *,
        block_number: int | None = None,
    ) -> ContractMetadata: ...

    def read_only_call(
        self,
        address: str,
        calldata: str,
        *,
        block_number: int | None = None,
    ) -> str: ...

    def close(self) -> None: ...


RpcClientFactory = Callable[[str], RpcClient]
UnavailableObservationStatus = Literal["skipped", "failed"]


def _safe_rpc_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: read-only RPC request failed; endpoint details redacted"


def _decode_call_result(call: ReadOnlyCallConfig, raw_result: str) -> str:
    if not raw_result.startswith("0x"):
        raise ValueError("RPC call result must start with 0x")
    payload = raw_result[2:]
    if len(payload) % 2:
        payload = f"0{payload}"
    try:
        raw = bytes.fromhex(payload)
    except ValueError as exc:
        raise ValueError("RPC call result is not hexadecimal") from exc

    if call.result_type == "raw":
        return f"0x{raw.hex()}"
    if len(raw) > 32:
        raise ValueError(f"{call.result_type} call result exceeds one ABI word")
    word = raw.rjust(32, b"\0")
    if call.result_type == "address":
        return f"0x{word[-20:].hex()}"
    if call.result_type == "uint256":
        return str(int.from_bytes(word, "big"))
    if call.result_type == "bool":
        value = int.from_bytes(word, "big")
        if value not in {0, 1}:
            raise ValueError("boolean call result must be zero or one")
        return "true" if value else "false"
    return f"0x{word.hex()}"


def _normalized_expected_value(call: ReadOnlyCallConfig) -> str | None:
    if call.expected_value is None:
        return None
    expected = call.expected_value.strip()
    if call.result_type in {"address", "bytes32", "raw"}:
        return expected.lower()
    if call.result_type == "bool":
        lowered = expected.lower()
        if lowered not in {"true", "false"}:
            raise ValueError("expected bool value must be true or false")
        return lowered
    return str(int(expected, 0))


def _unavailable_call_observations(
    contract: DeployedContractConfig,
    *,
    status: Literal["skipped", "failed"],
    warning: str,
) -> list[ReadOnlyCallObservation]:
    return [
        ReadOnlyCallObservation(
            name=call.name,
            calldata=call.calldata,
            result_type=call.result_type,
            status=status,
            expected_value=call.expected_value,
            warnings=[warning],
        )
        for call in contract.read_only_calls
    ]


def _base_contract_observation(
    contract: DeployedContractConfig,
    *,
    status: UnavailableObservationStatus,
    warning: str,
) -> DeployedContractObservation:
    return DeployedContractObservation(
        name=contract.name,
        network=contract.network,
        address=contract.address,
        role=contract.role,
        status=status,
        expected_source_repository=contract.expected_source_repository,
        expected_source_path=contract.expected_source_path,
        read_only_calls=_unavailable_call_observations(
            contract,
            status=status,
            warning=warning,
        ),
        warnings=[warning],
    )


class DeployedMetadataCollector:
    """Collect pinned, read-only bytecode and EIP-1967 metadata for configured contracts."""

    def __init__(
        self,
        client_factory: RpcClientFactory | None = None,
    ) -> None:
        self._client_factory = client_factory or ReadOnlyRpcClient

    def collect(
        self,
        target: TargetConfig,
        *,
        environment: Mapping[str, str] | None = None,
        output_path: Path | None = None,
        scope_snapshot_hash: str | None = None,
        scope_live_content_hash: str | None = None,
    ) -> DeployedMetadataManifest:
        env = environment if environment is not None else os.environ
        networks: list[DeployedNetworkObservation] = []
        observations: list[DeployedContractObservation] = []

        contracts_by_network: dict[str, list[DeployedContractConfig]] = {}
        for contract in target.deployed_contracts:
            contracts_by_network.setdefault(contract.network, []).append(contract)

        for network_name, contracts in contracts_by_network.items():
            network = target.networks[network_name]
            rpc_url = env.get(network.rpc_env_var)
            if not rpc_url:
                warning = f"{network.rpc_env_var} is not configured; deployed metadata was skipped"
                networks.append(
                    DeployedNetworkObservation(
                        network=network_name,
                        rpc_env_var=network.rpc_env_var,
                        expected_chain_id=network.chain_id,
                        status="skipped",
                        warnings=[warning],
                    )
                )
                observations.extend(
                    _base_contract_observation(
                        contract,
                        status="skipped",
                        warning=warning,
                    )
                    for contract in contracts
                )
                continue

            try:
                client = self._client_factory(rpc_url)
            except Exception as exc:
                warning = _safe_rpc_error(exc)
                networks.append(
                    DeployedNetworkObservation(
                        network=network_name,
                        rpc_env_var=network.rpc_env_var,
                        expected_chain_id=network.chain_id,
                        status="failed",
                        warnings=[warning],
                    )
                )
                observations.extend(
                    _base_contract_observation(
                        contract,
                        status="failed",
                        warning=warning,
                    )
                    for contract in contracts
                )
                continue

            try:
                try:
                    observed_chain_id = client.chain_id()
                    block_number = client.block_number()
                except Exception as exc:
                    warning = _safe_rpc_error(exc)
                    networks.append(
                        DeployedNetworkObservation(
                            network=network_name,
                            rpc_env_var=network.rpc_env_var,
                            expected_chain_id=network.chain_id,
                            status="failed",
                            warnings=[warning],
                        )
                    )
                    observations.extend(
                        _base_contract_observation(
                            contract,
                            status="failed",
                            warning=warning,
                        )
                        for contract in contracts
                    )
                    continue

                if observed_chain_id != network.chain_id:
                    warning = (
                        f"RPC chain ID mismatch: expected {network.chain_id}, "
                        f"observed {observed_chain_id}"
                    )
                    networks.append(
                        DeployedNetworkObservation(
                            network=network_name,
                            rpc_env_var=network.rpc_env_var,
                            expected_chain_id=network.chain_id,
                            observed_chain_id=observed_chain_id,
                            block_number=block_number,
                            status="failed",
                            warnings=[warning],
                        )
                    )
                    observations.extend(
                        _base_contract_observation(
                            contract,
                            status="failed",
                            warning=warning,
                        )
                        for contract in contracts
                    )
                    continue

                completed = 0
                failed = 0
                call_failures = 0
                for contract in contracts:
                    try:
                        metadata = client.contract_metadata(
                            contract.address,
                            block_number=block_number,
                        )
                        warnings: list[str] = []
                        status: Literal["completed", "failed"] = "completed"
                        if metadata["bytecode_size"] == 0:
                            status = "failed"
                            warnings.append("No deployed bytecode exists at the configured address")
                        if (
                            metadata["implementation_address"] is not None
                            and metadata["implementation_bytecode_size"] == 0
                        ):
                            status = "failed"
                            warnings.append("EIP-1967 implementation address has no bytecode")
                        if (
                            metadata["beacon_address"] is not None
                            and metadata["beacon_bytecode_size"] == 0
                        ):
                            status = "failed"
                            warnings.append("EIP-1967 beacon address has no bytecode")
                        if contract.proxy_kind == "eip1967" and metadata["proxy_kind"] == "none":
                            warnings.append(
                                "Configured as EIP-1967 but no implementation or beacon slot "
                                "was set"
                            )
                        if contract.proxy_kind == "none" and metadata["proxy_kind"] != "none":
                            warnings.append(
                                "Configured as non-proxy but EIP-1967 metadata was observed"
                            )

                        call_observations: list[ReadOnlyCallObservation] = []
                        for call in contract.read_only_calls:
                            try:
                                raw_result = client.read_only_call(
                                    contract.address,
                                    call.calldata,
                                    block_number=block_number,
                                )
                                decoded_value = _decode_call_result(call, raw_result)
                                expected_value = _normalized_expected_value(call)
                                matches_expected = (
                                    None
                                    if expected_value is None
                                    else decoded_value == expected_value
                                )
                                call_warnings: list[str] = []
                                if matches_expected is False:
                                    warning = (
                                        f"Read-only call {call.name} returned an unexpected "
                                        "value; manual review required"
                                    )
                                    call_warnings.append(warning)
                                    warnings.append(warning)
                                call_observations.append(
                                    ReadOnlyCallObservation(
                                        name=call.name,
                                        calldata=call.calldata,
                                        result_type=call.result_type,
                                        status="completed",
                                        raw_result=raw_result.lower(),
                                        decoded_value=decoded_value,
                                        expected_value=expected_value,
                                        matches_expected=matches_expected,
                                        warnings=call_warnings,
                                    )
                                )
                            except Exception as exc:
                                call_failures += 1
                                warning = _safe_rpc_error(exc)
                                warnings.append(f"Read-only call {call.name} failed: {warning}")
                                call_observations.append(
                                    ReadOnlyCallObservation(
                                        name=call.name,
                                        calldata=call.calldata,
                                        result_type=call.result_type,
                                        status="failed",
                                        expected_value=call.expected_value,
                                        warnings=[warning],
                                    )
                                )

                        observations.append(
                            DeployedContractObservation(
                                name=contract.name,
                                network=contract.network,
                                address=contract.address,
                                role=contract.role,
                                status=status,
                                block_number=metadata["block_number"],
                                bytecode_size=metadata["bytecode_size"],
                                bytecode_sha256=metadata["bytecode_sha256"],
                                proxy_kind=metadata["proxy_kind"],
                                implementation_address=metadata["implementation_address"],
                                implementation_bytecode_size=metadata[
                                    "implementation_bytecode_size"
                                ],
                                implementation_bytecode_sha256=metadata[
                                    "implementation_bytecode_sha256"
                                ],
                                admin_address=metadata["admin_address"],
                                beacon_address=metadata["beacon_address"],
                                beacon_bytecode_size=metadata["beacon_bytecode_size"],
                                beacon_bytecode_sha256=metadata["beacon_bytecode_sha256"],
                                expected_source_repository=contract.expected_source_repository,
                                expected_source_path=contract.expected_source_path,
                                read_only_calls=call_observations,
                                warnings=warnings,
                            )
                        )
                        if status == "completed":
                            completed += 1
                        else:
                            failed += 1
                    except Exception as exc:
                        failed += 1
                        observations.append(
                            _base_contract_observation(
                                contract,
                                status="failed",
                                warning=_safe_rpc_error(exc),
                            )
                        )

                network_warnings: list[str] = []
                if failed:
                    network_warnings.append(
                        f"{failed} configured contract metadata observation(s) failed"
                    )
                if call_failures:
                    network_warnings.append(
                        f"{call_failures} configured read-only call observation(s) failed"
                    )
                networks.append(
                    DeployedNetworkObservation(
                        network=network_name,
                        rpc_env_var=network.rpc_env_var,
                        expected_chain_id=network.chain_id,
                        observed_chain_id=observed_chain_id,
                        block_number=block_number,
                        status="completed" if completed else "failed",
                        warnings=network_warnings,
                    )
                )
            finally:
                client.close()

        manifest = DeployedMetadataManifest(
            target_id=target.target_id,
            created_at_utc=datetime.now(UTC),
            scope_snapshot_hash=scope_snapshot_hash,
            scope_live_content_hash=scope_live_content_hash,
            networks=networks,
            contracts=observations,
        )
        if output_path is not None:
            write_model(output_path, manifest)
        return manifest
