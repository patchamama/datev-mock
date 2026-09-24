package com.elo.datevmock.xml;

import com.elo.datevmock.model.PostingProposalRule;

import java.util.List;
import java.util.Set;

/**
 * Ports {@code app/xml_serializers.py::serialize_posting_proposal_rules} --
 * shared serializer for both incoming and outgoing invoice directions
 * (identical {@code PostingProposalRule} shape).
 */
public final class PostingProposalRuleXmlSerializer {

    private PostingProposalRuleXmlSerializer() {
    }

    public static String serialize(List<PostingProposalRule> records) {
        StringBuilder body = new StringBuilder();
        for (PostingProposalRule record : records) {
            body.append(DatevXmlRenderer.renderRecord(
                    record,
                    PostingProposalRule.XML_FIELD_ORDER,
                    "PostingProposalRule",
                    DatevXmlRenderer.genericNsAttrResolver(Set.of(), "")));
        }
        return DatevXmlRenderer.wrapArray(
                "ArrayOfPostingProposalRule", Namespaces.POSTING_PROPOSAL_RULE_NS, body.toString());
    }
}
