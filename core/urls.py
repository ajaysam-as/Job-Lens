from django.urls import path
from . import views
from .hirer_views import (
    post_job,
    initiate_payment,
    payment_callback,
    razorpay_webhook,
    hirer_dashboard,
)

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
    path('hirer/post/',                  post_job,         name='post_job'),
    path('hirer/pay/<int:posting_id>/',  initiate_payment, name='initiate_payment'),
    path('hirer/payment/callback/',      payment_callback, name='payment_callback'),
    path('hirer/payment/webhook/',       razorpay_webhook, name='razorpay_webhook'),
    path('hirer/dashboard/',             hirer_dashboard,  name='hirer_dashboard'),

    path("tracker/",                  views.tracker_view,           name="tracker"),
    path("tracker/update/",           views.update_tracker_status,  name="update_tracker_status"),
    path("tracker/delete/<int:pk>/",  views.delete_tracker,         name="delete_tracker"),
 
    # AI Resume Tips
    path("resume-tips/",              views.resume_tips_view,       name="resume_tips"),
 
]
