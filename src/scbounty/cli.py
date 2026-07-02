from __future__ import annotations

import os
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import orjson
import typer
from rich.console import Console
from rich.table import Table

from scbounty import __version__
from scbounty.analyzers import (
    AderynAdapter,
    EchidnaAdapter,
    FoundryAdapter,
    HalmosAdapter,
    MedusaAdapter,
    MythrilAdapter,
    SemgrepAdapter,
    SlitherAdapter,
    SolhintAdapter,
)
from scbounty.analyzers.runner import AnalysisRunner
from scbounty.config.loader import load_target
from scbounty.config.scope_coverage import (
    compare_target_scope_coverage,
    latest_attestation_path,
    load_scope_attestation,
    render_scope_coverage_markdown,
)
from scbounty.config.scope_gate import ScopeGate, ScopeVerificationError
from scbounty.harness.echidna_generator import generate_echidna_config
from scbounty.harness.foundry_generator import generate_foundry_harness
from scbounty.harness.medusa_generator import generate_medusa_config
from scbounty.reporting.service import (
    ReportError,
    generate_report,
    load_findings,
    resolve_run,
    triage_finding,
)
from scbounty.source.deployed import DeployedMetadataCollector
from scbounty.source.fetcher import SourceFetcher, SourceFetchError
from scbounty.targets.arbitrum import ARBITRUM_SCOPE_MESSAGE
from scbounty.targets.registry import list_target_ids
from scbounty.utils.logging import configure_logging
from scbounty.utils.paths import artifacts_root, repository_root, safe_child
from scbounty.utils.versions import executable_path, tool_version

console = Console()
app = typer.Typer(
    name="scbounty",
    help="Authorized, local-only smart-contract bounty research workbench.",
    no_args_is_help=True,
)
targets_app = typer.Typer(help="Inspect configured research targets.")
scope_app = typer.Typer(help="Verify live authorization scope.")
source_app = typer.Typer(help="Acquire and pin reviewed source repositories.")
harness_app = typer.Typer(help="Generate local-only harness templates.")
report_app = typer.Typer(help="Generate draft research reports.")
env_app = typer.Typer(help="Inspect the local toolchain.")
findings_app = typer.Typer(help="List and manually triage findings.")

app.add_typer(targets_app, name="targets")
app.add_typer(scope_app, name="scope")
app.add_typer(source_app, name="source")
app.add_typer(harness_app, name="harness")
app.add_typer(report_app, name="report")
app.add_typer(env_app, name="env")
app.add_typer(findings_app, name="findings")


@app.callback()
def main(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show diagnostic detail."),
) -> None:
    configure_logging(verbose)


@targets_app.command("list")
def targets_list() -> None:
    table = Table("Target", "Name", "Status", "Authorization")
    for target_id in list_target_ids():
        target = load_target(target_id)
        table.add_row(target.target_id, target.name, target.status, target.authorization.type)
    console.print(table)


@targets_app.command("show")
def targets_show(target_id: str) -> None:
    target = load_target(target_id)
    console.print_json(target.model_dump_json(indent=2))


@scope_app.command("check")
def scope_check(target_id: str) -> None:
    target = load_target(target_id)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = safe_child(artifacts_root(), "scope", target_id, f"{timestamp}.json")
    try:
        attestation = ScopeGate().verify(target, output_path=output)
    except ScopeVerificationError as exc:
        console.print(f"[red]Scope verification refused:[/] {exc}")
        raise typer.Exit(3) from exc
    if target.authorization.type == "educational_fixture":
        console.print(
            "[green]Educational fixture scope attested for local-only training. "
            "This is not a bounty target.[/]"
        )
    else:
        console.print(f"[green]{ARBITRUM_SCOPE_MESSAGE}[/]")
    console.print(f"Attestation: {output}")
    console.print(f"Scope hash: {attestation.snapshot_hash}")


