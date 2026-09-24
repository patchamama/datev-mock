package com.elo.datevmock.store;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.nio.file.Path;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;

/**
 * Ports {@code app/db.py}: a generic SQLite-backed write-overlay store, one
 * row per {@code (resourceType, recordId)}, an arbitrary JSON payload per
 * row. A short-lived JDBC connection is opened and closed per call, same
 * choice FastAPI made (simplicity over a shared/locked connection; this
 * mock's traffic volume makes the per-call connect cost irrelevant).
 *
 * <p>Every stored write survives an application restart because it's a real
 * file on disk (verified by {@code StoredRecordStoreTest
 * ::writtenRecordSurvivesASimulatedRestart}, which reopens a fresh instance
 * against the same path) -- there is deliberately no in-memory cache layer
 * here that a restart would need to invalidate.
 */
public class StoredRecordStore {

    private static final String CREATE_TABLE_SQL = """
            CREATE TABLE IF NOT EXISTS stored_records (
                resource_type TEXT NOT NULL,
                record_id TEXT NOT NULL,
                client_id TEXT,
                fiscal_year_id TEXT,
                data_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                PRIMARY KEY (resource_type, record_id)
            )
            """;

    private final String jdbcUrl;
    private final ObjectMapper json = new ObjectMapper();

    public StoredRecordStore(Path dbPath) {
        this.jdbcUrl = "jdbc:sqlite:" + dbPath.toAbsolutePath();
        initDb();
    }

    private Connection connect() {
        try {
            Connection conn = DriverManager.getConnection(jdbcUrl);
            try (var stmt = conn.createStatement()) {
                stmt.execute(CREATE_TABLE_SQL);
            }
            return conn;
        } catch (SQLException e) {
            throw new IllegalStateException("failed to open stored-record database at " + jdbcUrl, e);
        }
    }

    /** Creates the {@code stored_records} table if it doesn't exist yet. Safe to call repeatedly. */
    public final void initDb() {
        try (Connection conn = connect()) {
            // connect() already runs CREATE TABLE IF NOT EXISTS; this is the explicit named entry point.
        } catch (SQLException e) {
            throw new IllegalStateException("failed to initialize stored-record database at " + jdbcUrl, e);
        }
    }

