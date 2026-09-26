"""Preview-first receipt-to-voucher workflow."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from .security import require_approval


CENT = Decimal("0.01")


class ReceiptValidationError(ValueError):
    pass


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def _amount(value: Decimal) -> str:
    return f"{_money(value):.2f}"


@dataclass(frozen=True)
class Receipt:
    supplier: str
    transaction_date: date
    gross_amount: Decimal
    vat_amount: Decimal
    vat_rate: Decimal
    expense_account: str
    vat_account: str
    payment_account: str
    source_document: Path | None = None
    currency: str = "SEK"
    cost_center: str | None = None
    project: str | None = None
    description: str | None = None
    voucher_series: str | None = None
    reverse_charge_rate: Decimal | None = None
    reverse_charge_output_account: str | None = None

    @property
    def net_amount(self) -> Decimal:
        return _money(self.gross_amount - self.vat_amount)

    def validate(self) -> None:
        if not self.supplier.strip():
            raise ReceiptValidationError("supplier is required")
        if self.gross_amount <= 0:
            raise ReceiptValidationError("gross_amount must be positive")
        if self.vat_amount < 0 or self.vat_amount > self.gross_amount:
            raise ReceiptValidationError("vat_amount must be between zero and gross_amount")
        if self.vat_rate < 0 or self.vat_rate > 100:
            raise ReceiptValidationError("vat_rate must be between 0 and 100")
        if self.net_amount <= 0:
            raise ReceiptValidationError("net amount must be positive")
        if not all(str(x).strip() for x in (self.expense_account, self.vat_account, self.payment_account)):
            raise ReceiptValidationError("expense_account, vat_account, and payment_account are required")
        expected_vat = _money(self.gross_amount * self.vat_rate / (Decimal("100") + self.vat_rate))
        if abs(expected_vat - _money(self.vat_amount)) > Decimal("0.02"):
            raise ReceiptValidationError(
                f"vat_amount {self.vat_amount} is inconsistent with {self.vat_rate}% VAT on {self.gross_amount}")
        if self.source_document is not None and not self.source_document.is_file():
            raise ReceiptValidationError(f"source document does not exist: {self.source_document}")
        if self.reverse_charge_rate is not None:
            if not self.reverse_charge_output_account:
                raise ReceiptValidationError("reverse_charge_output_account is required")
            if self.reverse_charge_rate <= 0 or self.reverse_charge_rate > 100:
                raise ReceiptValidationError("reverse_charge_rate must be between 0 and 100")


class ReceiptWorkflow:
    def __init__(self, client):
        self.client = client

    @staticmethod
    def _voucher(receipt: Receipt) -> dict[str, Any]:
        rows: list[dict[str, str]] = [{
            "Account": receipt.expense_account,
            "Debit": _amount(receipt.net_amount),
            "Credit": "0.00",
        }]
        if receipt.vat_amount:
            rows.append({"Account": receipt.vat_account, "Debit": _amount(receipt.vat_amount), "Credit": "0.00"})
        if receipt.reverse_charge_rate is not None:
            reverse_vat = _money(receipt.net_amount * receipt.reverse_charge_rate / Decimal("100"))
            rows.append({"Account": receipt.vat_account, "Debit": _amount(reverse_vat), "Credit": "0.00"})
            rows.append({"Account": receipt.reverse_charge_output_account, "Debit": "0.00", "Credit": _amount(reverse_vat)})
        rows.append({"Account": receipt.payment_account, "Debit": "0.00", "Credit": _amount(receipt.gross_amount)})
        for row in rows:
            if receipt.cost_center:
                row["CostCenter"] = receipt.cost_center
            if receipt.project:
                row["Project"] = receipt.project
        voucher: dict[str, Any] = {
            "TransactionDate": receipt.transaction_date.isoformat(),
            "Description": receipt.description or f"Receipt - {receipt.supplier}",
            "VoucherRows": rows,
        }
        if receipt.voucher_series:
            voucher["VoucherSeries"] = receipt.voucher_series
        return {"Voucher": voucher}

    def preview(self, receipt: Receipt) -> dict[str, Any]:
        receipt.validate()
        voucher = self._voucher(receipt)
        debit = sum(Decimal(row["Debit"]) for row in voucher["Voucher"]["VoucherRows"])
        credit = sum(Decimal(row["Credit"]) for row in voucher["Voucher"]["VoucherRows"])
        if debit != credit:
            raise ReceiptValidationError("generated voucher is not balanced")
        warnings = []
        if receipt.reverse_charge_rate is not None:
            warnings.append("Reverse charge VAT is proposed; confirm that the service is taxable in Sweden.")
        if receipt.source_document is None:
            warnings.append("No source document attached; attach the receipt before bookkeeping.")
        return {
            "status": "ready_for_approval",
            "supplier": receipt.supplier,
            "transaction_date": receipt.transaction_date.isoformat(),
            "gross_amount": _amount(receipt.gross_amount),
            "vat_amount": _amount(receipt.vat_amount),
            "net_amount": _amount(receipt.net_amount),
            "currency": receipt.currency,
            "warnings": warnings,
            "voucher": voucher,
        }

    def book(self, receipt: Receipt, *, approval_token: str | None = None) -> Any:
        require_approval(approval_token)
        preview = self.preview(receipt)
        return self.client.create_voucher(preview["voucher"])
