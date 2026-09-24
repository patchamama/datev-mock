package com.elo.datevmock.store;

/**
 * Ports the 422 {@code fastapi.HTTPException} raised by
 * {@code app/routers/accounting.py::_validate_reference}. A future
 * controller (SB5-SB7) maps this to an HTTP 422 response the same way
 * FastAPI's exception handler does.
 */
public class ValidationException extends RuntimeException {

    private final int statusCode;

    public ValidationException(String message) {
        this(message, 422);
    }

    public ValidationException(String message, int statusCode) {
        super(message);
        this.statusCode = statusCode;
    }

    public int statusCode() {
        return statusCode;
    }
}
