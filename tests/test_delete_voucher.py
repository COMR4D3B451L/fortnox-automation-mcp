import json
import unittest

from fortnox_automation.client import FortnoxClient, Response


class DeleteTransport:
    def __init__(self):
        self.calls = []

    def __call__(self, url, method, headers, body):
        self.calls.append((url, method, dict(headers), body))
        return Response(204, {}, b"")


class DeleteVoucherTests(unittest.TestCase):
    def test_requires_explicit_confirmation(self):
        transport = DeleteTransport()
        client = FortnoxClient(access_token="token", transport=transport)
        with self.assertRaises(ValueError):
            client.delete_voucher("A", 15, financialyear=4)
        self.assertEqual(transport.calls, [])

    def test_deletes_without_retry_and_passes_financial_year(self):
        transport = DeleteTransport()
        client = FortnoxClient(access_token="token", transport=transport)
        result = client.delete_voucher("A", 15, financialyear=4, confirm=True)
        self.assertIsNone(result)
        self.assertEqual(len(transport.calls), 1)
        url, method, headers, body = transport.calls[0]
        self.assertEqual(method, "DELETE")
        self.assertIn("/3/vouchers/A/15", url)
        self.assertIn("financialyear=4", url)
        self.assertIsNone(body)


if __name__ == "__main__":
    unittest.main()