    private String toJson(Map<String, Object> data) {
        try {
            return json.writeValueAsString(data);
        } catch (Exception e) {
            throw new IllegalArgumentException("could not serialize stored record data to JSON", e);
        }
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> fromJson(String text) {
        try {
            return json.readValue(text, new TypeReference<LinkedHashMap<String, Object>>() {
            });
        } catch (Exception e) {
            throw new IllegalStateException("could not deserialize stored record data from JSON", e);
        }
    }

    public Map<String, Object> upsertRecord(String resourceType, String recordId, Map<String, Object> data) {
        return upsertRecord(resourceType, recordId, data, null, null);
    }

    /**
     * Inserts or replaces the row for {@code (resourceType, recordId)}.
     * {@code createdAt} is preserved across an update (only set on first
     * insert); {@code updatedAt} always reflects this call.
     */
    public Map<String, Object> upsertRecord(
            String resourceType, String recordId, Map<String, Object> data, String clientId, String fiscalYearId) {
        String now = Instant.now().toString();
        try (Connection conn = connect()) {
            String createdAt = now;
            try (PreparedStatement select = conn.prepareStatement(
                    "SELECT created_at FROM stored_records WHERE resource_type = ? AND record_id = ?")) {
                select.setString(1, resourceType);
                select.setString(2, recordId);
                try (ResultSet rs = select.executeQuery()) {
                    if (rs.next()) {
                        createdAt = rs.getString(1);
                    }
                }
            }
            try (PreparedStatement insert = conn.prepareStatement("""
                    INSERT OR REPLACE INTO stored_records
                        (resource_type, record_id, client_id, fiscal_year_id, data_json, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """)) {
                insert.setString(1, resourceType);
                insert.setString(2, recordId);
                insert.setString(3, clientId);
                insert.setString(4, fiscalYearId);
                insert.setString(5, toJson(data));
                insert.setString(6, createdAt);
                insert.setString(7, now);
                insert.executeUpdate();
            }
        } catch (SQLException e) {
            throw new IllegalStateException("failed to upsert stored record", e);
        }
        return data;
    }

    public Optional<Map<String, Object>> getRecord(String resourceType, String recordId) {
        try (Connection conn = connect();
             PreparedStatement stmt = conn.prepareStatement(
                     "SELECT data_json FROM stored_records WHERE resource_type = ? AND record_id = ?")) {
            stmt.setString(1, resourceType);
            stmt.setString(2, recordId);
            try (ResultSet rs = stmt.executeQuery()) {
                if (!rs.next()) {
                    return Optional.empty();
                }
                return Optional.of(fromJson(rs.getString(1)));
            }
        } catch (SQLException e) {
            throw new IllegalStateException("failed to read stored record", e);
        }
    }

    public List<Map<String, Object>> listRecords(String resourceType) {
        return listRecords(resourceType, null, null);
    }

    public List<Map<String, Object>> listRecords(String resourceType, String clientId, String fiscalYearId) {
        StringBuilder sql = new StringBuilder("SELECT data_json FROM stored_records WHERE resource_type = ?");
        List<String> params = new ArrayList<>(List.of(resourceType));
        if (clientId != null) {
            sql.append(" AND client_id = ?");
            params.add(clientId);
        }
        if (fiscalYearId != null) {
            sql.append(" AND fiscal_year_id = ?");
            params.add(fiscalYearId);
        }
        List<Map<String, Object>> result = new ArrayList<>();
        try (Connection conn = connect(); PreparedStatement stmt = conn.prepareStatement(sql.toString())) {
            for (int i = 0; i < params.size(); i++) {
                stmt.setString(i + 1, params.get(i));
            }
            try (ResultSet rs = stmt.executeQuery()) {
                while (rs.next()) {
                    result.add(fromJson(rs.getString(1)));
                }
            }
        } catch (SQLException e) {
            throw new IllegalStateException("failed to list stored records", e);
        }
        return result;
    }

    public boolean deleteRecord(String resourceType, String recordId) {
        try (Connection conn = connect();
             PreparedStatement stmt = conn.prepareStatement(
                     "DELETE FROM stored_records WHERE resource_type = ? AND record_id = ?")) {
            stmt.setString(1, resourceType);
            stmt.setString(2, recordId);
            return stmt.executeUpdate() > 0;
        } catch (SQLException e) {
            throw new IllegalStateException("failed to delete stored record", e);
        }
    }

    /**
     * Bulk counterpart to {@link #listRecords}/{@link #deleteRecord}: deletes
     * every row matching the given filters, returning the number removed.
     */
    public int deleteRecords(String resourceType, String clientId, String fiscalYearId) {
        StringBuilder sql = new StringBuilder("DELETE FROM stored_records WHERE resource_type = ?");
        List<String> params = new ArrayList<>(List.of(resourceType));
        if (clientId != null) {
            sql.append(" AND client_id = ?");
            params.add(clientId);
        }
        if (fiscalYearId != null) {
            sql.append(" AND fiscal_year_id = ?");
            params.add(fiscalYearId);
        }
        try (Connection conn = connect(); PreparedStatement stmt = conn.prepareStatement(sql.toString())) {
            for (int i = 0; i < params.size(); i++) {
                stmt.setString(i + 1, params.get(i));
            }
            return stmt.executeUpdate();
        } catch (SQLException e) {
            throw new IllegalStateException("failed to bulk-delete stored records", e);
        }
    }

    /** Deletes every row, across every resource type -- for test isolation and admin "reset stored writes". */
    public void reset() {
        try (Connection conn = connect(); var stmt = conn.createStatement()) {
            stmt.execute("DELETE FROM stored_records");
        } catch (SQLException e) {
            throw new IllegalStateException("failed to reset stored records", e);
        }
    }

    /** Every stored row, across every resource type, with its metadata -- for an admin "stored records" view. */
    public List<StoredRecordMeta> listAllWithMeta() {
        List<StoredRecordMeta> result = new ArrayList<>();
        try (Connection conn = connect(); var stmt = conn.createStatement();
             ResultSet rs = stmt.executeQuery(
                     "SELECT resource_type, record_id, client_id, fiscal_year_id, data_json, created_at, updated_at "
                             + "FROM stored_records ORDER BY resource_type, record_id")) {
            while (rs.next()) {
                result.add(new StoredRecordMeta(
                        rs.getString("resource_type"),
                        rs.getString("record_id"),
                        rs.getString("client_id"),
                        rs.getString("fiscal_year_id"),
                        fromJson(rs.getString("data_json")),
                        rs.getString("created_at"),
                        rs.getString("updated_at")));
            }
        } catch (SQLException e) {
            throw new IllegalStateException("failed to list stored records with metadata", e);
        }
        return result;
    }

    /** Test/internal helper: created_at/updated_at for one row, without the data payload. */
    Optional<RowMeta> rowMeta(String resourceType, String recordId) {
        try (Connection conn = connect();
             PreparedStatement stmt = conn.prepareStatement(
                     "SELECT created_at, updated_at FROM stored_records WHERE resource_type = ? AND record_id = ?")) {
            stmt.setString(1, resourceType);
            stmt.setString(2, recordId);
            try (ResultSet rs = stmt.executeQuery()) {
                if (!rs.next()) {
                    return Optional.empty();
                }
                return Optional.of(new RowMeta(rs.getString(1), rs.getString(2)));
            }
        } catch (SQLException e) {
            throw new IllegalStateException("failed to read stored record metadata", e);
        }
    }

    public record RowMeta(String createdAt, String updatedAt) {
    }

    public record StoredRecordMeta(
            String resourceType,
            String recordId,
            String clientId,
            String fiscalYearId,
            Map<String, Object> data,
            String createdAt,
            String updatedAt) {
    }
}
