from django.conf import settings

from config.version import get_version


def project_context(request):
    return {
        "PROJECT_NAME": "HonestMarkDuty",
        "PROJECT_TAGLINE": "Честное выполнение обязанностей",
        "APP_VERSION": get_version(),
        "ORGANIZATION_NAME": getattr(settings, "ORGANIZATION_NAME", ""),
        "ORGANIZATION_CITY": getattr(settings, "ORGANIZATION_CITY", ""),
    }
