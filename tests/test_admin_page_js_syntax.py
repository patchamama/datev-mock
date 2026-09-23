"""Validates that the /admin page's inline JavaScript actually parses.

Regression test for a real bug: an unescaped apostrophe inside a
single-quoted JS string literal ("Couldn't"/"mock's") broke the whole
inline <script> block with `SyntaxError: missing ) after argument list`,
silently preventing every data table and the override catalog from
loading in the browser. Smoke tests that merely check for substrings in
the HTML (as the rest of this file does) can't catch this class of bug —
only actually parsing the JS can. Requires `node` on PATH; the test is
skipped (not failed) if it isn't available, since it's a nice-to-have
extra safety net, not a hard project dependency.
"""
from __future__ import annotations

import re
import shutil
import subprocess

import pytest

ADMIN_PAGE = "/admin"

pytestmark = pytest.mark.skipif(
    shutil.which("node") is None, reason="node.js not available on PATH"
)


def _extract_inline_script(html: str) -> str:
    # The page has one external <script src="...bootstrap...">, then one
    # inline <script>...</script> block with the actual page logic.
    matches = re.findall(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.DOTALL)
    assert matches, "expected at least one inline <script> block with no src attribute"
    return max(matches, key=len)


def test_admin_page_inline_script_is_syntactically_valid_javascript(client, tmp_path):
    html = client.get(ADMIN_PAGE).text
    script = _extract_inline_script(html)

    script_file = tmp_path / "admin_inline.js"
    script_file.write_text(script, encoding="utf-8")

    result = subprocess.run(
        ["node", "--check", str(script_file)],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, (
        f"admin page's inline <script> has a JavaScript syntax error:\n{result.stderr}"
    )
