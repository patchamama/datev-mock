"""RED-phase tests for the DMS (Document Management System) API endpoints
(epic `datev-mock-extended-endpoints`, Phase C).

**Fidelity disclaimer (read this before touching the schema below):** unlike
Phases A and B, there is **no official OpenAPI spec** for DMS anywhere in the
bundled/extracted material (confirmed via a full-text grep of both spec
files — zero "dms" matches). The *only* ground truth is two one-line table
rows in `examples/DATEV_Mock_Server_Reference.md`'s "DMS API" section:

    GET /datev/api/dms/v1/domains    -> "Domain/folder/register tree, e.g. `Unternehmen`."
    GET /datev/api/dms/v1/documents  -> "Document metadata including amount, class, GUIDs, and timestamps."

Everything below the endpoint paths and those two descriptions is a
**self-designed, invented schema** — a deliberate, explicitly-flagged
exception to this epic's normal "never guess, only build from confirmed
evidence" rule (see the epic doc's Phase C section and its "Ground truth for
this epic" note). Nothing else in the reference doc models a comparable
hierarchical/tree resource to crib field names from (the closest analog,
`cost-centers`, is a flat list with no parent/child relationship), so the
tree shape here is common-sense DMS design, not extracted evidence.

Schema design and reasoning:

- **`domains`** — modeled as a **flat list with parent references**
  (`parent_id`), not deep JSON nesting. A flat list is trivially testable
  (no recursive-structure assertions needed) and is a completely standard,
  reasonable way to represent a tree over HTTP (adjacency-list style).
  Each record has:
    - `id` (str, non-empty) — the node's own identifier.
    - `name` (str, non-empty) — e.g. "Unternehmen" (the reference doc's own
      example), a folder like "Belege", or a register like "Rechnungseingang".
    - `type` (`domain` | `folder` | `register`) — distinguishes the three
      tree levels named literally in the description ("Domain/folder/register
      tree"), so this enum is the least speculative part of the design.
    - `parent_id` (str, optional) — present and referencing another record's
      `id` for every non-root (`folder`/`register`) record; **absent**
      (not `null`) for root `domain`-level records, consistent with this
      epic's established "optionality = field absence, never `nullable`"
      convention (see Phase A/B precedent in `master_data.py`/`accounting.py`).

- **`documents`** — per the description's four explicitly named facets
  (amount, class, GUIDs, timestamps), each record has:
    - `id` (str) — a real GUID (the description says "GUIDs" plural, so IDs
      specifically are asserted to be UUID-parseable, not just non-empty
      strings — see `test_document_id_is_a_guid`).
    - `name` (str, non-empty) — an obviously-necessary human-readable title;
      not mentioned in the description but a document with no title/filename
      would be an unreasonably incomplete "document metadata" record.
    - `amount` (numeric) — the description's "amount" facet; a plausible
      invoice/receipt amount.
    - `document_class` (str) — the description's "class" facet; a small
      invented enum (`invoice`, `receipt`, `contract`, `delivery_note`) since
      no real DATEV DMS document-class vocabulary is available anywhere in
      this repo's evidence.
    - `domain_id` (str) — ties this endpoint to `domains` by referencing one
      of its `id`s, which is a reasonable minimal-usefulness addition (a
      document with no folder/register location would be a DMS record with
      no place in the tree) rather than an invented independent field.
    - `created_at` / `modified_at` (str timestamps) — the description's
      "timestamps" facet (plural), hence two fields, not one.

Per this epic's cross-phase decisions (`odd/tasks/datev-mock-extended-endpoints.md`):
JSON-only, `Content-Type: application/json`, bare JSON arrays (never a
pagination wrapper), and no query-param semantics (`select`/`filter`/`skip`/
`top`/`expand`) implemented — both confirmed with a zero-query-param baseline
test per endpoint, same as every other phase.

Because this schema is self-designed rather than spec-derived, these tests
intentionally assert *shape and types*, not exact invented values (no
hardcoded fake name/amount is asserted anywhere) — this is a reasonable
invented contract for the GREEN writer to build fake data against, not a
verified DATEV API contract.

These tests intentionally import `DOMAINS_ENDPOINT` / `DOCUMENTS_ENDPOINT`
directly from `app.routers.dms`, a module that does not exist yet at all
(unlike Phases A/B, which extended an existing router module). This import
is expected to fail at collection time (`ModuleNotFoundError`/`ImportError`)
until the GREEN-phase router work (task C1) creates `app/routers/dms.py` and
these constants — that failure is the correct RED signal for this task; do
not add a try/except around it to hide it.
"""
from __future__ import annotations

import uuid

from app.routers.dms import DOCUMENTS_ENDPOINT, DOMAINS_ENDPOINT

MIN_DOMAIN_RECORDS = 5
MIN_DOCUMENT_RECORDS = 5

_DOMAIN_TYPES = {"domain", "folder", "register"}
_DOCUMENT_CLASSES = {"invoice", "receipt", "contract", "delivery_note"}


def _get_domains(client) -> list[dict]:
    response = client.get(DOMAINS_ENDPOINT)
    return response.json()


def _get_documents(client) -> list[dict]:
    response = client.get(DOCUMENTS_ENDPOINT)
    return response.json()


# --- GET /datev/api/dms/v1/domains ---


def test_domains_returns_200(client):
    response = client.get(DOMAINS_ENDPOINT)
    assert response.status_code == 200


