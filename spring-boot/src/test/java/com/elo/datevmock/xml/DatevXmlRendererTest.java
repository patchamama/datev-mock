package com.elo.datevmock.xml;

import org.junit.jupiter.api.Test;

import java.util.List;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * Exercises the generic XML rendering engine in isolation, against a local
 * dummy record type, before any real DATEV model uses it. Ports the
 * behavior of FastAPI's {@code app/xml_serializers.py} (`_render_field`,
 * `_render_dataclass_fields`, `_render_generic_record`): the same
 * DataContractSerializer conventions this project already reproduces in
 * Python — `i:nil="true"` for null, lowercase booleans, per-field namespace
 * overrides, and real recursion into nested records/lists instead of a
 * `toString()` fallthrough (the class of bug fixed in `_render_field` this
 * session for the Python side).
 */
class DatevXmlRendererTest {

    record Nested(String note, boolean active) {
    }

    record Dummy(
            String id,
            String parent,
            String membersToSerialize,
            String name,
            Integer age,
            Nested nested,
            List<Nested> items
    ) {
    }

    private static String nsAttr(String fieldName) {
        if (fieldName.equals("id") || fieldName.equals("parent")) {
            return " xmlns=\"" + Namespaces.SERVICEBUS_NS + "\"";
        }
        if (fieldName.equals("membersToSerialize")) {
            return " xmlns:d3p1=\"" + Namespaces.ARRAYS_NS + "\" xmlns=\"" + Namespaces.CONNECT_CONTRACTS_NS + "\"";
        }
        return "";
    }

    @Test
    void nullFieldRendersSelfClosingNil() {
        Dummy dummy = new Dummy("abc", null, null, null, null, null, List.of());
        String xml = DatevXmlRenderer.renderRecord(
                dummy, List.of("name"), "Dummy", DatevXmlRendererTest::nsAttr);
        assertEquals("<Dummy><Name i:nil=\"true\"/></Dummy>", xml);
    }

    @Test
    void scalarFieldsRenderPascalCaseTagsInDeclaredOrder() {
        Dummy dummy = new Dummy("abc", null, null, "Alice", 30, null, List.of());
        String xml = DatevXmlRenderer.renderRecord(
                dummy, List.of("name", "age"), "Dummy", DatevXmlRendererTest::nsAttr);
        assertEquals("<Dummy><Name>Alice</Name><Age>30</Age></Dummy>", xml);
    }

    @Test
    void booleanFieldsRenderLowercaseTrueFalse() {
        record Flag(boolean active) {
        }
        Flag flag = new Flag(true);
        String xml = DatevXmlRenderer.renderRecord(flag, List.of("active"), "Flag", f -> "");
        assertEquals("<Flag><Active>true</Active></Flag>", xml);
    }

    @Test
    void syntheticIdParentMembersToSerializeUseServiceBusAndArraysNamespaces() {
        Dummy dummy = new Dummy("abc", null, null, null, null, null, List.of());
        String xml = DatevXmlRenderer.renderRecord(
                dummy, List.of("id", "parent", "membersToSerialize"), "Dummy",
                DatevXmlRendererTest::nsAttr);
        assertEquals(
                "<Dummy>"
                        + "<Id xmlns=\"" + Namespaces.SERVICEBUS_NS + "\">abc</Id>"
                        + "<Parent xmlns=\"" + Namespaces.SERVICEBUS_NS + "\" i:nil=\"true\"/>"
                        + "<membersToSerialize xmlns:d3p1=\"" + Namespaces.ARRAYS_NS
                        + "\" xmlns=\"" + Namespaces.CONNECT_CONTRACTS_NS + "\" i:nil=\"true\"/>"
                        + "</Dummy>",
                xml);
    }

    @Test
    void nestedRecordFieldRecursesIntoItsOwnFieldsInDeclarationOrder() {
        Dummy dummy = new Dummy("abc", null, null, null, null, new Nested("hi", true), List.of());
        String xml = DatevXmlRenderer.renderRecord(
                dummy, List.of("nested"), "Dummy", f -> "");
        assertEquals(
                "<Dummy><Nested><Note>hi</Note><Active>true</Active></Nested></Dummy>", xml);
    }

    @Test
    void emptyListRendersSelfClosingElement() {
        Dummy dummy = new Dummy("abc", null, null, null, null, null, List.of());
        String xml = DatevXmlRenderer.renderRecord(dummy, List.of("items"), "Dummy", f -> "");
        assertEquals("<Dummy><Items/></Dummy>", xml);
    }

    @Test
    void populatedListWrapsEachItemInItsOwnClassNameTag() {
        Dummy dummy = new Dummy(
                "abc", null, null, null, null, null,
                List.of(new Nested("a", true), new Nested("b", false)));
        String xml = DatevXmlRenderer.renderRecord(dummy, List.of("items"), "Dummy", f -> "");
        assertEquals(
                "<Dummy><Items>"
                        + "<Nested><Note>a</Note><Active>true</Active></Nested>"
                        + "<Nested><Note>b</Note><Active>false</Active></Nested>"
                        + "</Items></Dummy>",
                xml);
    }

    @Test
    void textValuesAreXmlEscaped() {
        Dummy dummy = new Dummy("abc", null, null, "A & B < C > D", null, null, List.of());
        String xml = DatevXmlRenderer.renderRecord(dummy, List.of("name"), "Dummy", f -> "");
        assertEquals("<Dummy><Name>A &amp; B &lt; C &gt; D</Name></Dummy>", xml);
    }

    @Test
    void wrapArrayProducesDeclarationRootAndNamespaces() {
        String wrapped = DatevXmlRenderer.wrapArray(
                "ArrayOfDummy", "http://example/ns", "<Dummy/>");
        assertEquals(
                Namespaces.XML_DECLARATION
                        + "<ArrayOfDummy xmlns:i=\"" + Namespaces.XSI_NS
                        + "\" xmlns=\"http://example/ns\"><Dummy/></ArrayOfDummy>",
                wrapped);
    }
}
