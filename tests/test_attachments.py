import json
import tempfile
import unittest
from pathlib import Path

from fortnox_automation.client import FortnoxClient, Response


class AttachmentTransport:
    def __init__(self):
        self.calls = []

    def __call__(self, url, method, headers, body):
        self.calls.append((url, method, dict(headers), body))
        if url.endswith('/3/archive'):
            return Response(201, {}, b'{"File":{"Id":"archive-id","ArchiveFileId":"file-id","Name":"receipt.pdf"}}')
        return Response(201, {}, b'{"VoucherFileConnection":{"FileId":"file-id","VoucherSeries":"A","VoucherNumber":"1","VoucherYear":4}}')


class AttachmentTests(unittest.TestCase):
    def test_uploads_multipart_archive_file(self):
        transport = AttachmentTransport()
        client = FortnoxClient(access_token='token', transport=transport)
        with tempfile.NamedTemporaryFile(suffix='.pdf') as f:
            f.write(b'%PDF-test')
            f.flush()
            result = client.upload_archive_file(Path(f.name))
        self.assertEqual(result['File']['ArchiveFileId'], 'file-id')
        url, method, headers, body = transport.calls[0]
        self.assertEqual(method, 'POST')
        self.assertIn('multipart/form-data; boundary=', headers['Content-Type'])
        self.assertIn(b'filename="', body)
        self.assertIn(b'%PDF-test', body)

    def test_connects_archive_file_to_voucher(self):
        transport = AttachmentTransport()
        client = FortnoxClient(access_token='token', transport=transport)
        result = client.connect_voucher_file('file-id', voucher_series='A', voucher_number=1, voucher_year=4)
        self.assertEqual(result['VoucherFileConnection']['FileId'], 'file-id')
        self.assertEqual(transport.calls[0][1], 'POST')
        payload = json.loads(transport.calls[0][3])
        self.assertEqual(payload['VoucherFileConnection']['VoucherSeries'], 'A')


if __name__ == '__main__':
    unittest.main()
