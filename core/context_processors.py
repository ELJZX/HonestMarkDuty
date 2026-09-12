from django.conf import settings


def project_context(request):
    return {
        "PROJECT_NAME": "HonestMarkDuty",
        "PROJECT_TAGLINE": "Честный знак · сменный контур",
        "ORGANIZATION_NAME": getattr(settings, "ORGANIZATION_NAME", ""),
        "ORGANIZATION_CITY": getattr(settings, "ORGANIZATION_CITY", ""),
    }
