import json
import tempfile
import unittest
from pathlib import Path

from fortnox_automation.audit import AuditLog
from fortnox_automation.client import FortnoxClient, Response
from fortnox_automation.orchestrator import Orchestrator


class FakeTransport:
    def __init__(self):
        self.calls = []
        self.page = 0

    def __call__(self, url, method, headers, body):
        self.calls.append((url, method, dict(headers), body))
        if "/invoices?" in url.lower():
            self.page += 1
            rows = [{"DocumentNumber": str(self.page)}] if self.page == 1 else []
            return Response(200, {}, json.dumps({"Invoices": rows}).encode())
        return Response(200, {}, b'{"Invoice": {"DocumentNumber": "42"}}')


class CoreTests(unittest.TestCase):
    def test_pagination_and_headers(self):
        transport = FakeTransport()
        client = FortnoxClient(access_token="test-token", transport=transport, sleep=lambda _: None)
        rows = client.list_invoices(page_size=1)
        self.assertEqual(rows, [{"DocumentNumber": "1"}])
        self.assertEqual(transport.calls[0][2]["Authorization"], "Bearer test-token")
        self.assertIn("page=2", transport.calls[1][0])

    def test_read_plan_executes_and_audits(self):
        transport = FakeTransport()
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.jsonl"
            orch = Orchestrator(FortnoxClient(access_token="x", transport=transport, sleep=lambda _: None), AuditLog(str(audit_path)))
            result = orch.run("Show unpaid customer invoices")
            self.assertEqual(result[0]["DocumentNumber"], "1")
            self.assertEqual(len(audit_path.read_text().splitlines()), 2)

    def test_unknown_side_effect_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            orch = Orchestrator(FortnoxClient(access_token="x"), AuditLog(str(Path(tmp) / "audit.jsonl")))
            with self.assertRaises(PermissionError):
                orch.run("Create and send an invoice")

    def test_missing_token_is_explicit(self):
        client = FortnoxClient(access_token=None)
        with self.assertRaisesRegex(Exception, "FORTNOX_ACCESS_TOKEN"):
            client.list_invoices()


if __name__ == "__main__":
    unittest.main()
