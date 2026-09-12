from core.audit import set_current_user


class CurrentUserMiddleware:
    """Прокидывает текущего пользователя в thread-local для аудита."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user if getattr(request, "user", None) and request.user.is_authenticated else None
        set_current_user(user)
        try:
            return self.get_response(request)
        finally:
            set_current_user(None)
