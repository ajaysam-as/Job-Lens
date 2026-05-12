import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# ── Security ──────────────────────────────────────────────────────────────────
SECRET_KEY    = os.environ.get("SECRET_KEY", "change-me-in-production-use-a-long-random-string")
DEBUG = os.environ.get("DEBUG", "True") == "True"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")

# ── Apps ──────────────────────────────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "core",
]

# ── Middleware ────────────────────────────────────────────────────────────────
# NOTE: LocaleMiddleware must come AFTER SessionMiddleware and BEFORE CommonMiddleware
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",          # ← NEW: Tamil/English toggle
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF     = "joblens.urls"
WSGI_APPLICATION = "joblens.wsgi.application"

TEMPLATES = [{
    "BACKEND":  "django.template.backends.django.DjangoTemplates",
    "DIRS":     [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS":  {"context_processors": [
        "django.template.context_processors.debug",
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
        "django.template.context_processors.i18n",       # ← NEW: exposes LANGUAGE_CODE in templates
    ]},
}]

# ── Database ──────────────────────────────────────────────────────────────────
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600
    )
}

# ── Static files ──────────────────────────────────────────────────────────────
STATIC_URL       = "/static/"
STATIC_ROOT      = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"] if (BASE_DIR / "static").exists() else []
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ── Media files ───────────────────────────────────────────────────────────────
MEDIA_URL  = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ── Auth ──────────────────────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LOGIN_URL          = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"

# ── Internationalisation ──────────────────────────────────────────────────────
# FIX 4: Full i18n setup for Tamil/English toggle
from django.utils.translation import gettext_lazy as _

LANGUAGE_CODE = "en"           # default language
TIME_ZONE     = "Asia/Kolkata"
USE_I18N      = True
USE_L10N      = True
USE_TZ        = True

LANGUAGES = [
    ("en", _("English")),
    ("ta", _("தமிழ்")),
]

# Where Django looks for .po / .mo translation files
LOCALE_PATHS = [
    BASE_DIR / "locale",
]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Third-party API keys ──────────────────────────────────────────────────────
GROQ_API_KEY            = os.environ.get("GROQ_API_KEY",            "")
RAZORPAY_KEY_ID         = os.environ.get("RAZORPAY_KEY_ID",         "rzp_test_XXXXXXXXXXXX")
RAZORPAY_KEY_SECRET     = os.environ.get("RAZORPAY_KEY_SECRET",     "")
RAZORPAY_WEBHOOK_SECRET = os.environ.get("RAZORPAY_WEBHOOK_SECRET", "")
TWILIO_ACCOUNT_SID      = os.environ.get("TWILIO_ACCOUNT_SID",      "")
TWILIO_AUTH_TOKEN       = os.environ.get("TWILIO_AUTH_TOKEN",       "")
TWILIO_WHATSAPP_FROM    = os.environ.get("TWILIO_WHATSAPP_FROM",    "whatsapp:+14155238886")

# ── Email ─────────────────────────────────────────────────────────────────────
EMAIL_BACKEND       = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST          = "smtp.gmail.com"
EMAIL_PORT          = 587
EMAIL_USE_TLS       = True
EMAIL_HOST_USER     = os.environ.get("EMAIL_HOST_USER",     "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL  = os.environ.get("DEFAULT_FROM_EMAIL",  "JobLens <noreply@joblens.in>")

# ── Logging ───────────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "[{asctime}] {levelname} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "core":   {"handlers": ["console"], "level": "DEBUG",   "propagate": False},
    },
}

# ── CSRF ──────────────────────────────────────────────────────────────────────
CSRF_TRUSTED_ORIGINS = os.environ.get(
    "CSRF_TRUSTED_ORIGINS",
    "https://job-lens-production-b268.up.railway.app"
).split(",")

# ── Security headers (production only) ───────────────────────────────────────
if not DEBUG:
    SECURE_BROWSER_XSS_FILTER     = True
    SECURE_CONTENT_TYPE_NOSNIFF   = True
    X_FRAME_OPTIONS                = "DENY"
    SECURE_SSL_REDIRECT            = True
    SESSION_COOKIE_SECURE          = True
    CSRF_COOKIE_SECURE             = True
    SECURE_HSTS_SECONDS            = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_PROXY_SSL_HEADER        = ("HTTP_X_FORWARDED_PROTO", "https")
