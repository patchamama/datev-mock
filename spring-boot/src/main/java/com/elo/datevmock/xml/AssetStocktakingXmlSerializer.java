package com.elo.datevmock.xml;

import com.elo.datevmock.model.AssetStocktaking;

import java.util.List;
import java.util.Set;

/** Ports {@code app/xml_serializers.py::serialize_assets_stocktakings}. */
public final class AssetStocktakingXmlSerializer {

    private AssetStocktakingXmlSerializer() {
    }

    public static String serialize(List<AssetStocktaking> records) {
        StringBuilder body = new StringBuilder();
        for (AssetStocktaking record : records) {
            body.append(DatevXmlRenderer.renderRecord(
                    record,
                    AssetStocktaking.XML_FIELD_ORDER,
                    "AssetStocktaking",
                    DatevXmlRenderer.genericNsAttrResolver(Set.of(), "")));
        }
        return DatevXmlRenderer.wrapArray("ArrayOfAssetStocktaking", Namespaces.ASSET_STOCKTAKING_NS, body.toString());
    }
}
