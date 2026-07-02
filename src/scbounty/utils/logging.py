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
    # httpx/httpcore request logs include full URLs. RPC endpoints commonly carry API
    # tokens in their path or query string, so they must stay silent even in verbose mode.
    for logger_name in ("httpcore", "httpx"):
        logging.getLogger(logger_name).disabled = True
