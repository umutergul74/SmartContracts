import logging

from scbounty.utils.logging import configure_logging


def test_http_request_logging_is_disabled_even_in_verbose_mode(capsys) -> None:
    configure_logging(verbose=True)

    logging.getLogger("httpx").critical("HTTP Request: POST https://secret-token@example.test")

    captured = capsys.readouterr()
    assert "secret-token" not in captured.out
    assert "secret-token" not in captured.err
