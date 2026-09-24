package com.elo.datevmock.web;

import com.elo.datevmock.store.ValidationException;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;

import java.util.Map;

/** Maps {@link ValidationException} (SB4) to an HTTP 422, ports FastAPI's `HTTPException(422, ...)`. */
@RestControllerAdvice
public class ValidationExceptionHandler {

    @ExceptionHandler(ValidationException.class)
    public ResponseEntity<Map<String, String>> handle(ValidationException exception) {
        return ResponseEntity.status(HttpStatus.valueOf(exception.statusCode()))
                .body(Map.of("detail", exception.getMessage()));
    }
}
