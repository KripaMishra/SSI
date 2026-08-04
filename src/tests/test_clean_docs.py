import unittest
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.clean_docs import (
    extract_category,
    extract_ref,
    redact_pii,
    extract_tags,
    clean_empty_lines,
    process_doc,
    redact_phones,
    redact_emails,
    redact_names,
    compute_redaction_counts,
)


class TestExtractCategory(unittest.TestCase):
    def test_internal_email_demand(self):
        self.assertEqual(extract_category("Internal Email — Demand Planning"), "Internal Email — Demand Planning")

    def test_internal_email_supply(self):
        self.assertEqual(extract_category("Internal Email — Supply"), "Internal Email — Supply")

    def test_operations_note(self):
        self.assertEqual(extract_category("Operations Note"), "Operations Note")

    def test_price_revision(self):
        self.assertEqual(extract_category("Price Revision Circular"), "Price Revision Circular")

    def test_trade_circular(self):
        self.assertEqual(extract_category("Trade Circular"), "Trade Circular")

    def test_promotions_note(self):
        self.assertEqual(extract_category("Promotions Note"), "Promotions Note")

    def test_internal_note(self):
        self.assertEqual(extract_category("Internal Note"), "Internal Note")

    def test_market_visit_report(self):
        self.assertEqual(extract_category("Market Visit Report"), "Market Visit Report")

    def test_quarterly_review(self):
        self.assertEqual(extract_category("Quarterly Review — Speaker Notes"), "Quarterly Review — Speaker Notes")


class TestExtractRef(unittest.TestCase):
    def test_basic_ref(self):
        self.assertEqual(extract_ref("Ref: email_01"), "email_01")

    def test_no_ref(self):
        self.assertIsNone(extract_ref("No ref here"))

    def test_empty(self):
        self.assertIsNone(extract_ref(""))


class TestRedactPhones(unittest.TestCase):
    def test_indian_mobile(self):
        text, count = redact_phones("Contact: +91 9310750256")
        self.assertIn("<REDACTED_PHONE>", text)
        self.assertEqual(count, 1)

    def test_indian_mobile_no_spaces(self):
        text, count = redact_phones("Contact: +919310750256")
        self.assertIn("<REDACTED_PHONE>", text)
        self.assertEqual(count, 1)

    def test_multiple_phones(self):
        text, count = redact_phones("+91 1111111111 and +91 2222222222")
        self.assertEqual(count, 2)

    def test_no_phone(self):
        text, count = redact_phones("No phone here")
        self.assertEqual(text, "No phone here")
        self.assertEqual(count, 0)


class TestRedactEmails(unittest.TestCase):
    def test_email(self):
        text, count = redact_emails("deepa.pillai@suryaacp.example")
        self.assertIn("<REDACTED_EMAIL>", text)
        self.assertEqual(count, 1)

    def test_email_in_brackets(self):
        text, count = redact_emails("<deepa.pillai@suryaacp.example>")
        self.assertIn("<REDACTED_EMAIL>", text)
        self.assertEqual(count, 1)

    def test_multiple_emails(self):
        text, count = redact_emails("a@b.com and c@d.com")
        self.assertEqual(count, 2)

    def test_no_email(self):
        text, count = redact_emails("No email here")
        self.assertEqual(text, "No email here")
        self.assertEqual(count, 0)


class TestRedactNames(unittest.TestCase):
    def test_from_line(self):
        text, count = redact_names("From: Deepa Pillai <REDACTED_EMAIL>")
        self.assertIn("<REDACTED_NAME>", text)
        self.assertEqual(count, 1)

    def test_multi_word_name(self):
        text, count = redact_names("Rajesh Kumar reported the issue")
        self.assertIn("<REDACTED_NAME>", text)
        self.assertEqual(count, 1)

    def test_three_part_name(self):
        text, count = redact_names("Anjali Mehta emailed the team")
        self.assertIn("<REDACTED_NAME>", text)
        self.assertEqual(count, 1)

    def test_no_name(self):
        text, count = redact_names("just some random text")
        self.assertEqual(text, "just some random text")
        self.assertEqual(count, 0)


class TestRedactPII(unittest.TestCase):
    def test_email_with_name_and_phone(self):
        text = "From: Deepa Pillai <deepa.pillai@suryaacp.example>\nContact: +91 9310750256"
        result, stats = redact_pii(text)
        self.assertIn("<REDACTED_NAME>", result)
        self.assertIn("<REDACTED_EMAIL>", result)
        self.assertIn("<REDACTED_PHONE>", result)
        self.assertEqual(stats["names"], 1)
        self.assertEqual(stats["emails"], 1)
        self.assertEqual(stats["phones"], 1)

    def test_visit_note(self):
        text = "From: Rajesh Kumar <rajesh.kumar@suryaacp.example>\nContact: +91 9264486281"
        result, stats = redact_pii(text)
        self.assertIn("<REDACTED_NAME>", result)
        self.assertIn("<REDACTED_EMAIL>", result)
        self.assertIn("<REDACTED_PHONE>", result)

    def test_no_pii(self):
        text = "Routine operational note: no exceptions."
        result, stats = redact_pii(text)
        self.assertEqual(result, text)
        self.assertEqual(stats["names"], 0)
        self.assertEqual(stats["emails"], 0)
        self.assertEqual(stats["phones"], 0)


