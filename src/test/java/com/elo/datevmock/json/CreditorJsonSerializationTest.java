package com.elo.datevmock.json;

import com.elo.datevmock.model.Address;
import com.elo.datevmock.model.AddressUsageType;
import com.elo.datevmock.model.Creditor;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertFalse;
import static org.junit.jupiter.api.Assertions.assertTrue;

/**
 * Confirms the same generic {@link DatevJsonMapper} (record-aware,
 * snake_case, null-omitting) correctly handles a nested list-of-objects
 * field with no per-type special-casing -- the JSON-side equivalent of
 * {@code CreditorXmlSerializerTest}'s nested-list/nested-object coverage.
 */
class CreditorJsonSerializationTest {

    private final ObjectMapper mapper = DatevJsonMapper.create();

    private static Creditor sample() {
        Address address = new Address(
                "addr1",
                new AddressUsageType(true, false, false, false, false, false, false),
                null, null, null, null, null, null, null, null, null, null, null,
                null, null, null, null, null, null);
        return new Creditor(
                "c1", 42, "a1", "bp1", "bpr1", "ACME",
                "2020-01-01T00:00:00.000+01:00", true, false, "1", "ACME",
                null, List.of(address), null, null, null, null, null, null, null,
                null, null, null, null, null);
    }

    @Test
    void nestedAddressesListSerializesWithSnakeCaseKeysAndNestedObject() {
        JsonNode node = mapper.valueToTree(sample());
        JsonNode address = node.get("addresses").get(0);
        assertEquals("addr1", address.get("id").asText());
        assertTrue(address.get("address_usage_type").get("is_correspondence_address").asBoolean());
        assertFalse(address.get("address_usage_type").get("is_delivery_address").asBoolean());
    }

    @Test
    void nullOptionalFieldsAreAbsentIncludingNilNestedObjects() {
        JsonNode node = mapper.valueToTree(sample());
        assertFalse(node.has("alternative_search_name"));
        assertFalse(node.has("banks"));
        assertFalse(node.has("legal_person"));
    }
}
