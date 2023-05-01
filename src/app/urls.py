from django.urls import path, register_converter
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

from decouple import config
from . import converters, views

register_converter(converters.MediaTypeChecker, 'media_type')
register_converter(converters.StatusChecker, 'status')

urlpatterns = [
    path("", views.home, name="home"),
    path("medialist/<media_type:media_type>", views.media_list, name="medialist"),
    path("medialist/<media_type:media_type>/<status:status>", views.media_list, name="medialist_status"),
    path("search", views.media_search, name="search"),
    path("details/<media_type:media_type>/<int:media_id>/<str:title>", views.details, name="details"),
    path("profile", views.profile, name="profile"),
    path("login", views.UpdatedLoginView.as_view(), name="login"),
    path("logout", auth_views.LogoutView.as_view(), name="logout"),
    path("modal_data", views.modal_data, name="modal_data"),
    path("progress_edit", views.progress_edit, name="progress_edit"),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if config("REGISTRATION", default=True, cast=bool):
    urlpatterns.append(path("register/", views.register, name="register"))
