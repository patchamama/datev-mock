package com.elo.datevmock.model;

/**
 * DMS document metadata, ported from {@code app.models.Document}: {@code id}
 * is a real GUID, {@code domainId} ties the document to a {@link Domain}
 * tree node.
 */
public record Document(
        String id,
        String name,
        double amount,
        String documentClass,
        String domainId,
        String createdAt,
        String modifiedAt) {
}
