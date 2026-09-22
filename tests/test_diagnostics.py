"""RED-phase tests for GET /datev/api/diagnostics/v1/echo.

Asserts the mock reproduces the real DATEV `Echo` DataContractSerializer XML
shape: root element `{...ApplicationHost.Server.DataObjects}Echo` with an
`echo_message` in the "echo at DD.MM.YYYY HH:MM:SS" format and a GUID `id`,
freshly generated per call.
"""
from __future__ import annotations

import re
import uuid
import xml.etree.ElementTree as ET

ECHO_NS = "http://schemas.datacontract.org/2004/07/Datev.ApplicationHost.Server.DataObjects"
ECHO_ROOT_TAG = f"{{{ECHO_NS}}}Echo"

ECHO_MESSAGE_RE = re.compile(r"^echo at \d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2}$")
UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)

ENDPOINT = "/datev/api/diagnostics/v1/echo"


def _local_name(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _find_field_text(root: ET.Element, local_name: str) -> str:
    for child in root:
        if _local_name(child.tag) == local_name:
            assert child.text is not None, f"{local_name} has no text content"
            return child.text
    raise AssertionError(f"expected child element {local_name!r} not found under {root.tag}")


def test_echo_returns_200(client):
    response = client.get(ENDPOINT)
    assert response.status_code == 200


def test_echo_content_type_is_xml(client):
    response = client.get(ENDPOINT)
    assert response.headers["content-type"].startswith("application/xml")


def test_echo_body_is_valid_xml(client):
    response = client.get(ENDPOINT)
    # Raises ET.ParseError if malformed - that failure is itself a test failure.
    root = ET.fromstring(response.content)
    assert root is not None


def test_echo_root_tag_matches_datev_contract(client):
    response = client.get(ENDPOINT)
    root = ET.fromstring(response.content)
    assert root.tag == ECHO_ROOT_TAG


def test_echo_message_matches_expected_format(client):
    response = client.get(ENDPOINT)
    root = ET.fromstring(response.content)
    echo_message = _find_field_text(root, "echo_message")
    assert ECHO_MESSAGE_RE.match(echo_message), (
        f"echo_message {echo_message!r} does not match 'echo at DD.MM.YYYY HH:MM:SS'"
    )


def test_echo_id_is_a_valid_guid(client):
    response = client.get(ENDPOINT)
    root = ET.fromstring(response.content)
    echo_id = _find_field_text(root, "id")
    assert UUID_RE.match(echo_id), f"id {echo_id!r} is not a valid GUID"
    # Round-trip through uuid.UUID as a stronger validity check.
    uuid.UUID(echo_id)


def test_echo_id_is_dynamic_across_calls(client):
    first = ET.fromstring(client.get(ENDPOINT).content)
    second = ET.fromstring(client.get(ENDPOINT).content)

    first_id = _find_field_text(first, "id")
    second_id = _find_field_text(second, "id")

    assert first_id != second_id, "echo id must be freshly generated per call, not static"
