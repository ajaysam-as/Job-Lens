from django.urls import path
from . import views

urlpatterns = [
    path("",               views.index,          name="index"),
    path("analyze/",       views.analyze,         name="analyze"),
    path("rewrite-section/", views.rewrite_section, name="rewrite_section"),
]
