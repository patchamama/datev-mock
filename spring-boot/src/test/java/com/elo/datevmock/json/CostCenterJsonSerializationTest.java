package com.elo.datevmock.json;

import com.elo.datevmock.model.CostCenter;
import com.elo.datevmock.model.CostRate;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Ports the JSON-shape assertions from
 * {@code tests/test_accounting_fiscal_structure.py}
 * (`test_cost_center_cost_rates_use_integer_encoded_dates`,
 * `test_cost_center_cost_rates_are_omitted_in_legacy_mode_by_default`):
 * snake_case keys, null fields entirely absent (not `null`), integer-encoded
 * `valid_from`/`valid_to`, and `cost_rates` genuinely missing -- not `null`,
 * not `[]` -- in legacy mode.
 */
class CostCenterJsonSerializationTest {

    private final ObjectMapper mapper = DatevJsonMapper.create();

    private static CostCenter sample() {
        return new CostCenter(
                "1", "Verwaltung", "VW", "2020-01-01T00:00:00.000+01:00",
                List.of(new CostRate(20161201, 20991231, 1.5)),
                List.of(),
                null, null, null, null, null, null, null);
    }

    @Test
    void modernModeIncludesCostRatesWithSnakeCaseIntegerEncodedDates() throws Exception {
        JsonNode node = mapper.valueToTree(sample());

        assertEquals("1", node.get("id").asText());
        assertEquals("Verwaltung", node.get("long_name").asText());
        assertTrue(node.has("cost_rates"));
        JsonNode rate = node.get("cost_rates").get(0);
        assertEquals(20161201, rate.get("valid_from").asInt());
        assertEquals(20991231, rate.get("valid_to").asInt());
        assertEquals(1.5, rate.get("rate").asDouble());
    }

    @Test
    void nullOptionalFieldsAreEntirelyAbsentNotNullValued() {
        JsonNode node = mapper.valueToTree(sample());
        assertFalse(node.has("date_last_modification"));
        assertFalse(node.has("email"));
        assertFalse(node.has("note"));
    }

    @Test
    void legacyModeOmitsCostRatesEntirely() {
        CostCenter legacy = sample().withoutCostRates();
        JsonNode node = mapper.valueToTree(legacy);
        assertFalse(node.has("cost_rates"));
    }
}
