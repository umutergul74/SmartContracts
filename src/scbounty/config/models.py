from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

Severity = Literal["info", "low", "medium", "high", "critical"]
Confidence = Literal["low", "medium", "high"]
ScopeStatus = Literal["in_scope", "possibly_in_scope", "out_of_scope", "unknown"]
TriageStatus = Literal["needs_review", "confirmed", "rejected"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AuthorizationConfig(StrictModel):
    type: Literal["bug_bounty", "educational_fixture"]
    platform: str
    program_name: str
    program_url: HttpUrl
    scope_url: HttpUrl
    information_url: HttpUrl
    last_manually_verified_utc: date
    must_reverify_before_run: bool = True
    poc_required: bool = True
    kyc_required_for_payout: bool = False


class DisclosureConfig(StrictModel):
    channel: str
    submission_url: HttpUrl
    public_disclosure_requires_permission: bool = True


class NetworkConfig(StrictModel):
    chain_id: int = Field(gt=0)
    role: str
    rpc_env_var: str
    read_only: bool = True

    @model_validator(mode="after")
    def reject_secret_fields(self) -> NetworkConfig:
        lowered = self.rpc_env_var.lower()
        if "private" in lowered or "mnemonic" in lowered or "wallet" in lowered:
            raise ValueError("RPC environment variable must not reference wallet secrets")
        return self


class SourceRepository(StrictModel):
    name: str
    url: HttpUrl
    purpose: str
    default_branch: str = "main"
    local_path: str | None = None
    analysis_paths: list[str] = Field(default_factory=list)


class TargetConfig(StrictModel):
    target_id: str
    name: str
    status: str
    risk_profile: str
    authorization: AuthorizationConfig
    disclosure: DisclosureConfig
    allowed_testing: list[str] = Field(min_length=1)
    prohibited_testing: list[str] = Field(min_length=1)
    networks: dict[str, NetworkConfig] = Field(default_factory=dict)
    source_repositories: list[SourceRepository] = Field(default_factory=list)
    seed_in_scope_assets_from_immunefi_first_page: list[str] = Field(default_factory=list)
    seed_dao_addresses: dict[str, str] = Field(default_factory=dict)
    impact_categories_to_prioritize: dict[str, list[str]] = Field(default_factory=dict)
    scope_snapshot_file: str
    local_only_poc: bool = True

    @model_validator(mode="after")
    def enforce_safe_target(self) -> TargetConfig:
        if not self.local_only_poc:
            raise ValueError("local_only_poc must remain true")
        if self.authorization.type == "bug_bounty":
            if any(repository.local_path for repository in self.source_repositories):
                raise ValueError("real bug bounty targets must not use local fixture sources")
            required = {
                "mainnet_transactions",
                "public_testnet_transactions",
                "live_exploit_attempts",
            }
            missing = required.difference(self.prohibited_testing)
            if missing:
                raise ValueError(f"missing required prohibited methods: {sorted(missing)}")
            if not self.authorization.must_reverify_before_run:
                raise ValueError("real targets must re-verify scope before every run")
        return self


class ScopeSnapshot(StrictModel):
    schema_version: Literal["1"] = "1"
    target_id: str
    captured_at_utc: datetime
    source_url: HttpUrl
    program_last_updated: str
    asset_count: int = Field(gt=0)
    asset_urls_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    impact_count: int = Field(gt=0)
    impacts_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    seed_assets: list[str]
    repositories: list[HttpUrl]
    prohibited_activity_markers: list[str]


class ScopeDiff(StrictModel):
    passed: bool
    expected_asset_count: int
    observed_asset_count: int
    expected_asset_digest: str
    observed_asset_digest: str
    expected_impact_count: int
    observed_impact_count: int
    expected_impact_digest: str
    observed_impact_digest: str
    missing_seed_assets: list[str] = Field(default_factory=list)
    missing_safety_markers: list[str] = Field(default_factory=list)


class ScopeAttestation(StrictModel):
    schema_version: Literal["1"] = "1"
    attestation_id: str
    target_id: str
    verified_at_utc: datetime
    scope_url: HttpUrl
    snapshot_hash: str
    live_content_hash: str
    diff: ScopeDiff
    observed_asset_urls: list[str] = Field(default_factory=list)
    observed_impacts: list[str] = Field(default_factory=list)
    local_static_only: Literal[True] = True


class SourceLocation(StrictModel):
    path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)


