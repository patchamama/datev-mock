package com.elo.datevmock.store;

import java.util.Set;

/**
 * Ports {@code app/routers/accounting.py::_validate_reference}: a shared
 * write-side FK check raising a 422-equivalent when a body field references
 * an id/number absent from the current scope's candidate set. {@code null}/
 * omitted values are always left unvalidated (an optional reference field
 * the caller didn't set).
 */
public final class ReferenceValidation {

    private ReferenceValidation() {
    }

    public static void validateReference(Object value, Set<?> candidates, String fieldName) {
        if (value != null && !candidates.contains(value)) {
            throw new ValidationException(
                    fieldName + ": no matching record found for '" + value + "' in this scope");
        }
    }
}
