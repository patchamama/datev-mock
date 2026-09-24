package com.elo.datevmock.model;

/**
 * DMS {@code domain}/{@code folder}/{@code register} tree node, ported from
 * {@code app.models.Domain}. Modeled as a flat adjacency list ({@code
 * parentId} reference): {@code type} distinguishes the three tree levels,
 * {@code parentId} is present on every {@code folder}/{@code register}
 * record and absent (not {@code null}) on root {@code type == "domain"}
 * records — Jackson's {@code NON_NULL} inclusion (see {@code
 * DatevJsonMapper}) already drops a {@code null} field entirely, so a plain
 * {@code null} here serializes as field absence, matching the FastAPI
 * contract with no extra code.
 */
public record Domain(String id, String name, String type, String parentId) {
}