class TestExtractTags(unittest.TestCase):
    def test_sop_tag(self):
        doc = "# Internal Note\nRef: sop_policy_01\n\nSOP: Report sales in cases; 1 case = 24 eaches."
        tags = extract_tags(doc)
        self.assertIn("sop", tags)

    def test_attribution_unverified_tag(self):
        doc = "# Promotions Note\nRef: promo_note_redherring_02b\n\nsuggests a lapsed promo caused the decline (false)\n\n_Note: attribution unverified._"
        tags = extract_tags(doc)
        self.assertIn("attribution_unverified", tags)

    def test_no_tags(self):
        doc = "# Operations Note\nRef: routine_note_16\n\nRoutine note."
        tags = extract_tags(doc)
        self.assertEqual(tags, [])


class TestCleanEmptyLines(unittest.TestCase):
    def test_triple_newlines_reduced(self):
        text = "line 1\n\n\n\nline 2"
        self.assertEqual(clean_empty_lines(text), "line 1\n\nline 2")

    def test_leading_trailing_newlines(self):
        text = "\n\nline 1\nline 2\n\n"
        self.assertEqual(clean_empty_lines(text), "line 1\nline 2")

    def test_single_line(self):
        self.assertEqual(clean_empty_lines("hello"), "hello")


class TestProcessDoc(unittest.TestCase):
    def test_email_01_full_pipeline(self):
        content = "# Internal Email — Demand Planning\nRef: email_01\n\nFrom: Deepa Pillai <deepa.pillai@suryaacp.example>\nContact: +91 9310750256\n\nsupplier delay caused GlucoJoy Choco 120g stockout in Delhi\n"
        result = process_doc("Data/docs/email_01.txt", content)
        self.assertEqual(result["id"], "email_01")
        self.assertEqual(result["metadata"]["category"], "Internal Email — Demand Planning")
        self.assertEqual(result["metadata"]["ref"], "email_01")
        self.assertIn("<REDACTED_NAME>", result["text"])
        self.assertIn("<REDACTED_EMAIL>", result["text"])
        self.assertIn("<REDACTED_PHONE>", result["text"])
        self.assertGreater(result["metadata"]["redactions"]["names"], 0)
        self.assertGreater(result["metadata"]["redactions"]["emails"], 0)
        self.assertGreater(result["metadata"]["redactions"]["phones"], 0)

    def test_routine_note_no_pii(self):
        content = "# Operations Note\nRef: routine_note_16\n\nRoutine operational note 16: no exceptions.\n"
        result = process_doc("Data/docs/routine_note_16.txt", content)
        self.assertEqual(result["id"], "routine_note_16")
        self.assertEqual(result["metadata"]["category"], "Operations Note")
        self.assertEqual(result["metadata"]["ref"], "routine_note_16")
        self.assertEqual(result["text"], "Routine operational note 16: no exceptions.")
        self.assertEqual(result["metadata"]["redactions"]["names"], 0)

    def test_tags_included(self):
        content = "# Promotions Note\nRef: promo_note_redherring_02b\n\nsuggests a lapsed promo caused the decline (false)\n\n_Note: attribution unverified._\n"
        result = process_doc("Data/docs/promo_note_redherring_02b.txt", content)
        self.assertIn("attribution_unverified", result["metadata"]["tags"])

    def test_sop_tag(self):
        content = "# Internal Note\nRef: sop_policy_01\n\nSOP: Report sales in cases; 1 case = 24 eaches for biscuits, 12 for detergent. Returns are logged separately and must not be netted into primary sales. Escalate stockouts >3 days.\n"
        result = process_doc("Data/docs/sop_policy_01.txt", content)
        self.assertIn("sop", result["metadata"]["tags"])

    def test_email_from_attributes(self):
        content = "# Internal Email — Supply\nRef: email_02\n\nFrom: Anjali Mehta <anjali.mehta@suryaacp.example>\nContact: +91 9983498086\n\nGlucoJoy Choco 120g supply shortfall during Diwali peak in North\n"
        result = process_doc("Data/docs/email_02.txt", content)
        self.assertEqual(result["metadata"]["category"], "Internal Email — Supply")
        self.assertIn("from", result["metadata"]["attributes"])

    def test_output_format(self):
        content = "# Test\nRef: test_01\n\nSome content.\n"
        result = process_doc("Data/docs/test_01.txt", content)
        self.assertIn("id", result)
        self.assertIn("text", result)
        self.assertIn("metadata", result)
        self.assertIn("category", result["metadata"])
        self.assertIn("tags", result["metadata"])
        self.assertIn("redactions", result["metadata"])


class TestComputeRedactionCounts(unittest.TestCase):
    def test_all_three_types(self):
        counts = compute_redaction_counts(
            names=3,
            emails=2,
            phones=1,
        )
        self.assertEqual(counts["names"], 3)
        self.assertEqual(counts["emails"], 2)
        self.assertEqual(counts["phones"], 1)
        self.assertEqual(counts["total"], 6)


if __name__ == "__main__":
    unittest.main()