package com.elo.datevmock.overrides;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;
import org.w3c.dom.Document;
import org.xml.sax.InputSource;
import org.xml.sax.SAXException;

import javax.xml.parsers.DocumentBuilder;
import javax.xml.parsers.DocumentBuilderFactory;
import java.io.IOException;
import java.io.StringReader;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

/**
 * Ports {@code app/overrides.py}'s upload-time detection: which endpoint(s)
 * an uploaded file's content structurally matches, via its XML root element
 * or a JSON object's field-name fingerprint. Deliberately excluded from
 * {@link OverrideStore} (SB3's own scope note) -- this is that promised
 * SB9 piece.
 */
@Component
public class OverrideDetector {

    private static final Map<String, List<String>> XML_ROOT_MAP = Map.of(
            "Echo", List.of("diagnostics.echo"),
            "ArrayOfClientResource", List.of("master_data.clients"),
            "ArrayOfClient", List.of("accounting.clients"));

    // Order matters no more than in Python's dict (insertion order is
    // preserved, and each fingerprint is checked independently) -- kept as
    // an ordered map purely for readability against app/overrides.py.
    private static final Map<Set<String>, List<String>> FINGERPRINTS = new LinkedHashMap<>();

    static {
        FINGERPRINTS.put(Set.of("id", "name", "number"), List.of("accounting.clients"));
        FINGERPRINTS.put(
                Set.of("type", "status", "timestamp", "current_company_name"),
                List.of("master_data.addressees"));
        FINGERPRINTS.put(
                Set.of("type", "status", "timestamp", "firstname"),
                List.of("master_data.addressees"));
        FINGERPRINTS.put(Set.of("bic", "country_code"), List.of("master_data.banks"));
        FINGERPRINTS.put(
                Set.of("account_system", "currency_code", "legal_form", "taxation_method"),
                List.of("accounting.fiscal_years"));
        FINGERPRINTS.put(
                Set.of("short_name", "is_activated_for_postings"),
                List.of("accounting.cost_systems"));
        FINGERPRINTS.put(
                Set.of("long_name", "short_name", "creation_date"),
                List.of("accounting.cost_centers"));
        FINGERPRINTS.put(
                Set.of("addressee_id", "business_partner_number", "legal_entity_type"),
                List.of("accounting.creditors", "accounting.debitors"));
        FINGERPRINTS.put(
                Set.of("account_number", "caption", "main_function", "main_function_number"),
                List.of("accounting.general_ledger_accounts"));
        FINGERPRINTS.put(
                Set.of("evidence_type", "debit_credit_identifier", "open_balance_of_item", "is_condensed"),
                List.of(
                        "accounting.accounts_payable",
                        "accounting.accounts_payable_condense",
                        "accounting.accounts_receivable_condense"));
        FINGERPRINTS.put(
                Set.of("accounting_sequence_id", "record_type", "accounting_reason", "date_from", "date_to"),
                List.of("accounting.accounting_sequences_processed"));
        FINGERPRINTS.put(
                Set.of("tax_rate", "is_tax_rate_selectable"),
                List.of("accounting.accounting_transaction_keys"));
        FINGERPRINTS.put(
                Set.of("asset_number", "inventory_number"),
                List.of("accounting.assets_stocktakings"));
        FINGERPRINTS.put(
                Set.of("assignment_criteria", "posting_proposal_information", "uncertain_label"),
                List.of("accounting.posting_proposal_rules_incoming", "accounting.posting_proposal_rules_outgoing"));
        FINGERPRINTS.put(Set.of("caption", "due_type"), List.of("accounting.terms_of_payment"));
        FINGERPRINTS.put(Set.of("name", "type"), List.of("dms.domains"));
        FINGERPRINTS.put(
                Set.of("amount", "document_class", "domain_id", "created_at", "modified_at"),
                List.of("dms.documents"));
    }

    // Matches a bare "&" not already part of a recognized entity reference
    // (&amp; &lt; &gt; &quot; &apos; &#NN; &#xHH;) -- real-world captured
    // DATEV XML has been observed with unescaped "&" in text content.
    private static final Pattern BARE_AMPERSAND =
            Pattern.compile("&(?!(?:amp|lt|gt|quot|apos|#[0-9]+|#x[0-9a-fA-F]+);)");

    private final ObjectMapper jsonMapper = new ObjectMapper();

    /** Returns {@code content} unchanged if it already parses as XML, or with bare
     * "&"s repaired if that alone makes it parse; otherwise returns it unchanged. */
    public String sanitizeXml(String content) {
        if (parseXml(content) != null) {
            return content;
        }
        String repaired = BARE_AMPERSAND.matcher(content).replaceAll("&amp;");
        if (parseXml(repaired) != null) {
            return repaired;
        }
        return content;
    }

    /** Endpoint keys this content structurally matches (empty = none, 2-3 = one of
     * the documented ambiguous groups). */
    public List<String> detectCandidates(String content) {
        String rootTag = tryParseXmlRoot(content);
        if (rootTag != null) {
            return new ArrayList<>(XML_ROOT_MAP.getOrDefault(rootTag, List.of()));
        }

        JsonNode data = tryParseJson(content);
        if (data == null) {
            return List.of();
        }
        JsonNode record = data.isArray() ? (data.isEmpty() ? null : data.get(0)) : data;
        if (record == null || !record.isObject()) {
            return List.of();
        }

        Set<String> fields = new LinkedHashSet<>();
        record.fieldNames().forEachRemaining(fields::add);

        List<String> matched = new ArrayList<>();
        for (Map.Entry<Set<String>, List<String>> entry : FINGERPRINTS.entrySet()) {
            if (fields.containsAll(entry.getKey())) {
                for (String key : entry.getValue()) {
                    if (!matched.contains(key)) {
                        matched.add(key);
                    }
                }
            }
        }
        return matched;
    }

    /** {@code "xml"}, {@code "json"}, or {@code null} for content that parses as neither. */
    public String detectContentType(String content) {
        if (tryParseXmlRoot(content) != null) {
            return "xml";
        }
        if (tryParseJson(content) != null) {
            return "json";
        }
        return null;
    }

    private String tryParseXmlRoot(String content) {
        Document doc = parseXml(sanitizeXml(content));
        return doc == null ? null : doc.getDocumentElement().getLocalName() != null
                ? doc.getDocumentElement().getLocalName()
                : doc.getDocumentElement().getTagName();
    }

    private Document parseXml(String content) {
        try {
            DocumentBuilderFactory factory = DocumentBuilderFactory.newInstance();
            factory.setFeature("http://apache.org/xml/features/disallow-doctype-decl", true);
            DocumentBuilder builder = factory.newDocumentBuilder();
            return builder.parse(new InputSource(new StringReader(content)));
        } catch (Exception e) {
            // Any parse failure (SAXException, IOException, malformed input) --
            // not XML, nothing to detect a root element from.
            return null;
        }
    }

    private JsonNode tryParseJson(String content) {
        try {
            return jsonMapper.readTree(content);
        } catch (IOException e) {
            return null;
        }
    }
}
