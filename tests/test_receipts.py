import tempfile
import unittest
from unittest.mock import patch
from datetime import date
from decimal import Decimal
from pathlib import Path

from fortnox_automation.receipts import Receipt, ReceiptValidationError, ReceiptWorkflow


class FakeReceiptClient:
    def __init__(self):
        self.created = []

    def create_voucher(self, voucher):
        self.created.append(voucher)
        return {"Voucher": {"VoucherNumber": "V-1"}}


class ReceiptWorkflowTests(unittest.TestCase):
    def test_builds_balanced_voucher_preview(self):
        with tempfile.NamedTemporaryFile(suffix=".pdf") as source:
            receipt = Receipt(
                supplier="Office supplier", transaction_date=date(2026, 7, 19),
                gross_amount=Decimal("125.00"), vat_amount=Decimal("25.00"),
                vat_rate=Decimal("25"), expense_account="6110", vat_account="2641",
                payment_account="1930", source_document=Path(source.name), currency="SEK",
            )
            preview = ReceiptWorkflow(FakeReceiptClient()).preview(receipt)
            self.assertEqual(preview["status"], "ready_for_approval")
            self.assertEqual(preview["voucher"]["Voucher"]["VoucherRows"][0]["Debit"], "100.00")
            self.assertEqual(preview["voucher"]["Voucher"]["VoucherRows"][1]["Debit"], "25.00")
            self.assertEqual(preview["voucher"]["Voucher"]["VoucherRows"][2]["Credit"], "125.00")

    def test_invalid_vat_is_rejected_before_api(self):
        receipt = Receipt(
            supplier="Supplier", transaction_date=date(2026, 7, 19),
            gross_amount=Decimal("100.00"), vat_amount=Decimal("30.00"),
            vat_rate=Decimal("25"), expense_account="6110", vat_account="2641",
            payment_account="1930",
        )
        client = FakeReceiptClient()
        with self.assertRaises(ReceiptValidationError):
            ReceiptWorkflow(client).preview(receipt)
        self.assertFalse(client.created)

    def test_booking_requires_explicit_approval(self):
        receipt = Receipt(
            supplier="Supplier", transaction_date=date(2026, 7, 19),
            gross_amount=Decimal("125.00"), vat_amount=Decimal("25.00"),
            vat_rate=Decimal("25"), expense_account="6110", vat_account="2641",
            payment_account="1930",
        )
        client = FakeReceiptClient()
        with self.assertRaises(PermissionError):
            ReceiptWorkflow(client).book(receipt)
        self.assertFalse(client.created)

    def test_booking_uses_previewed_payload_after_approval(self):
        receipt = Receipt(
            supplier="Supplier", transaction_date=date(2026, 7, 19),
            gross_amount=Decimal("125.00"), vat_amount=Decimal("25.00"),
            vat_rate=Decimal("25"), expense_account="6110", vat_account="2641",
            payment_account="1930",
        )
        client = FakeReceiptClient()
        with patch.dict("os.environ", {"FORTNOX_APPROVAL_TOKEN": "test-approval-token"}):
            result = ReceiptWorkflow(client).book(receipt, approval_token="test-approval-token")
        self.assertEqual(result["Voucher"]["VoucherNumber"], "V-1")
        self.assertEqual(len(client.created), 1)


if __name__ == "__main__":
    unittest.main()
