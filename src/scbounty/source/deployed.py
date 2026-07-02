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

    def close(self) -> None: ...


RpcClientFactory = Callable[[str], RpcClient]
ObservationStatus = Literal["completed", "skipped", "failed"]


def _safe_rpc_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: read-only RPC request failed; endpoint details redacted"


def _base_contract_observation(
    contract: DeployedContractConfig,
    *,
    status: ObservationStatus,
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
