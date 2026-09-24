package com.elo.datevmock.xml;

import com.elo.datevmock.model.CostCenter;

import java.util.List;
import java.util.Set;

/** Ports {@code app/xml_serializers.py::serialize_cost_centers}. */
public final class CostCenterXmlSerializer {

    private CostCenterXmlSerializer() {
    }

    public static String serialize(List<CostCenter> records) {
        StringBuilder body = new StringBuilder();
        for (CostCenter record : records) {
            body.append(DatevXmlRenderer.renderRecord(
                    record,
                    CostCenter.XML_FIELD_ORDER,
                    "CostCenter",
                    DatevXmlRenderer.genericNsAttrResolver(Set.of(), "")));
        }
        return DatevXmlRenderer.wrapArray("ArrayOfCostCenter", Namespaces.COST_CENTER_NS, body.toString());
    }
}
