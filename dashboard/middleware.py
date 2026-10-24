from django.shortcuts import render


class FriendlyErrorPagesMiddleware:
    """Replace any bare 404 (including Django's technical debug 404) with the
    branded page, so every unknown route is handled identically in dev and prod."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if (
            response.status_code == 404
            and request.headers.get("x-requested-with") != "XMLHttpRequest"
            and not request.path.startswith("/static/")
            and "text/html" in response.get("Content-Type", "text/html")
            and not getattr(response, "_friendly", False)
        ):
            response = render(request, "404.html", status=404)
            response._friendly = True
        return response


class PrivatePagesMiddleware:
    """Pages for a signed-in student hold their own notes and tasks: never let a shared cache keep them.
    Also turns off browser features the site never uses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and not response.has_header("Cache-Control"):
            response["Cache-Control"] = "private, no-cache"
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=(), usb=()")
        return response
