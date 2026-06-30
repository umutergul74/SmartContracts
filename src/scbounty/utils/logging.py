from __future__ import annotations

import logging

from rich.logging import RichHandler


def configure_logging(verbose: bool = False) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=False, show_path=verbose)],
        force=True,
    )
