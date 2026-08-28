import hashlib
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse


class EbayMarketplaceDeletionEndpointTests(TestCase):
    def test_challenge_response_uses_expected_hash(self):
        token = "A" * 32
        challenge = "challenge-123"
        with patch.dict("os.environ", {"EBAY_DELETION_VERIFY_TOKEN": token}, clear=False):
            response = self.client.get(
                reverse("profit_web:ebay_marketplace_deletion"),
                {"challenge_code": challenge},
                secure=True,
                HTTP_HOST="testserver",
            )

        endpoint = "https://testserver/ebay/marketplace-deletion/"
        expected = hashlib.sha256((challenge + token + endpoint).encode("utf-8")).hexdigest()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"challengeResponse": expected})

    def test_post_is_acknowledged_without_persisting_payload(self):
        response = self.client.post(
            reverse("profit_web:ebay_marketplace_deletion"),
            data='{"notification": {"data": {"userId": "example"}}}',
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 204)
