package com.elo.datevmock.store;

import org.junit.jupiter.api.Test;

import java.util.Set;

import static org.junit.jupiter.api.Assertions.assertDoesNotThrow;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Ports {@code app/routers/accounting.py::_validate_reference}: a write-body
 * field referencing an id/number that doesn't exist in the current scope's
 * candidate set (generated + stored) fails with a 422-equivalent, exactly
 * what a subsequent GET in the same scope would/wouldn't show. {@code null}/
 * omitted values are always left unvalidated. SB5-SB7 controllers will call
 * this from their own request handlers once they exist.
 */
class ReferenceValidationTest {

    @Test
    void doesNotThrowWhenValueIsNull() {
        assertDoesNotThrow(() -> ReferenceValidation.validateReference(null, Set.of("a", "b"), "addressee_id"));
    }

    @Test
    void doesNotThrowWhenValueIsAmongCandidates() {
        assertDoesNotThrow(() -> ReferenceValidation.validateReference("a", Set.of("a", "b"), "addressee_id"));
    }

    @Test
    void throwsValidationExceptionWithStatus422WhenValueIsNotAmongCandidates() {
        ValidationException ex = assertThrows(ValidationException.class,
                () -> ReferenceValidation.validateReference("missing", Set.of("a", "b"), "addressee_id"));
        assertEquals(422, ex.statusCode());
        assertTrue(ex.getMessage().contains("addressee_id"));
        assertTrue(ex.getMessage().contains("missing"));
    }
}
