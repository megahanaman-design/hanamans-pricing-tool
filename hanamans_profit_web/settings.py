from pathlib import Path
import os
from urllib.parse import parse_qsl, unquote, urlsplit

from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

# Web settings only: load local credentials without changing the tkinter entry points.
# Existing process environment variables take precedence over values in .env.
load_dotenv(BASE_DIR / ".env")

LOCAL_SECRET_KEY = "local-only-hanamans-profit-tool"


def _is_vercel_environment():
    """Return whether settings are being loaded by a Vercel deployment."""
    return os.getenv("VERCEL") == "1" or bool(os.getenv("VERCEL_ENV"))


def _secret_key_from_environment(is_vercel=None):
    """Require a deployment secret while retaining the local-only fallback."""
    if is_vercel is None:
        is_vercel = _is_vercel_environment()
    secret_key = os.getenv("DJANGO_SECRET_KEY")
    if secret_key:
        return secret_key
    if is_vercel:
        raise ImproperlyConfigured(
            "DJANGO_SECRET_KEY must be set to a non-empty value on Vercel."
        )
    return LOCAL_SECRET_KEY


def _database_from_environment(database_url=None):
    """Build a Django database config without discarding URL query options."""
    database_url = database_url if database_url is not None else os.getenv("DATABASE_URL")
    if not database_url:
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}

    parsed = urlsplit(database_url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise ImproperlyConfigured("DATABASE_URL must use the postgres or postgresql scheme.")
    if not parsed.hostname or not parsed.path.lstrip("/"):
        raise ImproperlyConfigured("DATABASE_URL must include a host and database name.")

    database = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parsed.path.lstrip("/")),
        "HOST": parsed.hostname,
        "OPTIONS": dict(parse_qsl(parsed.query, keep_blank_values=True)),
    }
    if parsed.username is not None:
        database["USER"] = unquote(parsed.username)
    if parsed.password is not None:
        database["PASSWORD"] = unquote(parsed.password)
    try:
        if parsed.port is not None:
            database["PORT"] = parsed.port
    except ValueError as exc:
        raise ImproperlyConfigured("DATABASE_URL contains an invalid port.") from exc
    return database


SECRET_KEY = _secret_key_from_environment()
IS_VERCEL = _is_vercel_environment()
DEBUG = not IS_VERCEL
if IS_VERCEL:
    # A leading dot permits both vercel.app itself and deployment subdomains.
    ALLOWED_HOSTS = [".vercel.app"]
    for host_variable in ("VERCEL_URL", "VERCEL_PROJECT_PRODUCTION_URL"):
        if os.getenv(host_variable):
            ALLOWED_HOSTS.append(os.environ[host_variable].split(":", 1)[0])
    ALLOWED_HOSTS.extend(
        host.strip() for host in os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if host.strip()
    )
    CSRF_TRUSTED_ORIGINS = [
        f"https://*{host}" if host.startswith(".") else f"https://{host}"
        for host in ALLOWED_HOSTS
    ]
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = True
    CSRF_COOKIE_SECURE = True
else:
    # This is a local utility: retain access through the host PC's LAN IP.
    ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "profit_web",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "hanamans_profit_web.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": ["django.template.context_processors.request"]},
}]
WSGI_APPLICATION = "hanamans_profit_web.wsgi.application"
ASGI_APPLICATION = "hanamans_profit_web.asgi.application"
DATABASES = {"default": _database_from_environment()}
LANGUAGE_CODE = "ja"
TIME_ZONE = "Asia/Tokyo"
USE_I18N = True
USE_TZ = True
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
if IS_VERCEL:
    STORAGES = {
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
