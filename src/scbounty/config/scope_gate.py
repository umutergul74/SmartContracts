from __future__ import annotations

import html
import re
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import httpx

from scbounty.config.loader import load_scope_snapshot
from scbounty.config.models import ScopeAttestation, ScopeDiff, ScopeSnapshot, TargetConfig
from scbounty.utils.hashing import sha256_bytes, sha256_text, stable_json_hash
from scbounty.utils.serialization import write_model

_GITHUB_SOLIDITY_URL = re.compile(
    r"https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/"
    r"(?:blob|tree)/[^\"'\\\s?]+\.sol(?:\?[^\"'\\\s]*)?"
)
_SPACE = re.compile(r"\s+")

KNOWN_ARBITRUM_IMPACTS: tuple[tuple[str, str], ...] = (
    ("critical", "Direct theft of any user funds, whether at-rest or in-motion"),
    ("critical", "Permanent freezing of funds (cannot be fixed by upgrade)"),
    ("critical", "Insolvency"),
    ("high", "Permanent freezing of funds (can be fixed by upgrade)"),
    ("high", "Bugs relating to reorgs"),
    ("high", "Damage relating to withdrawing funds via fast bridges"),
    (
        "high",
        "Denial of Service (DoS) Attacks that cause network-wide outages "
        "(attacks that only take down the RPC do not count)",
    ),
    (
        "medium",
        "Griefing (e.g. no profit motive for an attacker, but damage to the users or the protocol)",
    ),
    ("medium", "Theft of gas"),
    ("medium", "Unbounded gas consumption"),
    ("medium", "Smart contract unable to operate due to lack of funds"),
    ("medium", "Block stuffing for profit"),
    ("low", "Smart contract fails to deliver promised returns, but doesn’t lose value"),
)


class ScopeVerificationError(RuntimeError):
    """Raised when a real target cannot prove its current authorization scope."""


class _ScriptCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._in_script = False
        self.parts: list[str] = []

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        del attrs
        if tag.casefold() == "script":
            self._in_script = True

    def handle_endtag(self, tag: str) -> None:
        if tag.casefold() == "script":
            self._in_script = False

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self.parts.append(data)


def _normalized_page(raw: str) -> str:
    return html.unescape(raw).replace("\\/", "/").replace("\\u0026", "&")


def _script_payload(raw: str) -> str:
    collector = _ScriptCollector()
    collector.feed(raw)
    return "\n".join(collector.parts)


def _normalized_text(value: str) -> str:
    return _SPACE.sub(" ", value).strip().casefold()


def _canonical_asset_url(value: str) -> str:
    split = urlsplit(value)
    path = split.path.replace("/tree/", "/blob/")
    return urlunsplit((split.scheme.lower(), split.netloc.lower(), path, "", ""))


def extract_asset_urls(raw: str) -> list[str]:
    page = _normalized_page(raw)
    scripts = _normalized_page(_script_payload(raw))
    source = scripts if _GITHUB_SOLIDITY_URL.search(scripts) else page
    return [_canonical_asset_url(item) for item in _GITHUB_SOLIDITY_URL.findall(source)]


def extract_impacts(raw: str) -> list[str]:
    page = _normalized_text(_normalized_page(raw))
    observed: list[str] = []
    for severity, title in KNOWN_ARBITRUM_IMPACTS:
        if _normalized_text(title) in page:
            observed.append(f"{severity}|{title}")
    return observed


def scope_fingerprint(raw: str) -> tuple[list[str], list[str]]:
    assets = sorted(extract_asset_urls(raw))
    impacts = sorted(extract_impacts(raw))
    return assets, impacts


