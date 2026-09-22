"""RED-phase tests for the mutable in-memory data store (`app/data_store.py`).

`app/data_store.py` does not exist yet; this file is expected to fail on
collection with `ModuleNotFoundError` until S2 (GREEN phase) implements it.
See `odd/tasks/datev-mock-settings.md` for the planned contract this test
file is designing.

Cardinality: `app/fake_data.py` generates 18 `ClientResource` (master-data)
records and 8 `Client` (accounting) records by default — confirmed by
reading `_generate_client_resources(count: int = 18)` and
`_generate_accounting_clients(count: int = 8)`, and their module-level call
sites (`CLIENT_RESOURCES = _generate_client_resources()`,
`ACCOUNTING_CLIENTS = _generate_accounting_clients()`), both called with no
override.

Contract under test (settled here, for the GREEN implementer):
  - Module-level functions (not a class) on `app.data_store`, operating on
    process-lifetime mutable state seeded from `app.fake_data` at import.
  - `list_master_data()` / `list_accounting_clients()` return the current
    records.
  - `add_master_data(fields: dict)` / `add_accounting_client(fields: dict)`
    take a plain dict of field values, always generate a fresh server-side
    `Id` (ignoring/overwriting any `"Id"` key the caller supplies), and
    return the created record.
  - `update_master_data(id, fields: dict)` / `update_accounting_client(id,
    fields: dict)` merge the given fields into the existing record (partial
    update — untouched fields keep their previous value) and raise
    `KeyError` when `id` is not found.
  - `delete_master_data(id)` / `delete_accounting_client(id)` remove the
    record; deleting an unknown `id` is a clean no-op (does not raise).
  - `reset()` restores both datasets to a freshly generated dataset with the
    same cardinality as `app/fake_data.py` produces (18 / 8).
"""
from __future__ import annotations

import pytest

from app import data_store

MASTER_DATA_COUNT = 18
ACCOUNTING_COUNT = 8


@pytest.fixture(autouse=True)
def _reset_store():
    """Every test starts from (and leaves behind) the fresh generated dataset."""
    data_store.reset()
    yield
    data_store.reset()


# --- master-data ---


def test_list_master_data_returns_current_records():
    records = data_store.list_master_data()
    assert len(records) == MASTER_DATA_COUNT


def test_add_master_data_generates_fresh_id_and_appears_in_listing():
    before_ids = {r.Id for r in data_store.list_master_data()}

    created = data_store.add_master_data(
        {"Name": "Testfirma GmbH", "Number": 9999, "Status": "active", "Type": "legal_person"}
    )

    assert created.Id
    assert created.Id not in before_ids

    after = data_store.list_master_data()
    assert len(after) == MASTER_DATA_COUNT + 1
    assert any(r.Id == created.Id for r in after)


def test_add_master_data_ignores_caller_supplied_id():
    created = data_store.add_master_data(
        {
            "Id": "caller-supplied-id",
            "Name": "X",
            "Number": 1,
            "Status": "active",
            "Type": "legal_person",
        }
    )
    assert created.Id != "caller-supplied-id"


def test_update_master_data_changes_only_the_targeted_record():
    records = data_store.list_master_data()
    target, other = records[0], records[1]
    other_name_before = other.Name

    updated = data_store.update_master_data(target.Id, {"Name": "Renamed GmbH"})

    assert updated.Id == target.Id
    assert updated.Name == "Renamed GmbH"

    refreshed_other = next(r for r in data_store.list_master_data() if r.Id == other.Id)
    assert refreshed_other.Name == other_name_before


def test_update_master_data_leaves_unspecified_fields_untouched():
    target = data_store.list_master_data()[0]
    number_before = target.Number

    updated = data_store.update_master_data(target.Id, {"Name": "Renamed Only"})

    assert updated.Number == number_before


def test_update_master_data_unknown_id_raises_key_error():
    with pytest.raises(KeyError):
        data_store.update_master_data("does-not-exist", {"Name": "X"})


