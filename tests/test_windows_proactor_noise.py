"""Tests for the Windows ProactorEventLoop connection-reset noise filter.

Real socket/SSL behavior isn't reproducible via `TestClient` (no real
sockets), so these test the filtering logic directly: does it correctly
distinguish the known-benign pattern from anything else, and does it defer
unrecognized exceptions to the loop's normal handling.
"""
from __future__ import annotations

from unittest.mock import MagicMock

from app.windows_proactor_noise import _handler, _is_benign_proactor_reset


class _FakeHandle:
    def __repr__(self) -> str:
        return "<Handle _ProactorBasePipeTransport._call_connection_lost(None)>"


class _OtherHandle:
    def __repr__(self) -> str:
        return "<Handle SomeOtherCallback()>"


def test_benign_proactor_reset_is_recognized():
    context = {"exception": ConnectionResetError(), "handle": _FakeHandle()}
    assert _is_benign_proactor_reset(context) is True


def test_connection_reset_from_a_different_handle_is_not_suppressed():
    context = {"exception": ConnectionResetError(), "handle": _OtherHandle()}
    assert _is_benign_proactor_reset(context) is False


def test_non_connection_reset_exception_is_not_suppressed():
    context = {"exception": ValueError("something else"), "handle": _FakeHandle()}
    assert _is_benign_proactor_reset(context) is False


def test_missing_exception_key_is_not_suppressed():
    assert _is_benign_proactor_reset({"handle": _FakeHandle()}) is False


def test_handler_swallows_the_benign_pattern_without_calling_default_handler():
    loop = MagicMock()
    context = {"exception": ConnectionResetError(), "handle": _FakeHandle()}

    _handler(loop, context)

    loop.default_exception_handler.assert_not_called()


def test_handler_defers_unrecognized_exceptions_to_the_default_handler():
    loop = MagicMock()
    context = {"exception": ValueError("real problem"), "handle": _OtherHandle()}

    _handler(loop, context)

    loop.default_exception_handler.assert_called_once_with(context)
