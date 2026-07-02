from __future__ import annotations

from typing import Any, Literal, TypedDict

import httpx

from scbounty.utils.hashing import sha256_bytes

_EIP1967_IMPLEMENTATION_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
_EIP1967_ADMIN_SLOT = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"
_EIP1967_BEACON_SLOT = "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50"
_BEACON_IMPLEMENTATION_CALLDATA = "0x5c60da1b"
_ZERO_ADDRESS = "0x" + "00" * 20


class ContractMetadata(TypedDict):
    address: str
    block_number: int
    bytecode_size: int
    bytecode_sha256: str
    proxy_kind: Literal["eip1967", "eip1967_beacon", "none"]
    implementation_address: str | None
    implementation_bytecode_size: int | None
    implementation_bytecode_sha256: str | None
    admin_address: str | None
    beacon_address: str | None
    beacon_bytecode_size: int | None
    beacon_bytecode_sha256: str | None


def _hex_bytes(value: str) -> bytes:
    if not value.startswith("0x"):
        raise ValueError("RPC hex value must start with 0x")
    payload = value[2:]
    if len(payload) % 2:
        payload = f"0{payload}"
    try:
        return bytes.fromhex(payload)
    except ValueError as exc:
        raise ValueError("RPC returned malformed hexadecimal data") from exc


def _storage_address(value: str) -> str | None:
    raw = _hex_bytes(value)
    if len(raw) > 32:
        raise ValueError("RPC storage value exceeds 32 bytes")
    padded = raw.rjust(32, b"\0")
    address = f"0x{padded[-20:].hex()}"
    return None if address == _ZERO_ADDRESS else address


def _code_fingerprint(code: str) -> tuple[int, str]:
    raw = _hex_bytes(code)
    return len(raw), sha256_bytes(raw)


class ReadOnlyRpcClient:
    """Small JSON-RPC client exposing only non-mutating Ethereum methods."""

    def __init__(self, rpc_url: str, client: httpx.Client | None = None) -> None:
        self._rpc_url = rpc_url
        self._client = client or httpx.Client(timeout=15.0)
        self._owns_client = client is None

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def _call(self, method: str, params: list[Any]) -> str:
        if method not in {
            "eth_blockNumber",
            "eth_call",
            "eth_chainId",
            "eth_getCode",
            "eth_getStorageAt",
        }:
            raise ValueError(f"RPC method is not in the read-only allowlist: {method}")
        response = self._client.post(
            self._rpc_url,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        )
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            raise RuntimeError(f"Read-only RPC returned an error: {payload['error']}")
        result = payload.get("result")
        if not isinstance(result, str):
            raise RuntimeError("Read-only RPC returned a non-string result")
        return result

    def chain_id(self) -> int:
        return int(self._call("eth_chainId", []), 16)

    def block_number(self) -> int:
        return int(self._call("eth_blockNumber", []), 16)

    def _code(self, address: str, block_tag: str) -> tuple[int, str]:
        return _code_fingerprint(self._call("eth_getCode", [address, block_tag]))

    def contract_metadata(
        self,
        address: str,
        *,
        block_number: int | None = None,
    ) -> ContractMetadata:
        observed_block = block_number if block_number is not None else self.block_number()
        block_tag = hex(observed_block)
        code_size, code_hash = self._code(address, block_tag)
        implementation = _storage_address(
            self._call(
                "eth_getStorageAt",
                [address, _EIP1967_IMPLEMENTATION_SLOT, block_tag],
            )
        )
        admin = _storage_address(
            self._call("eth_getStorageAt", [address, _EIP1967_ADMIN_SLOT, block_tag])
        )
        beacon = _storage_address(
            self._call("eth_getStorageAt", [address, _EIP1967_BEACON_SLOT, block_tag])
        )

        proxy_kind: Literal["eip1967", "eip1967_beacon", "none"] = "none"
        implementation_size: int | None = None
        implementation_hash: str | None = None
        beacon_size: int | None = None
        beacon_hash: str | None = None

        if implementation is not None:
            proxy_kind = "eip1967"
        elif beacon is not None:
            proxy_kind = "eip1967_beacon"
            beacon_size, beacon_hash = self._code(beacon, block_tag)
            implementation = _storage_address(
                self._call(
                    "eth_call",
                    [{"to": beacon, "data": _BEACON_IMPLEMENTATION_CALLDATA}, block_tag],
                )
            )

        if implementation is not None:
            implementation_size, implementation_hash = self._code(implementation, block_tag)

        return ContractMetadata(
            address=address,
            block_number=observed_block,
            bytecode_size=code_size,
            bytecode_sha256=code_hash,
            proxy_kind=proxy_kind,
            implementation_address=implementation,
            implementation_bytecode_size=implementation_size,
            implementation_bytecode_sha256=implementation_hash,
            admin_address=admin,
            beacon_address=beacon,
            beacon_bytecode_size=beacon_size,
            beacon_bytecode_sha256=beacon_hash,
        )
