from django.urls import path
from . import views
urlpatterns = [
    # ── Existing routes ───────────────────────────────────────────────────────
    path('',                        views.landing,               name='landing'),
    path('register/',               views.register_view,         name='register'),
    path('login/',                  views.login_view,            name='login'),
    path('logout/',                 views.logout_view,           name='logout'),
    path('dashboard/',              views.dashboard,             name='dashboard'),
    path('upload-resume/',          views.upload_resume,         name='upload_resume'),
    path('find-jobs/',              views.find_jobs,             name='find_jobs'),
    path('save-job/',               views.save_job,              name='save_job'),
    path('saved-jobs/',             views.saved_jobs,            name='saved_jobs'),
    path('generate-cover-letter/',  views.generate_cover_letter, name='generate_cover_letter'),
    path('profile/',                views.profile,               name='profile'),

    # ── New: Government Jobs ──────────────────────────────────────────────────
    path('govt-jobs/',              views.govt_jobs,             name='govt_jobs'),

    # ── New: Hirer Platform ───────────────────────────────────────────────────
    path('hirer/post/',                  views.post_job,         name='post_job'),

    path('hirer/dashboard/',             views.hirer_dashboard,  name='hirer_dashboard'),

    path("tracker/",                 views.tracker,        name="tracker"),
    path("tracker/update/<int:pk>/", views.tracker_update, name="tracker_update"),
    path("tracker/delete/<int:pk>/", views.tracker_delete, name="tracker_delete"),
    path("resume-tips/",             views.resume_tips,    name="resume_tips"),
]
