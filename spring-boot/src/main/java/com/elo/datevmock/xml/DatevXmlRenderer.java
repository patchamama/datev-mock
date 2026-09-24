package com.elo.datevmock.xml;

import java.lang.reflect.Field;
import java.lang.reflect.RecordComponent;
import java.util.List;
import java.util.Set;
import java.util.function.Function;

/**
 * Generic DataContractSerializer-style XML rendering engine, ported from
 * FastAPI's {@code app/xml_serializers.py} (`_render_field`,
 * `_render_dataclass_fields`, `_render_generic_record`).
 *
 * <p>Every DATEV model rendered through this engine must be a Java
 * {@code record}: nested single-object fields and list-item fields are
 * detected via {@link Class#isRecord()} and recursed into through their
 * {@link RecordComponent}s in declaration order — the direct Java
 * equivalent of Python's {@code dataclasses.fields()} iteration order that
 * {@code _render_dataclass_fields} relies on. This intentionally avoids the
 * bug class fixed in the Python renderer this session, where nested
 * dataclasses/lists used to fall through to a broken {@code str(value)}
 * instead of recursing into real elements.
 */
public final class DatevXmlRenderer {

    private DatevXmlRenderer() {
    }

    /**
     * Renders a top-level DATEV record: {@code fieldOrder} lists Java
     * (camelCase) field names in declaration order, including synthetic
     * preamble fields like {@code parent}/{@code membersToSerialize} that
     * don't exist on the record itself and always render {@code i:nil}.
     * {@code nsAttrResolver} returns the (possibly empty) namespace
     * attribute string to attach to a given field's element, mirroring
     * {@code _generic_ns_attr}/{@code _master_data_ns_attr}/etc.
     */
    public static String renderRecord(
            Object record, List<String> fieldOrder, String tag,
            Function<String, String> nsAttrResolver) {
        StringBuilder body = new StringBuilder();
        for (String fieldName : fieldOrder) {
            Object value = fieldValue(record, fieldName);
            String nsAttr = nsAttrResolver.apply(fieldName);
            body.append(renderField(xmlTag(fieldName), value, nsAttr == null ? "" : nsAttr));
        }
        return "<" + tag + ">" + body + "</" + tag + ">";
    }

    /**
     * The namespace-override pattern shared by every generic DATEV record
     * (ports {@code _generic_ns_attr}): {@code id}/{@code parent} always get
     * the ServiceBus namespace, {@code membersToSerialize} always gets the
     * Arrays/Connect-Contracts pair, and an optional caller-supplied set of
     * "common" fields (e.g. `Creditor`/`Debitor`'s array/nested-object
     * fields) get an extra {@code d3p1} namespace override when nil.
     */
    public static Function<String, String> genericNsAttrResolver(
            Set<String> commonNsFields, String commonNs) {
        return fieldName -> {
            if (fieldName.equals("id") || fieldName.equals("parent")) {
                return " xmlns=\"" + Namespaces.SERVICEBUS_NS + "\"";
            }
            if (fieldName.equals("membersToSerialize")) {
                return " xmlns:d3p1=\"" + Namespaces.ARRAYS_NS
                        + "\" xmlns=\"" + Namespaces.CONNECT_CONTRACTS_NS + "\"";
            }
            if (commonNsFields.contains(fieldName)) {
                return " xmlns:d3p1=\"" + commonNs + "\"";
            }
            return "";
        };
    }

    /** Wraps a rendered body in the `<?xml ...?><ArrayOfX xmlns:i=... xmlns=...>` envelope. */
    public static String wrapArray(String rootTag, String defaultNs, String body) {
        return Namespaces.XML_DECLARATION
                + "<" + rootTag + " xmlns:i=\"" + Namespaces.XSI_NS
                + "\" xmlns=\"" + defaultNs + "\">"
                + body
                + "</" + rootTag + ">";
    }

    private static Object fieldValue(Object record, String fieldName) {
        // `parent`/`membersToSerialize` are synthetic (no real field on any
        // record) -- every confirmed sample in this project always renders
        // them `i:nil="true"`, same as the Python `_field_value` helper.
        if (fieldName.equals("parent") || fieldName.equals("membersToSerialize")) {
            return null;
        }
        try {
            Field field = record.getClass().getDeclaredField(fieldName);
            field.setAccessible(true);
            return field.get(record);
        } catch (ReflectiveOperationException e) {
            throw new IllegalStateException(
                    "No field '" + fieldName + "' on " + record.getClass(), e);
        }
    }

    private static String renderField(String tagName, Object value, String nsAttr) {
        if (value == null) {
            return "<" + tagName + nsAttr + " i:nil=\"true\"/>";
        }
        if (value instanceof Boolean bool) {
            // DataContractSerializer renders booleans lowercase.
            return "<" + tagName + nsAttr + ">" + (bool ? "true" : "false") + "</" + tagName + ">";
        }
        if (value instanceof List<?> list) {
            if (list.isEmpty()) {
                return "<" + tagName + nsAttr + "/>";
            }
            String itemTag = list.get(0).getClass().getSimpleName();
            StringBuilder items = new StringBuilder();
            for (Object item : list) {
                items.append("<").append(itemTag).append(">")
                        .append(renderRecordFields(item))
                        .append("</").append(itemTag).append(">");
            }
            return "<" + tagName + nsAttr + ">" + items + "</" + tagName + ">";
        }
        if (value.getClass().isRecord()) {
            return "<" + tagName + nsAttr + ">" + renderRecordFields(value) + "</" + tagName + ">";
        }
        return "<" + tagName + nsAttr + ">" + escape(String.valueOf(value)) + "</" + tagName + ">";
    }

    private static String renderRecordFields(Object instance) {
        StringBuilder sb = new StringBuilder();
        for (RecordComponent component : instance.getClass().getRecordComponents()) {
            try {
                Object value = component.getAccessor().invoke(instance);
                sb.append(renderField(xmlTag(component.getName()), value, ""));
            } catch (ReflectiveOperationException e) {
                throw new IllegalStateException(e);
            }
        }
        return sb.toString();
    }

    private static String xmlTag(String fieldName) {
        if (fieldName.equals("id")) {
            return "Id";
        }
        if (fieldName.equals("parent")) {
            return "Parent";
        }
        if (fieldName.equals("membersToSerialize")) {
            return "membersToSerialize";
        }
        return Character.toUpperCase(fieldName.charAt(0)) + fieldName.substring(1);
    }

    private static String escape(String text) {
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;");
    }
}
