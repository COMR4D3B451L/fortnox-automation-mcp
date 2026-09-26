"""Minimal stdio MCP server for connecting the wrapper to Hermes."""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

try:
    from .client import FortnoxClient
    from .config import load_project_env
    from .receipts import Receipt, ReceiptWorkflow
    from .security import require_approval
except ImportError:  # Allows Hermes to launch this file by absolute path.
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from fortnox_automation.client import FortnoxClient
    from fortnox_automation.config import load_project_env
    from fortnox_automation.receipts import Receipt, ReceiptWorkflow
    from fortnox_automation.security import require_approval


def _tools():
    tools = [
        {"name": "fortnox_list_invoices", "description": "List Fortnox invoices (read-only)",
         "inputSchema": {"type": "object", "properties": {"params": {"type": "object"}, "max_items": {"type": "integer", "maximum": 500}}}},
        {"name": "fortnox_list_customers", "description": "List Fortnox customers (read-only)",
         "inputSchema": {"type": "object", "properties": {"params": {"type": "object"}, "max_items": {"type": "integer", "maximum": 500}}}},
        {"name": "fortnox_preview_receipt", "description": "Validate a receipt and build a balanced voucher preview; does not write to Fortnox",
         "inputSchema": {"type": "object", "required": ["receipt"], "properties": {"receipt": {"type": "object"}}}},
    ]
    if os.getenv("FORTNOX_ENABLE_WRITES") == "1":
        tools.append({"name": "fortnox_create_invoice", "description": "Create invoice; explicit approval required",
                      "inputSchema": {"type": "object", "required": ["invoice", "approval_token"],
                                       "properties": {"invoice": {"type": "object"}, "approval_token": {"type": "string"}}}})
        tools.append({"name": "fortnox_book_receipt", "description": "Book a validated receipt; explicit approval required",
                      "inputSchema": {"type": "object", "required": ["receipt", "approval_token"],
                                       "properties": {"receipt": {"type": "object"}, "approval_token": {"type": "string"}}}})
        tools.append({"name": "fortnox_attach_voucher_document", "description": "Upload a local document to Fortnox archive and connect it to a voucher; explicit approval required",
                      "inputSchema": {"type": "object", "required": ["source_document", "voucher_series", "voucher_number", "voucher_year", "approval_token"],
                                       "properties": {"source_document": {"type": "string"}, "voucher_series": {"type": "string"}, "voucher_number": {"type": "integer"}, "voucher_year": {"type": "integer"}, "approval_token": {"type": "string"}}}})
        tools.append({"name": "fortnox_delete_voucher", "description": "Permanently delete one voucher; explicit approval required and audit checks remain the caller's responsibility",
                      "inputSchema": {"type": "object", "required": ["voucher_series", "voucher_number", "voucher_year", "approval_token"],
                                       "properties": {"voucher_series": {"type": "string"}, "voucher_number": {"type": "integer"}, "voucher_year": {"type": "integer"}, "approval_token": {"type": "string"}}}})
    return tools


def _receipt(data):
    return Receipt(
        supplier=str(data["supplier"]), transaction_date=date.fromisoformat(data["transaction_date"]),
        gross_amount=Decimal(str(data["gross_amount"])), vat_amount=Decimal(str(data["vat_amount"])),
        vat_rate=Decimal(str(data["vat_rate"])), expense_account=str(data["expense_account"]),
        vat_account=str(data["vat_account"]), payment_account=str(data["payment_account"]),
        source_document=Path(data["source_document"]) if data.get("source_document") else None,
        currency=str(data.get("currency", "SEK")), cost_center=data.get("cost_center"),
        project=data.get("project"), description=data.get("description"), voucher_series=data.get("voucher_series"),
    )


def _result(value):
    return {"content": [{"type": "text", "text": json.dumps(value, ensure_ascii=False, default=str)}]}


def main() -> None:
    load_project_env()
    client = FortnoxClient()
    for line in sys.stdin:
        try:
            req = json.loads(line)
            method, params, request_id = req.get("method"), req.get("params", {}), req.get("id")
            if method == "initialize":
                out = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}},
                       "serverInfo": {"name": "fortnox-automation", "version": "0.1.0"}}
            elif method == "notifications/initialized":
                continue
            elif method == "tools/list":
                out = {"tools": _tools()}
            elif method == "tools/call":
                name, args = params.get("name"), params.get("arguments", {})
                max_items = min(int(args.get("max_items", 100)), 500)
                if name == "fortnox_list_invoices":
                    out = _result(client.list_invoices(max_items=max_items, **args.get("params", {})))
                elif name == "fortnox_list_customers":
                    out = _result(client.list_customers(max_items=max_items, **args.get("params", {})))
                elif name == "fortnox_preview_receipt":
                    out = _result(ReceiptWorkflow(client).preview(_receipt(args["receipt"])))
                elif name == "fortnox_create_invoice":
                    require_approval(args.get("approval_token"))
                    out = _result(client.create_invoice(args["invoice"]))
                elif name == "fortnox_book_receipt":
                    require_approval(args.get("approval_token"))
                    out = _result(ReceiptWorkflow(client).book(_receipt(args["receipt"]), approval_token=args.get("approval_token")))
                elif name == "fortnox_attach_voucher_document":
                    require_approval(args.get("approval_token"))
                    source = Path(args["source_document"])
                    uploaded = client.upload_archive_file(source)
                    file_row = uploaded.get("File", uploaded) if isinstance(uploaded, dict) else {}
                    file_id = file_row.get("Id") or file_row.get("ArchiveFileId")
                    if not file_id:
                        raise ValueError("Fortnox archive upload did not return a file ID")
                    connection = client.connect_voucher_file(
                        file_id, voucher_series=str(args["voucher_series"]),
                        voucher_number=args["voucher_number"], voucher_year=int(args["voucher_year"]))
                    out = _result({"upload": file_row, "connection": connection})
                elif name == "fortnox_delete_voucher":
                    require_approval(args.get("approval_token"))
                    out = _result(client.delete_voucher(
                        str(args["voucher_series"]), int(args["voucher_number"]),
                        financialyear=int(args["voucher_year"]), confirm=True))
                else:
                    raise ValueError(f"Unknown tool: {name}")
            else:
                raise ValueError(f"Unsupported method: {method}")
            if request_id is not None:
                print(json.dumps({"jsonrpc": "2.0", "id": request_id, "result": out}), flush=True)
        except Exception as exc:
            if req.get("id") is not None:
                print(json.dumps({"jsonrpc": "2.0", "id": req["id"], "error": {"code": -32000, "message": str(exc)}}), flush=True)


if __name__ == "__main__":
    main()