@scope_app.command("coverage")
def scope_coverage(
    target_id: str,
    attestation: Path | None = typer.Option(
        None,
        "--attestation",
        exists=True,
        dir_okay=False,
        help="Scope attestation JSON. Defaults to the latest local attestation.",
    ),
    output_format: Literal["table", "json", "markdown"] = typer.Option(
        "table",
        "--format",
        help="Output format for the coverage summary.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        dir_okay=False,
        help="Optional file path for JSON or Markdown coverage output.",
    ),
) -> None:
    target = load_target(target_id)
    try:
        attestation_path = attestation or latest_attestation_path(target_id)
        scope_attestation = load_scope_attestation(attestation_path)
    except (FileNotFoundError, ValueError) as exc:
        console.print(f"[red]Scope coverage refused:[/] {exc}")
        raise typer.Exit(3) from exc

    coverage = compare_target_scope_coverage(target, scope_attestation)
    if output_format == "json":
        payload = coverage.to_payload(target_id=target_id, attestation_path=attestation_path)
        rendered = (
            orjson.dumps(payload, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS).decode() + "\n"
        )
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
            console.print(f"Wrote scope coverage JSON: {output}")
        else:
            typer.echo(rendered, nl=False)
        return

    if output_format == "markdown":
        rendered = render_scope_coverage_markdown(
            coverage,
            target_id=target_id,
            attestation_path=attestation_path,
        )
        if output:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8")
            console.print(f"Wrote scope coverage Markdown: {output}")
        else:
            typer.echo(rendered, nl=False)
        return

    table = Table("Repository", "Live assets", "Configured paths", "Exact matches")
    for repository, counts in coverage.repositories.items():
        observed_count, configured_count, exact_count = counts
        table.add_row(
            repository,
            str(observed_count),
            str(configured_count),
            str(exact_count),
        )
    console.print(table)
    console.print(f"Attestation: {attestation_path}")
    console.print(
        "Summary: "
        f"{coverage.exact_match_count}/{coverage.github_blob_asset_count} GitHub blob assets "
        f"are selected by this target profile "
        f"({coverage.observed_asset_count} total observed scope assets); "
        f"{len(coverage.configured_not_observed)} configured paths are not in the "
        "observed live scope."
    )
    if coverage.observed_not_configured:
        console.print("[yellow]Live assets outside this analysis profile:[/]")
        for key in coverage.observed_not_configured[:20]:
            console.print(f"- {key.repository}/{key.path}")
        if len(coverage.observed_not_configured) > 20:
            console.print(f"... plus {len(coverage.observed_not_configured) - 20} more")


@source_app.command("fetch")
def source_fetch(target_id: str) -> None:
    target = load_target(target_id)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = safe_child(artifacts_root(), "sources", target_id, f"{timestamp}.json")
    try:
        ScopeGate().verify(target)
        manifest = SourceFetcher().fetch(target, output_path=output)
    except (ScopeVerificationError, SourceFetchError) as exc:
        console.print(f"[red]Source acquisition refused:[/] {exc}")
        raise typer.Exit(4) from exc
    table = Table("Repository", "Commit", "Selected files")
    for artifact in manifest.artifacts:
        table.add_row(
            artifact.repository, artifact.commit_sha[:12], str(len(artifact.selected_paths))
        )
    console.print(table)
    console.print(f"Manifest: {output}")


@source_app.command("metadata")
def source_metadata(target_id: str) -> None:
    """Capture read-only deployed bytecode and EIP-1967 metadata."""
    target = load_target(target_id)
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    output = safe_child(artifacts_root(), "deployed", target_id, f"{timestamp}.json")
    try:
        attestation = ScopeGate().verify(target)
        manifest = DeployedMetadataCollector().collect(
            target,
            output_path=output,
            scope_snapshot_hash=attestation.snapshot_hash,
            scope_live_content_hash=attestation.live_content_hash,
        )
    except ScopeVerificationError as exc:
        console.print(f"[red]Deployed metadata refused:[/] {exc}")
        raise typer.Exit(4) from exc

    table = Table("Network", "Contract", "Status", "Code bytes", "Proxy", "Implementation")
    for contract in manifest.contracts:
        implementation = contract.implementation_address or "-"
        table.add_row(
            contract.network,
            contract.name,
            contract.status,
            str(contract.bytecode_size) if contract.bytecode_size is not None else "-",
            contract.proxy_kind,
            implementation,
        )
    console.print(table)
    completed = sum(contract.status == "completed" for contract in manifest.contracts)
    skipped = sum(contract.status == "skipped" for contract in manifest.contracts)
    failed = sum(contract.status == "failed" for contract in manifest.contracts)
    console.print(f"Deployed metadata: {completed} completed, {skipped} skipped, {failed} failed")
    console.print(f"Manifest: {output}")


@app.command("analyze")
def analyze(
    target_id: str,
    safe: bool = typer.Option(True, "--safe", help="Required local/static-only mode."),
    tool: str | None = typer.Option(None, "--tool", help="Run one configured analyzer."),
) -> None:
    if safe is not True:
        console.print("[red]Only safe mode exists.[/]")
        raise typer.Exit(2)
    target = load_target(target_id)
    try:
        manifest, findings, run_dir = AnalysisRunner().run(target, tool=tool)
    except (ScopeVerificationError, SourceFetchError, ValueError) as exc:
        console.print(f"[red]Analysis refused:[/] {exc}")
        raise typer.Exit(5) from exc
    table = Table("Analyzer", "Status", "Version", "Warnings")
    for result in manifest.analyzer_results:
        table.add_row(
            result.analyzer,
            result.status,
            result.execution.version or "-",
            "; ".join(result.warnings) or "-",
        )
    console.print(table)
    console.print(f"Findings requiring review: {len(findings)}")
    console.print(f"Run: {run_dir}")


@harness_app.command("generate")
def harness_generate(
    target_id: str,
    kind: str = typer.Option(..., "--kind", help="foundry, echidna, or medusa"),
) -> None:
    load_target(target_id)
    output_dir = safe_child(artifacts_root(), "harness", target_id, kind)
    generators = {
        "foundry": generate_foundry_harness,
        "echidna": generate_echidna_config,
        "medusa": generate_medusa_config,
    }
    generator = generators.get(kind)
    if generator is None:
        console.print("[red]Harness kind must be foundry, echidna, or medusa.[/]")
        raise typer.Exit(2)
    output = generator(target_id, output_dir)
    console.print(f"[green]Generated local-only harness:[/] {output}")


