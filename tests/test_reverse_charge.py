import unittest
from datetime import date
from decimal import Decimal

from fortnox_automation.receipts import Receipt, ReceiptWorkflow


class FakeClient:
    def create_voucher(self, payload):
        return payload


class ReverseChargeTests(unittest.TestCase):
    def test_foreign_service_preview_adds_reverse_charge_vat_rows(self):
        receipt = Receipt(
            supplier="Scandinavian Medical Center", transaction_date=date(2026, 7, 12),
            gross_amount=Decimal("45000.00"), vat_amount=Decimal("0.00"), vat_rate=Decimal("0"),
            expense_account="4531", vat_account="2645", payment_account="1930",
            reverse_charge_rate=Decimal("25"), reverse_charge_output_account="2614",
        )
        preview = ReceiptWorkflow(FakeClient()).preview(receipt)
        rows = preview["voucher"]["Voucher"]["VoucherRows"]
        self.assertEqual([(r["Account"], r["Debit"], r["Credit"]) for r in rows], [
            ("4531", "45000.00", "0.00"),
            ("2645", "11250.00", "0.00"),
            ("2614", "0.00", "11250.00"),
            ("1930", "0.00", "45000.00"),
        ])
        self.assertIn("reverse charge", preview["warnings"][0].lower())


if __name__ == "__main__":
    unittest.main()
