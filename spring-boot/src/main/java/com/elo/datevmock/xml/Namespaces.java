package com.elo.datevmock.xml;

/**
 * DataContractSerializer namespace constants, ported 1:1 from
 * {@code app/xml_serializers.py}'s module-level namespace constants.
 */
public final class Namespaces {

    public static final String XML_DECLARATION = "<?xml version=\"1.0\" encoding=\"utf-8\"?>";

    public static final String XSI_NS = "http://www.w3.org/2001/XMLSchema-instance";
    public static final String SERVICEBUS_NS =
            "http://xml.datev.de/Framework/ServiceBus/Contracts/V01";
    public static final String CONNECT_CONTRACTS_NS =
            "http://schemas.datacontract.org/2004/07/Datev.Connect.Contracts";
    public static final String ARRAYS_NS =
            "http://schemas.microsoft.com/2003/10/Serialization/Arrays";

    public static final String ACCOUNTING_COMMON_NS =
            "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts.Common";
    public static final String COST_CENTER_NS =
            "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts.CostCenter";
    public static final String BUSINESS_PARTNERS_NS =
            "http://schemas.datacontract.org/2004/07/Datev.Irw.Connect.Accounting.Contracts.BusinessPartners";
    public static final String MASTER_DATA_NS =
            "http://schemas.datacontract.org/2004/07/Datev.Sdd.Connect.PlugIn.Contracts.Resources";

    private Namespaces() {
    }
}
