package com.elo.datevmock.dms;

import com.elo.datevmock.model.Document;
import com.elo.datevmock.model.Domain;
import org.springframework.stereotype.Component;

import java.time.OffsetDateTime;
import java.time.ZoneOffset;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/**
 * Ports {@code app/fake_data.py::_generate_domains}/{@code
 * _generate_documents}: a small, fixed, hand-authored domain/folder/register
 * tree (not randomly generated — a coherent hand-authored tree is clearer
 * than a randomized one for a resource this small, per the Python source's
 * own comment) plus a fixed-count document list cycling through that tree's
 * node ids, generated once and stable for the JVM's lifetime — same
 * "unscoped, generated once" shape as {@code MasterDataGenerator}.
 */
@Component
public class DmsGenerator {

    private static final DateTimeFormatter TIMESTAMP_FORMAT =
            DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss.SSSxxx");

    // (id, name, type, parentId) -- ported 1:1 from _DMS_DOMAIN_TREE.
    private static final Object[][] DOMAIN_TREE = {
            {"DOM0001", "Unternehmen", "domain", null},
            {"DOM0002", "Belege", "folder", "DOM0001"},
            {"DOM0003", "Rechnungswesen", "folder", "DOM0001"},
            {"DOM0004", "Rechnungseingang", "register", "DOM0002"},
            {"DOM0005", "Rechnungsausgang", "register", "DOM0002"},
            {"DOM0006", "Kontoauszüge", "register", "DOM0003"},
    };

    private static final String[] DOCUMENT_CLASSES = {"invoice", "receipt", "contract", "delivery_note"};

    private static final String[] DOCUMENT_NAMES = {
            "Rechnung_2024_001.pdf",
            "Quittung_Buero.pdf",
            "Vertrag_Wartung.pdf",
            "Lieferschein_1042.pdf",
            "Rechnung_2024_002.pdf",
            "Quittung_Reise.pdf",
    };

    private static final int DOCUMENT_COUNT = 6;

    private final List<Domain> domains;
    private final List<Document> documents;

    public DmsGenerator() {
        this.domains = generateDomains();
        this.documents = generateDocuments();
    }

    public List<Domain> domains() {
        return List.copyOf(domains);
    }

    public List<Document> documents() {
        return List.copyOf(documents);
    }

    private static List<Domain> generateDomains() {
        List<Domain> result = new ArrayList<>();
        for (Object[] node : DOMAIN_TREE) {
            result.add(new Domain((String) node[0], (String) node[1], (String) node[2], (String) node[3]));
        }
        return result;
    }

    private static List<Document> generateDocuments() {
        String[] domainIds = new String[DOMAIN_TREE.length];
        for (int i = 0; i < DOMAIN_TREE.length; i++) {
            domainIds[i] = (String) DOMAIN_TREE[i][0];
        }

        List<Document> result = new ArrayList<>();
        OffsetDateTime created = OffsetDateTime.now(ZoneOffset.ofHours(1));
        for (int index = 0; index < DOCUMENT_COUNT; index++) {
            String createdAt = created.format(TIMESTAMP_FORMAT);
            String modifiedAt = created.plusDays(index + 1).format(TIMESTAMP_FORMAT);
            result.add(new Document(
                    UUID.randomUUID().toString(),
                    DOCUMENT_NAMES[index % DOCUMENT_NAMES.length],
                    Math.round((19.99 + index * 42.5) * 100.0) / 100.0,
                    DOCUMENT_CLASSES[index % DOCUMENT_CLASSES.length],
                    domainIds[index % domainIds.length],
                    createdAt,
                    modifiedAt));
        }
        return result;
    }
}
