package com.elo.datevmock.model;

import java.util.List;

/**
 * Ports {@code app/models.py::ClientResource} — exact 42-field layout, in
 * order. Field order matters for {@link com.elo.datevmock.xml.DatevXmlRenderer},
 * which renders in {@link #XML_FIELD_ORDER} order to match the real
 * DATEV Sdd.Connect contract's element order.
 */
public record ClientResource(
        String id,
        String accountHolderForBilling,
        String authorizedRecipientForLegalPerson,
        String authorizedRecipientForNaturalPerson,
        String clientSince,
        String clientTo,
        String correspondenceRecipient,
        String differingName,
        String establishmentId,
        String establishmentName,
        String establishmentNumber,
        String establishmentShortName,
        String functionalAreaId,
        String functionalAreaName,
        String functionalAreaShortName,
        String identificationCheckedOn,
        String identificationComment,
        String identificationStatus,
        String invoiceRecipients,
        String leadId,
        String legalPersonId,
        String name,
        String naturalPersonId,
        String note,
        int number,
        String onlineRevision,
        String organizationId,
        String organizationName,
        String organizationNumber,
        String revision,
        String riskAssessment,
        String riskAssessmentDate,
        String riskAssessmentReason,
        String status,
        String stayRegistered,
        String timestamp,
        String transparencyRegister,
        String transparencyRegisterCheckedOn,
        String transparencyRegisterComment,
        String type
) {

    /**
     * Ports {@code app/models.py::CLIENT_RESOURCE_FIELD_ORDER} exactly.
     * {@code parent}/{@code membersToSerialize} are synthetic (no record
     * component) — {@link com.elo.datevmock.xml.DatevXmlRenderer} always
     * renders them {@code i:nil}, same convention as {@link CostCenter}.
     */
    public static final List<String> XML_FIELD_ORDER = List.of(
            "id",
            "parent",
            "membersToSerialize",
            "accountHolderForBilling",
            "authorizedRecipientForLegalPerson",
            "authorizedRecipientForNaturalPerson",
            "clientSince",
            "clientTo",
            "correspondenceRecipient",
            "differingName",
            "establishmentId",
            "establishmentName",
            "establishmentNumber",
            "establishmentShortName",
            "functionalAreaId",
            "functionalAreaName",
            "functionalAreaShortName",
            "identificationCheckedOn",
            "identificationComment",
            "identificationStatus",
            "invoiceRecipients",
            "leadId",
            "legalPersonId",
            "name",
            "naturalPersonId",
            "note",
            "number",
            "onlineRevision",
            "organizationId",
            "organizationName",
            "organizationNumber",
            "revision",
            "riskAssessment",
            "riskAssessmentDate",
            "riskAssessmentReason",
            "status",
            "stayRegistered",
            "timestamp",
            "transparencyRegister",
            "transparencyRegisterCheckedOn",
            "transparencyRegisterComment",
            "type"
    );
}
