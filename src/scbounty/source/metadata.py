from __future__ import annotations

from typing import Any

import httpx

from scbounty.utils.hashing import sha256_text

_EIP1967_IMPLEMENTATION_SLOT = "0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc"
_EIP1967_ADMIN_SLOT = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"


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
        if method not in {"eth_getCode", "eth_getStorageAt", "eth_call", "eth_chainId"}:
            raise ValueError(f"RPC method is not in the read-only allowlist: {method}")
        response = self._client.post(
            self._rpc_url,
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
        )
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            raise RuntimeError(f"Read-only RPC returned an error: {payload['error']}")
        return str(payload["result"])

    def contract_metadata(self, address: str) -> dict[str, str]:
        code = self._call("eth_getCode", [address, "latest"])
        implementation = self._call(
            "eth_getStorageAt", [address, _EIP1967_IMPLEMENTATION_SLOT, "latest"]
        )
        admin = self._call("eth_getStorageAt", [address, _EIP1967_ADMIN_SLOT, "latest"])
        return {
            "address": address,
            "bytecode_sha256": sha256_text(code),
            "implementation_slot": implementation,
            "admin_slot": admin,
        }
