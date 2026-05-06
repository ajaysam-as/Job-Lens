from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
 
urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
 
# Admin branding
admin.site.site_header  = "JobLens Admin"
admin.site.site_title   = "JobLens"
admin.site.index_title  = "Welcome to JobLens Admin"
 