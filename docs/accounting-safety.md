# Accounting safety

The software validates payload structure. It does not provide legal, tax, or accounting advice.

Before a mutation, review:

- Fortnox company and financial year.
- Voucher series and period lock.
- Supplier/customer identity.
- Gross, net, and VAT amounts.
- Debit/credit balance.
- VAT treatment and account mapping.
- Source document and duplicate risk.
- External effect: booking, sending, paying, cancelling, crediting, or deleting.

Use previews first. Do not automatically create missing financial years. Do not automatically reverse or delete a financial record. Prefer a reviewed correction workflow where appropriate.

The public repository contains no tenant data. Keep live reports, source documents, and audit logs outside the checkout.
