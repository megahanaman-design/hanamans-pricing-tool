import os
import json
import subprocess
import sys
from unittest import TestCase
from unittest.mock import patch

from django.core.signing import Signer
from django.core.exceptions import ImproperlyConfigured

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

    def test_vercel_requires_nonempty_secret_key(self):
        for environment in ({"VERCEL": "1"}, {"VERCEL_ENV": "production"},
                            {"VERCEL": "1", "DJANGO_SECRET_KEY": ""}):
            with self.subTest(environment=environment), patch.dict(os.environ, environment, clear=True):
                with self.assertRaisesRegex(ImproperlyConfigured, "DJANGO_SECRET_KEY"):
                    settings._secret_key_from_environment()


class DatabaseSettingsTests(TestCase):
    def test_missing_database_url_keeps_local_sqlite(self):
        database = settings._database_from_environment("")
        self.assertEqual(database["ENGINE"], "django.db.backends.sqlite3")
        self.assertEqual(database["NAME"], settings.BASE_DIR / "db.sqlite3")

    def test_postgres_url_is_parsed_and_query_options_are_preserved(self):
        database = settings._database_from_environment(
            "postgresql://user%40shop:p%40ss%2Fword@db.example.com:6543/profit%20tool"
            "?sslmode=require&connect_timeout=10"
        )
        self.assertEqual(database["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(database["USER"], "user@shop")
        self.assertEqual(database["PASSWORD"], "p@ss/word")
        self.assertEqual(database["HOST"], "db.example.com")
        self.assertEqual(database["PORT"], 6543)
        self.assertEqual(database["NAME"], "profit tool")
        self.assertEqual(database["OPTIONS"], {"sslmode": "require", "connect_timeout": "10"})


class DeploymentSettingsTests(TestCase):
    def test_vercel_detection_enables_production_proxy_settings(self):
        code = (
            "import json; from hanamans_profit_web import settings; "
            "print(json.dumps({'debug': settings.DEBUG, 'hosts': settings.ALLOWED_HOSTS, "
            "'proxy': settings.SECURE_PROXY_SSL_HEADER}))"
        )
        environment = os.environ.copy()
        environment.update({"VERCEL": "1", "VERCEL_URL": "preview.example.vercel.app",
                            "DJANGO_SECRET_KEY": "deployment-test-only"})
        result = subprocess.run(
            [sys.executable, "-c", code], check=True, capture_output=True, text=True,
            cwd=settings.BASE_DIR, env=environment,
        )
        deployed = json.loads(result.stdout)
        self.assertFalse(deployed["debug"])
        self.assertIn(".vercel.app", deployed["hosts"])
        self.assertIn("preview.example.vercel.app", deployed["hosts"])
        self.assertEqual(deployed["proxy"], ["HTTP_X_FORWARDED_PROTO", "https"])

    def test_local_defaults_remain_debug_and_lan_friendly(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertFalse(settings._is_vercel_environment())
        if not settings.IS_VERCEL:
            self.assertTrue(settings.DEBUG)
            self.assertEqual(settings.ALLOWED_HOSTS, ["*"])