def test_domains_content_type_is_json(client):
    response = client.get(DOMAINS_ENDPOINT)
    assert response.headers["content-type"].startswith("application/json")


def test_domains_endpoint_requires_no_query_params(client):
    """Baseline check for the cross-phase "no select/filter/skip/top" decision:
    calling with no query params at all must work fine."""
    response = client.get(DOMAINS_ENDPOINT, params={})
    assert response.status_code == 200


def test_domains_body_is_bare_array_with_minimum_records(client):
    records = _get_domains(client)
    assert isinstance(records, list)
    assert len(records) >= MIN_DOMAIN_RECORDS, (
        f"expected at least {MIN_DOMAIN_RECORDS} domain records, got {len(records)}"
    )


def test_domain_record_has_core_fields(client):
    records = _get_domains(client)
    assert records, "no domain records returned"

    for record in records:
        assert isinstance(record.get("id"), str) and record["id"].strip()
        assert isinstance(record.get("name"), str) and record["name"].strip()
        assert record.get("type") in _DOMAIN_TYPES


def test_domain_dataset_contains_multiple_tree_levels(client):
    """Proves the fake dataset actually varies `type` across tree levels, not
    just declares the enum — a dataset of a single level would let the
    parent/child tests below pass vacuously."""
    records = _get_domains(client)
    types_seen = {record.get("type") for record in records}
    assert len(types_seen) >= 2, (
        f"expected at least 2 distinct domain/folder/register levels, saw {types_seen}"
    )


def test_root_domain_records_have_no_parent_id(client):
    """Contract for GREEN: a top-level `type == "domain"` record is a tree
    root and must omit `parent_id` entirely (field absence, not `null`,
    matching this epic's established optionality convention)."""
    records = _get_domains(client)
    root_records = [r for r in records if r.get("type") == "domain"]
    assert root_records, "no root-level (type == domain) records returned"

    for record in root_records:
        assert "parent_id" not in record


def test_non_root_domain_records_have_parent_id_referencing_a_known_id(client):
    """Contract for GREEN: every `folder`/`register` record must carry a
    `parent_id` that resolves to another record's `id` in the same
    response — proving this is an actual (if flat) tree, not just decorative
    `type` labels."""
    records = _get_domains(client)
    known_ids = {record["id"] for record in records}
    non_root_records = [r for r in records if r.get("type") in {"folder", "register"}]
    assert non_root_records, "no folder/register records returned"

    for record in non_root_records:
        assert isinstance(record.get("parent_id"), str) and record["parent_id"].strip()
        assert record["parent_id"] in known_ids


# --- GET /datev/api/dms/v1/documents ---


def test_documents_returns_200(client):
    response = client.get(DOCUMENTS_ENDPOINT)
    assert response.status_code == 200


def test_documents_content_type_is_json(client):
    response = client.get(DOCUMENTS_ENDPOINT)
    assert response.headers["content-type"].startswith("application/json")


def test_documents_endpoint_requires_no_query_params(client):
    response = client.get(DOCUMENTS_ENDPOINT, params={})
    assert response.status_code == 200


def test_documents_body_is_bare_array_with_minimum_records(client):
    records = _get_documents(client)
    assert isinstance(records, list)
    assert len(records) >= MIN_DOCUMENT_RECORDS, (
        f"expected at least {MIN_DOCUMENT_RECORDS} document records, got {len(records)}"
    )


def test_document_record_has_core_fields(client):
    records = _get_documents(client)
    assert records, "no document records returned"

    for record in records:
        assert isinstance(record.get("id"), str) and record["id"].strip()
        assert isinstance(record.get("name"), str) and record["name"].strip()
        assert isinstance(record.get("amount"), (int, float))
        assert record.get("document_class") in _DOCUMENT_CLASSES
        assert isinstance(record.get("created_at"), str) and record["created_at"].strip()
        assert isinstance(record.get("modified_at"), str) and record["modified_at"].strip()


def test_document_id_is_a_guid(client):
    """The description explicitly says "GUIDs" (plural), so document `id`s
    specifically are asserted to be UUID-parseable, not just non-empty
    strings (unlike e.g. `domains[].id`, which the description gives no such
    guarantee for)."""
    records = _get_documents(client)
    assert records, "no document records returned"

    for record in records:
        uuid.UUID(record["id"])  # raises ValueError if not a valid GUID


def test_document_amount_is_a_plausible_positive_number(client):
    records = _get_documents(client)
    assert records, "no document records returned"

    for record in records:
        assert record["amount"] > 0


def test_document_dataset_contains_multiple_classes(client):
    """Proves the fake dataset actually varies `document_class`, not just
    declares the enum — a dataset of a single class would be a weaker,
    vacuous fixture."""
    records = _get_documents(client)
    classes_seen = {record.get("document_class") for record in records}
    assert len(classes_seen) >= 2, (
        f"expected at least 2 distinct document classes, saw {classes_seen}"
    )


def test_document_has_domain_id_referencing_a_known_domain(client):
    """Ties the two DMS endpoints together sensibly: every document belongs
    to a node (domain/folder/register) in the `domains` tree."""
    documents = _get_documents(client)
    domains = _get_domains(client)
    known_domain_ids = {domain["id"] for domain in domains}
    assert documents, "no document records returned"

    for record in documents:
        assert isinstance(record.get("domain_id"), str) and record["domain_id"].strip()
        assert record["domain_id"] in known_domain_ids
