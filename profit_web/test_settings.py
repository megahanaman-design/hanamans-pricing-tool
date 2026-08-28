import os
from unittest import TestCase
from unittest.mock import patch

from django.core.signing import Signer

from hanamans_profit_web import settings


class SecretKeySettingsTests(TestCase):
    def test_missing_secret_key_uses_local_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(settings._secret_key_from_environment(), settings.LOCAL_SECRET_KEY)

    def test_empty_secret_key_uses_local_fallback_and_can_sign_oauth_state(self):
        # This matches the first-run .env copied unchanged from .env.example.
        with patch.dict(os.environ, {"DJANGO_SECRET_KEY": ""}, clear=True):
            secret_key = settings._secret_key_from_environment()

        self.assertEqual(secret_key, settings.LOCAL_SECRET_KEY)
        signer = Signer(key=secret_key, fallback_keys=[])
        signed_state = signer.sign_object("oauth-state")
        self.assertEqual(signer.unsign_object(signed_state), "oauth-state")

    def test_configured_secret_key_is_used(self):
        with patch.dict(os.environ, {"DJANGO_SECRET_KEY": "configured-test-key"}, clear=True):
            self.assertEqual(settings._secret_key_from_environment(), "configured-test-key")