def test_delete_master_data_removes_record():
    target = data_store.list_master_data()[0]

    data_store.delete_master_data(target.Id)

    remaining_ids = {r.Id for r in data_store.list_master_data()}
    assert target.Id not in remaining_ids
    assert len(data_store.list_master_data()) == MASTER_DATA_COUNT - 1


def test_delete_master_data_unknown_id_is_a_clean_noop():
    before = len(data_store.list_master_data())

    data_store.delete_master_data("does-not-exist")  # must not raise

    assert len(data_store.list_master_data()) == before


def test_reset_master_data_restores_original_cardinality():
    data_store.add_master_data(
        {"Name": "Extra", "Number": 1, "Status": "active", "Type": "legal_person"}
    )
    target = data_store.list_master_data()[0]
    data_store.delete_master_data(target.Id)

    data_store.reset()

    assert len(data_store.list_master_data()) == MASTER_DATA_COUNT


# --- accounting ---


def test_list_accounting_clients_returns_current_records():
    records = data_store.list_accounting_clients()
    assert len(records) == ACCOUNTING_COUNT


def test_add_accounting_client_generates_fresh_id_and_appears_in_listing():
    before_ids = {r.Id for r in data_store.list_accounting_clients()}

    created = data_store.add_accounting_client({"Name": "Testkunde AG", "Number": 88888})

    assert created.Id
    assert created.Id not in before_ids

    after = data_store.list_accounting_clients()
    assert len(after) == ACCOUNTING_COUNT + 1
    assert any(r.Id == created.Id for r in after)


def test_add_accounting_client_ignores_caller_supplied_id():
    created = data_store.add_accounting_client(
        {"Id": "caller-supplied-id", "Name": "X", "Number": 1}
    )
    assert created.Id != "caller-supplied-id"


def test_update_accounting_client_changes_only_the_targeted_record():
    records = data_store.list_accounting_clients()
    target, other = records[0], records[1]
    other_name_before = other.Name

    updated = data_store.update_accounting_client(target.Id, {"Name": "Renamed AG"})

    assert updated.Id == target.Id
    assert updated.Name == "Renamed AG"

    refreshed_other = next(r for r in data_store.list_accounting_clients() if r.Id == other.Id)
    assert refreshed_other.Name == other_name_before


def test_update_accounting_client_unknown_id_raises_key_error():
    with pytest.raises(KeyError):
        data_store.update_accounting_client("does-not-exist", {"Name": "X"})


def test_delete_accounting_client_removes_record():
    target = data_store.list_accounting_clients()[0]

    data_store.delete_accounting_client(target.Id)

    remaining_ids = {r.Id for r in data_store.list_accounting_clients()}
    assert target.Id not in remaining_ids
    assert len(data_store.list_accounting_clients()) == ACCOUNTING_COUNT - 1


def test_delete_accounting_client_unknown_id_is_a_clean_noop():
    before = len(data_store.list_accounting_clients())

    data_store.delete_accounting_client("does-not-exist")  # must not raise

    assert len(data_store.list_accounting_clients()) == before


def test_reset_accounting_restores_original_cardinality():
    data_store.add_accounting_client({"Name": "Extra", "Number": 1})
    target = data_store.list_accounting_clients()[0]
    data_store.delete_accounting_client(target.Id)

    data_store.reset()

    assert len(data_store.list_accounting_clients()) == ACCOUNTING_COUNT


def test_reset_restores_both_datasets_together():
    data_store.add_master_data(
        {"Name": "Extra MD", "Number": 1, "Status": "active", "Type": "legal_person"}
    )
    data_store.add_accounting_client({"Name": "Extra Acct", "Number": 1})

    data_store.reset()

    assert len(data_store.list_master_data()) == MASTER_DATA_COUNT
    assert len(data_store.list_accounting_clients()) == ACCOUNTING_COUNT
