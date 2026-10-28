import os
from datetime import timedelta
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-in-production")
DEBUG = os.getenv("DEBUG", "True") == "True"
ALLOWED_HOSTS = [h.strip() for h in os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1,backend").split(",") if h.strip()]

# Render sets this to the service's public hostname (e.g. my-api.onrender.com)
RENDER_EXTERNAL_HOSTNAME = os.getenv("RENDER_EXTERNAL_HOSTNAME")
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

if not DEBUG and SECRET_KEY == "dev-secret-change-in-production":
    raise RuntimeError("Set SECRET_KEY when DEBUG=False.")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "channels",
    "research",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    # Hosted Postgres (Render, etc.) provides a single DATABASE_URL
    "default": dj_database_url.parse(os.environ["DATABASE_URL"], conn_max_age=60)
} if os.getenv("DATABASE_URL") else {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME":     os.getenv("POSTGRES_DB",       "research_db"),
        "USER":     os.getenv("POSTGRES_USER",     "research_user"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", "research_pass"),
        "HOST":     os.getenv("POSTGRES_HOST",     "db"),
        "PORT":     os.getenv("POSTGRES_PORT",     "5432"),
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG":  {"hosts": [os.getenv("REDIS_URL", "redis://redis:6379/0")]},
    }
}

# Comma-separated frontend origins, e.g. https://research-frontend.onrender.com. Unset = allow all (local dev).
CORS_ALLOWED_ORIGINS = [o.strip().rstrip("/") for o in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()]
CORS_ALLOW_ALL_ORIGINS = not CORS_ALLOWED_ORIGINS
CSRF_TRUSTED_ORIGINS = [o.strip().rstrip("/") for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o.strip()]
if RENDER_EXTERNAL_HOSTNAME:
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

# Behind Render's HTTPS proxy
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if not DEBUG:
    # Render already redirects http→https at the edge, so SECURE_SSL_REDIRECT is left off
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE    = True
    SECURE_HSTS_SECONDS   = 60 * 60 * 24 * 30

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME":  timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS":  True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default":     {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

GEMINI_API_KEY  = os.getenv("GEMINI_API_KEY",  "")
TAVILY_API_KEY  = os.getenv("TAVILY_API_KEY",  "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIM   = int(os.getenv("EMBEDDING_DIM", 384))
GEMINI_MODEL    = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
FORCE_MOCK_GEMINI = os.getenv("FORCE_MOCK_GEMINI", "False") == "True"
FORCE_MOCK_EMBEDDINGS = os.getenv("FORCE_MOCK_EMBEDDINGS", "False") == "True"
