"""
joblens/urls.py  — root URL config
FIX 4: Added i18n_patterns + set_language endpoint for Tamil toggle.

The set_language view is built into Django — it reads `language` from POST
and sets the session/cookie. The navbar JS calls it, then reloads.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
import django.views.i18n as i18n_views

urlpatterns = [
    # Language-switcher endpoint (must be OUTSIDE i18n_patterns)
    path("i18n/setlang/", i18n_views.set_language, name="set_language"),
]

urlpatterns += i18n_patterns(
    path("admin/",  admin.site.urls),
    path("",        include("core.urls")),
    prefix_default_language=False,   # English URLs stay at /…, Tamil at /ta/…
)

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
