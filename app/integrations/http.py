"""Shared HTTP handling. Never log URLs, headers, bodies or credentials."""

import logging
import time
from datetime import date
from typing import Any
import httpx
from app.exceptions.external import ExternalAPIError, ExternalAPITimeoutError

logger = logging.getLogger("smartstock.integrations")
# httpx/httpcore request logs can contain query-string API keys.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


async def get_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    provider: str,
    requested_date: date,
    params: dict[str, Any],
    headers: dict[str, str] | None,
    error_type: type[ExternalAPIError],
    timeout_type: type[ExternalAPITimeoutError]
) -> Any:
    started = time.monotonic()
    try:
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        payload = response.json()
        logger.info(
            "provider=%s date=%s elapsed_ms=%.0f result=ok",
            provider,
            requested_date,
            (time.monotonic() - started) * 1000,
        )
        return payload
    except httpx.TimeoutException:
        logger.warning(
            "provider=%s date=%s elapsed_ms=%.0f result=timeout",
            provider,
            requested_date,
            (time.monotonic() - started) * 1000,
        )
        raise timeout_type() from None
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "provider=%s date=%s elapsed_ms=%.0f result=http_error status=%s",
            provider,
            requested_date,
            (time.monotonic() - started) * 1000,
            exc.response.status_code,
        )
        raise error_type() from None
    except httpx.RequestError:
        logger.warning(
            "provider=%s date=%s elapsed_ms=%.0f result=connection_error",
            provider,
            requested_date,
            (time.monotonic() - started) * 1000,
        )
        raise error_type() from None
    except (ValueError, UnicodeDecodeError):
        logger.warning(
            "provider=%s date=%s elapsed_ms=%.0f result=invalid_json",
            provider,
            requested_date,
            (time.monotonic() - started) * 1000,
        )
        raise error_type() from None


def invalid_response(provider: str, requested_date: date) -> None:
    logger.warning(
        "provider=%s date=%s result=invalid_response", provider, requested_date
    )
