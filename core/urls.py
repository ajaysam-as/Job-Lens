from django.urls import path
from . import views

urlpatterns = [
    path('', views.landing, name='landing'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('upload-resume/', views.upload_resume, name='upload_resume'),
    path('find-jobs/', views.find_jobs, name='find_jobs'),
    path('save-job/', views.save_job, name='save_job'),
    path('saved-jobs/', views.saved_jobs, name='saved_jobs'),
    path('generate-cover-letter/', views.generate_cover_letter, name='generate_cover_letter'),
    path('profile/', views.profile, name='profile'),
]
