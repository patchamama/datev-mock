package com.elo.datevmock.json;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.databind.PropertyNamingStrategies;
import com.fasterxml.jackson.databind.json.JsonMapper;

/**
 * JSON projection matching FastAPI's {@code app/routers/accounting.py::_to_json}
 * (`_strip_none(asdict(record))`): raw dataclass field names (snake_case,
 * not the DATEV XML PascalCase) and {@code None} fields dropped entirely --
 * never emitted as an explicit {@code null}.
 */
public final class DatevJsonMapper {

    private DatevJsonMapper() {
    }

    public static com.fasterxml.jackson.databind.ObjectMapper create() {
        return JsonMapper.builder()
                .propertyNamingStrategy(PropertyNamingStrategies.SNAKE_CASE)
                .serializationInclusion(JsonInclude.Include.NON_NULL)
                .build();
    }
}
