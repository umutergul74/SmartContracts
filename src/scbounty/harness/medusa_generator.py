from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, StrictUndefined

from scbounty.utils.paths import repository_root


def generate_medusa_config(target_id: str, output_dir: Path) -> Path:
    template_path = repository_root() / "templates" / "medusa" / "medusa.json.j2"
    destination = output_dir / "medusa.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    rendered = Environment(undefined=StrictUndefined).from_string(
        template_path.read_text(encoding="utf-8")
    )
    destination.write_text(rendered.render(target_id=target_id), encoding="utf-8")
    return destination
