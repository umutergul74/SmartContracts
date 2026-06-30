from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, StrictUndefined

from scbounty.utils.paths import repository_root


def generate_foundry_harness(target_id: str, output_dir: Path) -> Path:
    template_path = repository_root() / "templates" / "foundry" / "invariant_test.t.sol.j2"
    template = Environment(undefined=StrictUndefined, autoescape=False).from_string(
        template_path.read_text(encoding="utf-8")
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{target_id.title()}GatewayInvariant.t.sol"
    destination.write_text(template.render(target_id=target_id), encoding="utf-8")
    return destination
