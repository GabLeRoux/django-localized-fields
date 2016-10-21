import dj_database_url

DEBUG = True
TEMPLATE_DEBUG = True

SECRET_KEY = 'this is my secret key'

TEST_RUNNER = 'django.test.runner.DiscoverRunner'

DATABASES = {
    'default': dj_database_url.config(default='postgres:///localized_fields')
}

LANGUAGE_CODE = 'en'
LANGUAGES = (
    ('en', 'English'),
    ('ro', 'Romanian'),
    ('nl', 'Dutch')
)

INSTALLED_APPS = [
    'localized_fields',
    'tests'
]
