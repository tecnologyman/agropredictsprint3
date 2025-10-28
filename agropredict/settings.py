import os
from pathlib import Path
import dj_database_url
from dotenv import load_dotenv
from django.contrib.messages import constants as messages

# -------------------------------
# BASE Y VARIABLES DE ENTORNO
# -------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')

# -------------------------------
# SEGURIDAD
# -------------------------------
SECRET_KEY = os.getenv('SECRET_KEY', 'django-insecure-change-this-in-production-agropredict-2024')
DEBUG = True  # For demo purposes
ALLOWED_HOSTS = [
    '127.0.0.1',
    'localhost',
    'sprint3.agropredict.tecnologyman.cl',
    'https://fdsw.agropredict.tecnologyman.cl',
    '.up.railway.app',
]

CSRF_TRUSTED_ORIGINS = [
    'https://sprint3.agropredict.tecnologyman.cl',
    'https://fdsw.agropredict.tecnologyman.cl',
    'https://*.up.railway.app',
]

# -------------------------------
# APLICACIONES
# -------------------------------
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',  # Mantenerla, aunque no haya login
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'predicciones',
]

# -------------------------------
# MIDDLEWARE
# -------------------------------
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',  # Archivos estáticos
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    # ⚠️ Puedes comentar la siguiente línea si no usas request.user en templates:
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# -------------------------------
# URLS Y WSGI
# -------------------------------
ROOT_URLCONF = 'agropredict.urls'
WSGI_APPLICATION = 'agropredict.wsgi.application'

# -------------------------------
# TEMPLATES
# -------------------------------
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',  # OK aunque no haya login
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

# -------------------------------
# BASE DE DATOS (Railway o local)
# -------------------------------
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# -------------------------------
# VALIDACIÓN DE CONTRASEÑAS
# -------------------------------
AUTH_PASSWORD_VALIDATORS = []  # Desactivadas para demo

# -------------------------------
# INTERNACIONALIZACIÓN
# -------------------------------
LANGUAGE_CODE = 'es-cl'
TIME_ZONE = 'America/Santiago'
USE_I18N = True
USE_TZ = True

# -------------------------------
# ARCHIVOS ESTÁTICOS Y MEDIA
# -------------------------------
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# -------------------------------
# LOGGING Y MENSAJES
# -------------------------------
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': LOGS_DIR / 'agropredict.log',
        },
    },
    'loggers': {
        'agropredict.apis': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
}

MESSAGE_TAGS = {
    messages.DEBUG: 'info',
    messages.INFO: 'info',
    messages.SUCCESS: 'success',
    messages.WARNING: 'warning',
    messages.ERROR: 'error',
}

# -------------------------------
# LOGIN / REDIRECCIONES (DESACTIVADO)
# -------------------------------
LOGIN_URL = '/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

# -------------------------------
# CONFIG PERSONALIZADA
# -------------------------------
ACCUWEATHER_API_KEY = os.environ.get('ACCUWEATHER_API_KEY', 'demo_key')

ECONOMIC_ANALYSIS_DEFAULTS = {
    'PRECIO_AGUA_M3': 150,
    'TASA_DESCUENTO': 0.08,
    'AÑOS_PROYECCION': 5,
}

FASTAPI_BASE_URL = os.getenv("FASTAPI_BASE_URL", "http://localhost:8001")

# -------------------------------
# SEGURIDAD EXTRA PARA PRODUCCIÓN
# -------------------------------
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000  # 1 año
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
