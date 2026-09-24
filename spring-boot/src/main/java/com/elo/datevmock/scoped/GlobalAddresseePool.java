package com.elo.datevmock.scoped;

import java.util.List;

/**
 * Placeholder for the global {@code Addressee.id} list that
 * {@code app/scoped_data.py::get_creditors_for_scope} cross-references
 * (architecture decision #4 of {@code odd/tasks/datev-mock-referential-integrity.md}):
 * master data isn't scoped, so a creditor's {@code addresseeId} deliberately
 * reaches into a client-independent, global pool rather than a per-scope one.
 *
 * <p>The real {@code Addressee} model/master-data domain is SB5's scope
 * (master-data API parity), not SB3's. Until SB5 ports it, this fixed id
 * pool stands in for "the global addressee id list" so SB3 can prove the
 * real cross-reference *mechanism* (a creditor's {@code addresseeId} always
 * points at a real id from this pool) without inventing the full Addressee
 * record shape prematurely. SB5 should replace this class's role with the
 * real generated {@code Addressee} list once it exists.
 */
final class GlobalAddresseePool {

    private GlobalAddresseePool() {
    }

    static final List<String> ADDRESSEE_IDS = List.of(
            "ADR-00001", "ADR-00002", "ADR-00003", "ADR-00004", "ADR-00005",
            "ADR-00006", "ADR-00007", "ADR-00008", "ADR-00009", "ADR-00010"
    );
}
