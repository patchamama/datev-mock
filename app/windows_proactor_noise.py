"""Suppresses a known-benign asyncio/Windows log noise pattern.

On Windows, uvicorn's SSL server uses asyncio's ProactorEventLoop. When a
client (e.g. a browser) closes an HTTPS connection, the loop sometimes
tries `socket.shutdown(SHUT_RDWR)` on a socket the remote side already
reset, and Windows' Proactor implementation surfaces that as an unhandled
exception in `_ProactorBasePipeTransport._call_connection_lost` instead of
swallowing it (unlike Linux). This is a long-documented asyncio/uvicorn
behavior, not an application error — the request that triggered it has
already completed successfully by the time this fires.

`install()` registers a loop exception handler that filters out exactly
this pattern and otherwise defers to asyncio's default handling, so real
problems are still reported normally.
"""
from __future__ import annotations

import asyncio
from typing import Any


def _is_benign_proactor_reset(context: dict[str, Any]) -> bool:
    exception = context.get("exception")
    if not isinstance(exception, ConnectionResetError):
        return False
    handle = context.get("handle")
    return "_call_connection_lost" in repr(handle)


def _handler(loop: asyncio.AbstractEventLoop, context: dict[str, Any]) -> None:
    if _is_benign_proactor_reset(context):
        return
    loop.default_exception_handler(context)


def install() -> None:
    asyncio.get_running_loop().set_exception_handler(_handler)
