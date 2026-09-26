import os
import unittest
from unittest.mock import patch

from fortnox_automation.security import ApprovalError, require_approval


class ApprovalSecurityTests(unittest.TestCase):
    def test_missing_configuration_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ApprovalError):
                require_approval("APPROVED")

    def test_literal_approved_is_not_a_magic_bypass(self):
        with patch.dict(os.environ, {"FORTNOX_APPROVAL_TOKEN": "long-random-test-secret"}):
            with self.assertRaises(ApprovalError):
                require_approval("APPROVED")
            require_approval("long-random-test-secret")

    def test_mismatch_does_not_reveal_expected_token(self):
        with patch.dict(os.environ, {"FORTNOX_APPROVAL_TOKEN": "long-random-test-secret"}):
            with self.assertRaisesRegex(ApprovalError, "Explicit approval token"):
                require_approval("wrong-token")
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ApprovalError, "FORTNOX_APPROVAL_TOKEN"):
                require_approval(None)


if __name__ == "__main__":
    unittest.main()
