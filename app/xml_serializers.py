"""Hand-built XML rendering for the three DATEV DataContractSerializer shapes.

Built with plain string templates (not `xml.etree.ElementTree`) because the
real contract mixes a root-level default namespace with several *per-field*
namespace overrides (bare `xmlns="..."` re-declarations plus unused `d3p1`
prefixes) that ElementTree's serializer cannot reproduce byte-for-byte — it
always hoists namespaces to auto-generated `ns0`/`ns1` prefixes instead of
re-declaring a bare default per element. String templates give full control
over the exact shape while still producing well-formed XML (verified by the
test suite's own `ET.fromstring` round-trip).
"""
from __future__ import annotations

from xml.sax.saxutils import escape

from app.models import (
    CLIENT_FIELD_ORDER,
    CLIENT_RESOURCE_FIELD_ORDER,
    Client,
    ClientResource,
    Echo,
)

XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
SERVICEBUS_NS = "http://xml.datev.de/Framework/ServiceBus/Contracts/V01"
CONNECT_CONTRACTS_NS = "http://schemas.datacontract.org/2004/07/Datev.Connect.Contracts"
ARRAYS_NS = "http://schemas.microsoft.com/2003/10/Serialization/Arrays"

ECHO_NS = "http://schemas.datacontract.org/2004/07/Datev.ApplicationHost.Server.DataObjects"
MASTER_DATA_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Sdd.Connect.PlugIn.Contracts.Resources"
)
ACCOUNTING_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts.Clients"
)
ACCOUNTING_PRODUCTIVITIES_NS = (
    "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts.Productivities"
)

XML_DECLARATION = '<?xml version="1.0" encoding="utf-8"?>'


def _render_field(name: str, value: object, ns_attr: str = "") -> str:
    if value is None:
        return f'<{name}{ns_attr} i:nil="true"/>'
    return f"<{name}{ns_attr}>{escape(str(value))}</{name}>"


def _master_data_ns_attr(field_name: str) -> str:
    if field_name in ("Id", "Parent"):
        return f' xmlns="{SERVICEBUS_NS}"'
    if field_name == "membersToSerialize":
        return f' xmlns:d3p1="{ARRAYS_NS}" xmlns="{CONNECT_CONTRACTS_NS}"'
    return ""


def _accounting_ns_attr(field_name: str) -> str:
    if field_name in ("Id", "Parent"):
        return f' xmlns="{SERVICEBUS_NS}"'
    if field_name == "membersToSerialize":
        return f' xmlns:d3p1="{ARRAYS_NS}" xmlns="{CONNECT_CONTRACTS_NS}"'
    if field_name == "AccountingProductivities":
        return f' xmlns:d3p1="{ACCOUNTING_PRODUCTIVITIES_NS}"'
    return ""


def _serialize_client_resource(record: ClientResource) -> str:
    fields = "".join(
        _render_field(name, getattr(record, name), _master_data_ns_attr(name))
        for name in CLIENT_RESOURCE_FIELD_ORDER
    )
    return f"<ClientResource>{fields}</ClientResource>"


def serialize_client_resources(records: list[ClientResource]) -> str:
    body = "".join(_serialize_client_resource(r) for r in records)
    return (
        f"{XML_DECLARATION}"
        f'<ArrayOfClientResource xmlns:i="{XSI_NS}" xmlns="{MASTER_DATA_NS}">'
        f"{body}"
        "</ArrayOfClientResource>"
    )


def _serialize_client(record: Client) -> str:
    fields = "".join(
        _render_field(name, getattr(record, name), _accounting_ns_attr(name))
        for name in CLIENT_FIELD_ORDER
    )
    return f"<Client>{fields}</Client>"


def serialize_clients(records: list[Client]) -> str:
    body = "".join(_serialize_client(r) for r in records)
    return (
        f"{XML_DECLARATION}"
        f'<ArrayOfClient xmlns:i="{XSI_NS}" xmlns="{ACCOUNTING_NS}">'
        f"{body}"
        "</ArrayOfClient>"
    )


def serialize_echo(echo: Echo) -> str:
    return (
        f"{XML_DECLARATION}"
        f'<Echo xmlns:i="{XSI_NS}" xmlns="{ECHO_NS}">'
        f"<echo_message>{escape(echo.echo_message)}</echo_message>"
        f"<id>{escape(echo.id)}</id>"
        "</Echo>"
    )
