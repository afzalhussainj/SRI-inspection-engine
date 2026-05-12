"""
URL configuration for inspection_engine project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve
from django.urls import include, path, re_path
from .views import ReactAppView


urlpatterns = [
    path('admin/', admin.site.urls),
    path("api/", include("forms.urls")),
]

# Serve static files in development only
# In production, WhiteNoise handles static files automatically
if settings.DEBUG:
    urlpatterns += [
        re_path(
            r"^assets/(?P<path>.*)$",
            serve,
            {"document_root": settings.STATICFILES_DIRS[0]},
        ),
        re_path(
            r"^(?P<path>vite\.svg)$",
            serve,
            {"document_root": settings.TEMPLATES[0]["DIRS"][0]},
        ),
    ]
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # Ephemeral disk only; no S3 in this stack. Branding logos and uploads need a URL.
    urlpatterns += [
        re_path(
            r"^media/(?P<path>.*)$",
            serve,
            {"document_root": settings.MEDIA_ROOT},
        ),
    ]

# Catch-all for React app (MUST be last!)
# Only enable when a built frontend bundle is present.
_template_dirs = settings.TEMPLATES[0].get("DIRS", []) if settings.TEMPLATES else []
_frontend_index = None
if _template_dirs:
    _candidate = _template_dirs[0]
    try:
        _frontend_index = _candidate / "index.html"
    except Exception:
        _frontend_index = None

if _frontend_index and _frontend_index.exists():
    urlpatterns += [
        re_path(r"^.*$", ReactAppView.as_view(), name="react"),
    ]