@app.command("test")
def test_run(
    target_id: str,
    kind: str = typer.Option(..., "--kind", help="unit or invariant"),
    local_only: bool = typer.Option(False, "--local-only", help="Required safety acknowledgement."),
) -> None:
    load_target(target_id)
    if not local_only:
        console.print("[red]Tests require --local-only.[/]")
        raise typer.Exit(2)
    if kind not in {"unit", "invariant"}:
        console.print("[red]Test kind must be unit or invariant.[/]")
        raise typer.Exit(2)
    fixture = repository_root() / "tests" / "fixtures" / "toy_bridge"
    result = FoundryAdapter().test(
        fixture,
        "invariant_EscrowNeverFallsBelowRepresentationSupply" if kind == "invariant" else None,
    )
    if result.status != "completed":
        console.print(
            f"[red]Foundry test did not complete:[/] "
            f"{result.execution.stderr or '; '.join(result.warnings)}"
        )
        raise typer.Exit(6)
    console.print("[green]Local-only Foundry tests passed.[/]")


@report_app.command("generate")
def report_generate(
    target_id: str,
    report_format: str = typer.Option(..., "--format", help="markdown, json, or immunefi"),
    run_id: str | None = typer.Option(None, "--run-id"),
) -> None:
    target = load_target(target_id)
    if report_format not in {"markdown", "json", "immunefi"}:
        console.print("[red]Report format must be markdown, json, or immunefi.[/]")
        raise typer.Exit(2)
    try:
        run_dir = resolve_run(target_id, run_id)
        manifest = generate_report(
            target,
            run_dir,
            report_format,  # type: ignore[arg-type]
        )
    except (ReportError, RuntimeError) as exc:
        console.print(f"[red]Report generation refused:[/] {exc}")
        raise typer.Exit(7) from exc
    console.print(f"[green]Report generated:[/] {manifest.output_path}")


@findings_app.command("list")
def findings_list(
    target_id: str,
    run_id: str | None = typer.Option(None, "--run-id"),
) -> None:
    run_dir = resolve_run(target_id, run_id)
    findings = load_findings(run_dir)
    table = Table("ID", "Severity", "Confidence", "Scope", "Triage", "Title")
    for finding in findings:
        table.add_row(
            finding.finding_id,
            finding.severity,
            finding.confidence,
            finding.scope_status,
            finding.triage_status,
            finding.title,
        )
    console.print(table)


@findings_app.command("triage")
def findings_triage(
    finding_id: str,
    run_id: str = typer.Option(..., "--run-id"),
    status: str = typer.Option(..., "--status"),
    note_file: Path = typer.Option(..., "--note-file", exists=True, dir_okay=False),
    scope_confirmed: bool = typer.Option(False, "--scope-confirmed"),
    poc_status: str | None = typer.Option(None, "--poc-status"),
) -> None:
    allowed_status = {"needs_review", "confirmed", "rejected"}
    allowed_poc = {None, "local_fixture", "local_fork"}
    if status not in allowed_status or poc_status not in allowed_poc:
        console.print("[red]Invalid triage status or PoC status.[/]")
        raise typer.Exit(2)
    run_dir = safe_child(artifacts_root(), "runs", run_id)
    try:
        finding = triage_finding(
            run_dir,
            finding_id,
            status,  # type: ignore[arg-type]
            note_file.read_text(encoding="utf-8"),
            scope_confirmed=scope_confirmed,
            poc_status=poc_status,  # type: ignore[arg-type]
        )
    except ReportError as exc:
        console.print(f"[red]Triage refused:[/] {exc}")
        raise typer.Exit(8) from exc
    console.print(f"[green]Updated {finding.finding_id}:[/] {finding.triage_status}")


@env_app.command("doctor")
def env_doctor() -> None:
    adapters = [
        FoundryAdapter(),
        SlitherAdapter(),
        SemgrepAdapter(),
        AderynAdapter(),
        MythrilAdapter(),
        EchidnaAdapter(),
        MedusaAdapter(),
        HalmosAdapter(),
        SolhintAdapter(),
    ]
    table = Table("Tool", "Available", "Version")
    table.add_row("scbounty", "yes", __version__)
    table.add_row("python", "yes", platform.python_version())
    table.add_row("git", "yes" if executable_path("git") else "no", tool_version("git") or "-")
    for adapter in adapters:
        table.add_row(
            adapter.name,
            "yes" if adapter.is_available() else "no",
            adapter.version() or "-",
        )
    console.print(table)
    rpc_names = ("ETHEREUM_RPC_URL", "ARBITRUM_ONE_RPC_URL", "ARBITRUM_NOVA_RPC_URL")
    configured = [name for name in rpc_names if os.getenv(name)]
    console.print(
        f"Read-only RPC configuration: {len(configured)}/{len(rpc_names)} "
        "(values are intentionally hidden)"
    )
    console.print("Private keys are neither required nor loaded.")


def entrypoint() -> None:
    app()


if __name__ == "__main__":
    entrypoint()
