from pathlib import Path
import os

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Web settings only: load local credentials without changing the tkinter entry points.
# Existing process environment variables take precedence over values in .env.
load_dotenv(BASE_DIR / ".env")

LOCAL_SECRET_KEY = "local-only-hanamans-profit-tool"


def _secret_key_from_environment():
    """Use the local key when DJANGO_SECRET_KEY is absent or blank."""
    return os.getenv("DJANGO_SECRET_KEY") or LOCAL_SECRET_KEY


SECRET_KEY = _secret_key_from_environment()
DEBUG = True
# This is a local utility: allow a Chromebook/phone to connect using the host PC's LAN IP.
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "profit_web",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
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
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}
LANGUAGE_CODE = "ja"
TIME_ZONE = "Asia/Tokyo"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
