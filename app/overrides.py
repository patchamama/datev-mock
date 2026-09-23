"""In-memory, per-process store for custom endpoint-response overrides.

Lets an admin upload an XML or JSON file that is served verbatim instead of
this mock's normal generated response for a specific endpoint. Detection
figures out which endpoint(s) an uploaded file's structure corresponds to;
storage is process-lifetime only (never persisted to disk), consistent with
how `app/data_store.py` already handles in-memory dataset edits.

See `odd/tasks/datev-mock-custom-overrides.md` for the full design (endpoint
key table, fingerprint fields, ambiguous groups) — this module implements
that contract faithfully. Router integration (actually serving overrides
from `diagnostics.py`/`master_data.py`/`accounting.py`/`dms.py`) is a
separate, later task (V3), not implemented here.
"""
from __future__ import annotations

import json
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

# --- detection ---

# The 3 possible XML root tags in this whole mock (namespace prefix, if any,
# is stripped before lookup).
_XML_ROOT_MAP: dict[str, list[str]] = {
    "Echo": ["diagnostics.echo"],
    "ArrayOfClientResource": ["master_data.clients"],
    "ArrayOfClient": ["accounting.clients"],
}

# JSON fingerprints: a set of field names that must ALL be present (extra
# fields are fine) on the first array element (or the top-level object, if
# the payload isn't a list). Several DATEV resources share an identical
# schema, so more than one fingerprint may legitimately match the same
# payload — that produces the 3 documented ambiguous groups.
_FINGERPRINTS: dict[frozenset[str], list[str]] = {
    frozenset({"id", "name", "number"}): ["accounting.clients"],
    frozenset({"type", "status", "timestamp", "current_company_name"}): [
        "master_data.addressees"
    ],
    frozenset({"type", "status", "timestamp", "firstname"}): ["master_data.addressees"],
    frozenset({"bic", "country_code"}): ["master_data.banks"],
    frozenset(
        {"account_system", "currency_code", "legal_form", "taxation_method"}
    ): ["accounting.fiscal_years"],
    frozenset({"short_name", "is_activated_for_postings"}): ["accounting.cost_systems"],
    frozenset({"long_name", "short_name", "creation_date"}): ["accounting.cost_centers"],
    frozenset({"addressee_id", "business_partner_number", "legal_entity_type"}): [
        "accounting.creditors",
        "accounting.debitors",
    ],
    frozenset(
        {"account_number", "caption", "main_function", "main_function_number"}
    ): ["accounting.general_ledger_accounts"],
    frozenset(
        {"amount_debit", "amount_credit", "evidence_type", "debit_credit_identifier"}
    ): [
        "accounting.accounts_payable",
        "accounting.accounts_payable_condense",
        "accounting.accounts_receivable_condense",
    ],
    frozenset(
        {
            "accounting_sequence_id",
            "record_type",
            "accounting_reason",
            "date_from",
            "date_to",
        }
    ): ["accounting.accounting_sequences_processed"],
    frozenset({"tax_rate", "is_tax_rate_selectable"}): [
        "accounting.accounting_transaction_keys"
    ],
    frozenset({"asset_number", "inventory_number"}): ["accounting.assets_stocktakings"],
    frozenset(
        {"assignment_criteria", "posting_proposal_information", "uncertain_label"}
    ): [
        "accounting.posting_proposal_rules_incoming",
        "accounting.posting_proposal_rules_outgoing",
    ],
    frozenset({"caption", "due_type"}): ["accounting.terms_of_payment"],
    frozenset({"name", "type"}): ["dms.domains"],
    frozenset(
        {"amount", "document_class", "domain_id", "created_at", "modified_at"}
    ): ["dms.documents"],
}


def _strip_namespace(tag: str) -> str:
    if tag.startswith("{"):
        return tag.split("}", 1)[1]
    return tag


def _try_parse_xml_root(content: str) -> str | None:
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return None
    return _strip_namespace(root.tag)


def _try_parse_json(content: str) -> Any | None:
    try:
        return json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return None


def detect_candidates(content: str) -> list[str]:
    """Return the list of endpoint keys an uploaded file's content matches.

    Empty means no match, one means unambiguous, 2-3 means one of the
    documented structurally-identical resource groups.
    """
    root_tag = _try_parse_xml_root(content)
    if root_tag is not None:
        return list(_XML_ROOT_MAP.get(root_tag, []))

    data = _try_parse_json(content)
    if data is None:
        return []

    if isinstance(data, list):
        if not data:
            return []
        record = data[0]
    else:
        record = data

    if not isinstance(record, dict):
        return []

    fields = set(record.keys())
    matched: list[str] = []
    for required, keys in _FINGERPRINTS.items():
        if required <= fields:
            for key in keys:
                if key not in matched:
                    matched.append(key)
    return matched


def detect_content_type(content: str) -> str | None:
    """Return `"xml"`, `"json"`, or `None` for content that parses as
    neither (mirrors the two-pass order `detect_candidates` uses)."""
    if _try_parse_xml_root(content) is not None:
        return "xml"
    if _try_parse_json(content) is not None:
        return "json"
    return None


# --- storage ---


@dataclass
class Override:
    content: str
    content_type: str
    filename: str
    uploaded_at: str
    enabled: bool = True


_overrides: dict[str, Override] = {}
_pending: dict[str, dict[str, Any]] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def set_override(key: str, content: str, content_type: str, filename: str) -> None:
    _overrides[key] = Override(
        content=content,
        content_type=content_type,
        filename=filename,
        uploaded_at=_now_iso(),
        enabled=True,
    )


def get_active_override(key: str) -> Override | None:
    override = _overrides.get(key)
    if override is not None and override.enabled:
        return override
    return None


def list_overrides() -> dict[str, dict]:
    return {
        key: {
            "content_type": override.content_type,
            "filename": override.filename,
            "uploaded_at": override.uploaded_at,
            "enabled": override.enabled,
        }
        for key, override in _overrides.items()
    }


def set_enabled(key: str, enabled: bool) -> None:
    override = _overrides.get(key)
    if override is not None:
        override.enabled = enabled


def delete_override(key: str) -> None:
    _overrides.pop(key, None)


def clear_all_overrides() -> None:
    """Test-only helper: wipes all stored and pending state."""
    _overrides.clear()
    _pending.clear()


def store_pending(
    content: str, content_type: str, filename: str, candidates: list[str]
) -> str:
    pending_id = str(uuid.uuid4())
    _pending[pending_id] = {
        "content": content,
        "content_type": content_type,
        "filename": filename,
        "candidates": list(candidates),
    }
    return pending_id


def resolve_pending(pending_id: str, key: str) -> None:
    pending = _pending.get(pending_id)
    if pending is None:
        raise ValueError(f"unknown pending upload: {pending_id!r}")
    if key not in pending["candidates"]:
        raise ValueError(
            f"{key!r} is not one of the candidates for pending upload {pending_id!r}"
        )
    set_override(key, pending["content"], pending["content_type"], pending["filename"])
    del _pending[pending_id]