def compare_live_scope(
    raw: str,
    snapshot: ScopeSnapshot,
) -> ScopeDiff:
    assets, impacts = scope_fingerprint(raw)
    asset_names = {Path(urlsplit(url).path).name for url in assets}
    page = _normalized_text(_normalized_page(raw))
    missing_seed = sorted(set(snapshot.seed_assets).difference(asset_names))
    missing_markers = sorted(
        marker
        for marker in snapshot.prohibited_activity_markers
        if _normalized_text(marker) not in page
    )
    asset_digest = sha256_text("\n".join(assets))
    impact_digest = sha256_text("\n".join(impacts))
    passed = (
        len(assets) == snapshot.asset_count
        and asset_digest == snapshot.asset_urls_sha256
        and len(impacts) == snapshot.impact_count
        and impact_digest == snapshot.impacts_sha256
        and not missing_seed
        and not missing_markers
    )
    return ScopeDiff(
        passed=passed,
        expected_asset_count=snapshot.asset_count,
        observed_asset_count=len(assets),
        expected_asset_digest=snapshot.asset_urls_sha256,
        observed_asset_digest=asset_digest,
        expected_impact_count=snapshot.impact_count,
        observed_impact_count=len(impacts),
        expected_impact_digest=snapshot.impacts_sha256,
        observed_impact_digest=impact_digest,
        missing_seed_assets=missing_seed,
        missing_safety_markers=missing_markers,
    )


class ScopeGate:
    def __init__(self, client: httpx.Client | None = None) -> None:
        self._client = client

    def verify(
        self,
        target: TargetConfig,
        *,
        root: Path | None = None,
        output_path: Path | None = None,
    ) -> ScopeAttestation:
        if target.authorization.type == "educational_fixture":
            snapshot = load_scope_snapshot(target, root)
            verified = datetime.now(UTC)
            snapshot_hash = stable_json_hash(snapshot.model_dump(mode="json"))
            diff = ScopeDiff(
                passed=True,
                expected_asset_count=snapshot.asset_count,
                observed_asset_count=snapshot.asset_count,
                expected_asset_digest=snapshot.asset_urls_sha256,
                observed_asset_digest=snapshot.asset_urls_sha256,
                expected_impact_count=snapshot.impact_count,
                observed_impact_count=snapshot.impact_count,
                expected_impact_digest=snapshot.impacts_sha256,
                observed_impact_digest=snapshot.impacts_sha256,
            )
            attestation = ScopeAttestation(
                attestation_id=sha256_text(
                    f"{target.target_id}|fixture|{verified.isoformat()}|{snapshot_hash}"
                )[:24],
                target_id=target.target_id,
                verified_at_utc=verified,
                scope_url=target.authorization.scope_url,
                snapshot_hash=snapshot_hash,
                live_content_hash=sha256_text("educational-fixture-scope"),
                diff=diff,
            )
            if output_path is not None:
                write_model(output_path, attestation)
            return attestation
        snapshot = load_scope_snapshot(target, root)
        owns_client = self._client is None
        client = self._client or httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(20.0),
            headers={
                "User-Agent": "scbounty/0.1 authorized-local-research scope-verifier",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        try:
            response = client.get(str(target.authorization.scope_url))
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ScopeVerificationError(
                f"Live scope could not be verified; real-target analysis is refused: {exc}"
            ) from exc
        finally:
            if owns_client:
                client.close()

        raw_bytes = response.content
        try:
            raw = raw_bytes.decode(response.encoding or "utf-8", errors="replace")
            observed_assets, observed_impacts = scope_fingerprint(raw)
            diff = compare_live_scope(raw, snapshot)
        except Exception as exc:
            raise ScopeVerificationError(f"Live scope parser failed closed: {exc}") from exc
        if not diff.passed:
            raise ScopeVerificationError(
                "Live scope differs from the reviewed snapshot; analysis is refused. "
                f"assets={diff.observed_asset_count}/{diff.expected_asset_count}, "
                f"impacts={diff.observed_impact_count}/{diff.expected_impact_count}, "
                f"missing_seed={diff.missing_seed_assets}, "
                f"missing_safety_markers={diff.missing_safety_markers}"
            )

        verified = datetime.now(UTC)
        snapshot_hash = stable_json_hash(snapshot.model_dump(mode="json"))
        live_hash = sha256_bytes(raw_bytes)
        attestation = ScopeAttestation(
            attestation_id=sha256_text(
                f"{target.target_id}|{verified.isoformat()}|{snapshot_hash}|{live_hash}"
            )[:24],
            target_id=target.target_id,
            verified_at_utc=verified,
            scope_url=target.authorization.scope_url,
            snapshot_hash=snapshot_hash,
            live_content_hash=live_hash,
            diff=diff,
            observed_asset_urls=observed_assets,
            observed_impacts=observed_impacts,
        )
        if output_path is not None:
            write_model(output_path, attestation)
        return attestation