class EvidenceItem(StrictModel):
    kind: str
    summary: str
    artifact_path: str | None = None
    source: str | None = None


class Finding(StrictModel):
    schema_version: Literal["1"] = "1"
    finding_id: str
    target_id: str
    title: str
    severity: Severity
    confidence: Confidence
    category: str
    detector: str
    tool: str | None = None
    affected_contracts: list[str]
    affected_functions: list[str]
    source_locations: list[SourceLocation]
    description: str
    impact: str
    impact_category: str
    severity_rationale: str
    exploitability_notes: str
    safe_poc_status: Literal[
        "not_started",
        "local_fixture",
        "local_fork",
        "needs_manual_triage",
        "not_reproducible",
    ]
    reproduction_steps: list[str]
    evidence: list[EvidenceItem]
    false_positive_risks: list[str]
    recommended_fix: str
    references: list[str]
    scope_status: ScopeStatus
    scope_evidence: list[str]
    triage_status: TriageStatus = "needs_review"
    artifact_references: list[str] = Field(default_factory=list)
    deduplication_key: str
    created_at_utc: datetime

    @model_validator(mode="after")
    def prevent_untriaged_severity_escalation(self) -> Finding:
        if self.severity in {"high", "critical"} and self.triage_status != "confirmed":
            raise ValueError("high/critical findings require confirmed human triage")
        return self

    @property
    def shareable(self) -> bool:
        return (
            self.scope_status == "in_scope"
            and self.triage_status == "confirmed"
            and self.safe_poc_status in {"local_fixture", "local_fork"}
        )


class ToolExecution(StrictModel):
    tool: str
    available: bool
    version: str | None = None
    command: list[str] = Field(default_factory=list)
    started_at_utc: datetime | None = None
    ended_at_utc: datetime | None = None
    exit_code: int | None = None
    timed_out: bool = False
    stdout: str = ""
    stderr: str = ""


class AnalyzerResult(StrictModel):
    analyzer: str
    status: Literal["completed", "skipped", "failed"]
    execution: ToolExecution
    findings: list[Finding] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class SourceArtifact(StrictModel):
    repository: str
    url: HttpUrl
    commit_sha: str
    checkout_path: str
    selected_paths: list[str]
    selected_content_hash: str


class SourceManifest(StrictModel):
    schema_version: Literal["1"] = "1"
    target_id: str
    created_at_utc: datetime
    artifacts: list[SourceArtifact]


class TriageRecord(StrictModel):
    schema_version: Literal["1"] = "1"
    finding_id: str
    run_id: str
    status: TriageStatus
    note: str
    reviewed_at_utc: datetime


class RunManifest(StrictModel):
    schema_version: Literal["1"] = "1"
    run_id: str
    target_id: str
    started_at_utc: datetime
    completed_at_utc: datetime | None = None
    status: Literal["running", "completed", "failed"]
    safe_mode: Literal[True] = True
    config_hash: str
    scope_attestation: ScopeAttestation | None = None
    source_manifest_path: str | None = None
    analyzer_results: list[AnalyzerResult] = Field(default_factory=list)
    findings_path: str | None = None


class ReportManifest(StrictModel):
    schema_version: Literal["1"] = "1"
    run_id: str
    target_id: str
    generated_at_utc: datetime
    format: Literal["markdown", "json", "immunefi"]
    output_path: str
    included_findings: list[str]
    draft: bool


class BuildManifest(StrictModel):
    schema_version: Literal["1"] = "1"
    target_id: str
    workspace: Path
    execution: ToolExecution
