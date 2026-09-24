package com.elo.datevmock.xml;

import com.elo.datevmock.model.CostSystem;

import java.util.List;
import java.util.Set;

/**
 * Ports {@code app/xml_serializers.py::serialize_cost_systems}. Repeated
 * element is {@code CostSystems} (plural) -- confirmed real shape, not the
 * generically-expected singular.
 */
public final class CostSystemXmlSerializer {

    private CostSystemXmlSerializer() {
    }

    private static final List<String> FIELD_ORDER = List.of(
            "id",
            "parent",
            "membersToSerialize",
            "costField",
            "isActivatedForPostings",
            "number",
            "shortName"
    );

    public static String serialize(List<CostSystem> records) {
        StringBuilder body = new StringBuilder();
        for (CostSystem record : records) {
            body.append(DatevXmlRenderer.renderRecord(
                    record, FIELD_ORDER, "CostSystems", DatevXmlRenderer.genericNsAttrResolver(Set.of(), "")));
        }
        return DatevXmlRenderer.wrapArray("ArrayOfCostSystems", Namespaces.COST_SYSTEMS_NS, body.toString());
    }
}
