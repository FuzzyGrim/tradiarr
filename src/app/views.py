from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.views import LoginView
from django.contrib.auth.decorators import login_required
from django.utils.http import url_has_allowed_host_and_scheme
from django.http import JsonResponse
from django.conf import settings
from django.template.loader import render_to_string

from app.models import Media, Season
from app.forms import (
    UserLoginForm,
    UserRegisterForm,
    UserUpdateForm,
    PasswordChangeForm,
)
from app.utils import database, interactions, imports, helpers

import logging

logger = logging.getLogger(__name__)


@login_required
def home(request):
    media_list = Media.objects.filter(
        user_id=request.user, status__in=["Watching", "Paused"]
    ).order_by("media_type", "-status", "title")

    # Create a dictionary to group the results by media_type and status
    media_dict = {}
    for media in media_list:
        key = f"{media.media_type}_{media.status}"
        if key not in media_dict:
            if media.status == "Watching":
                list_title = f"{media.media_type.capitalize()} in Progress"
            elif media.status == "Paused":
                list_title = f"{media.media_type.capitalize()} on Hold"
            media_dict[key] = {
                "list_title": list_title,
                "media_list": [],
            }
        media_dict[key]["media_list"].append(media)

    context = {
        "page": "home",
        "media_dict": media_dict,
    }
    return render(request, "app/home.html", context)


@login_required
def medialist(request, media_type, status=None):

    if media_type not in ["anime", "manga", "tv", "movie"]:
        return error_view(request, status_code=404)

    if status and status not in ["completed", "watching", "paused", "dropped", "planning"]:
        return error_view(request, status_code=404)

    if request.method == "POST":
        if "delete" in request.POST:
            metadata = request.session.get("metadata")
            Media.objects.get(
                media_id=metadata["id"],
                media_type=media_type,
                user=request.user,
                api=metadata["api"],
            ).delete()
        # media edit triggered
        elif "status" in request.POST:
            database.edit_media(request)

        if status:
            return redirect("medialist", media_type=media_type, status=status)
        else:
            return redirect("medialist", media_type=media_type)

    if status:
        media_list = Media.objects.filter(
            user_id=request.user, media_type=media_type, status=status.capitalize()
        ).prefetch_related("seasons")
    else:
        media_list = Media.objects.filter(
            user_id=request.user, media_type=media_type
        ).prefetch_related("seasons")

    return render(
        request,
        "app/medialist.html",
        {
            "page": media_type,
            "media_list": media_list,
            "statuses": [
                "All",
                "Completed",
                "Watching",
                "Paused",
                "Dropped",
                "Planning",
            ],
        },
    )


@login_required
def search(request):
    api = request.GET.get("api")
    query = request.GET.get("q")
    request.session["last_selected_api"] = api
    if request.method == "POST":
        metadata = request.session.get("metadata")
        if "delete" in request.POST:
            Media.objects.get(
                media_id=metadata["id"],
                media_type=metadata["media_type"],
                user=request.user,
                api=metadata["api"],
            ).delete()
        elif "status" in request.POST:
            if Media.objects.filter(
                media_id=metadata["id"],
                user=request.user,
                api=metadata["api"],
            ).exists():
                database.edit_media(request)
            else:
                database.add_media(request)

        return redirect("/search?api=" + api + "&q=" + query)

    query_list = interactions.search(api, query)
    context = {"query_list": query_list}
    return render(request, "app/search.html", context)


def register(request):
    form = UserRegisterForm(request.POST if request.method == "POST" else None)
    if form.is_valid():
        form.save()
        messages.success(request, "Your account has been created, you can now log in!")
        logger.info(
            f"New user registered: {form.cleaned_data.get('username')} at {helpers.get_client_ip(request)}"
        )
        return redirect("login")
    return render(request, "app/register.html", {"form": form, "page": "register"})


class UpdatedLoginView(LoginView):
    form_class = UserLoginForm
    template_name = "app/login.html"

    def form_valid(self, form):
        remember_me = form.cleaned_data["remember_me"]
        if remember_me:
            self.request.session.set_expiry(2592000)  # 30 days
            self.request.session.modified = True

        logger.info(
            f"User logged in as: {self.request.POST['username']} at {helpers.get_client_ip(self.request)}"
        )
        return super(UpdatedLoginView, self).form_valid(form)

    def form_invalid(self, form):
        messages.error(
            self.request,
            "Please enter a correct username and password. Note that both fields are case-sensitive.",
        )
        logger.error(
            f"Failed login attempt for: {self.request.POST['username']} at {helpers.get_client_ip(self.request)}"
        )
        return super(UpdatedLoginView, self).form_invalid(form)


@login_required
def profile(request):
    user_form = UserUpdateForm(instance=request.user)
    password_form = PasswordChangeForm(request.user)

    if request.method == "POST":
        if "default_api" in request.POST:
            user_form = UserUpdateForm(request.POST, instance=request.user)
            if user_form.is_valid():
                user_form.save()
                messages.success(request, "Your account has been updated!")
                logger.info("Successful account update for: " + request.user.username)
                return redirect("profile")

        elif "new_password1" in request.POST:
            password_form = PasswordChangeForm(request.user, request.POST)
            if password_form.is_valid():
                password = password_form.save()
                update_session_auth_hash(request, password)
                messages.success(request, "Your password has been updated!")
                logger.info("Successful password change for: " + request.user.username)
                return redirect("profile")

        elif "mal" in request.POST:
            logger.info(f"Importing {request.POST['mal']} from MyAnimeList")
            if imports.import_myanimelist(request.POST["mal"], request.user):
                messages.success(request, "Your MyAnimeList has been imported!")
                logger.info(
                    f"Finished importing {request.POST['mal']} from MyAnimeList"
                )
                return redirect("profile")
            else:
                messages.error(request, "MyAnimeList user not found")
                logger.error(
                    f"An error occurred while importing {request.POST['mal']} from MyAnimeList"
                )

        elif request.FILES.get("tmdb"):
            logger.info("Importing from TMDB csv file")
            if imports.import_tmdb(request.FILES.get("tmdb"), request.user):
                messages.success(request, "Your TMDB list has been imported!")
                logger.info("TMDB import successful")
                return redirect("profile")
            else:
                messages.error(
                    request,
                    'Error importing your list, make sure it\'s a CSV file containing the word "ratings" or "watchlist" in the name',
                )
                logger.error("TMDB import failed")

        elif "anilist" in request.POST:
            logger.info(f"Importing {request.POST['anilist']} from Anilist")
            error = imports.import_anilist(request.POST["anilist"], request.user)
            if error == "":
                messages.success(request, "Your AniList has been imported!")
                logger.info(
                    f"Finished importing {request.POST['anilist']} from Anilist"
                )
                return redirect("profile")
            elif error == "User not found":
                messages.error(request, "AniList user not found")
                logger.error(
                    f"An error occurred while importing {request.POST['anilist']} from Anilist"
                )
            else:
                title = "Couldn't find a matching MAL ID for: \n"
                messages.error(request, title + error)
                return redirect("profile")

        else:
            messages.error(request, "There was an error with your request")

    context = {
        "user_form": user_form,
        "password_form": password_form,
        "page": "profile",
    }
    return render(request, "app/profile.html", context)


def edit(request):
    media_type = request.GET.get("media_type")
    media_id = request.GET.get("media_id")

    if media_type in ["anime", "manga"]:
        media = interactions.mal_edit(request, media_type, media_id)
    elif media_type in ["movie", "tv"]:
        media = interactions.tmdb_edit(request, media_type, media_id)

    response = media["response"]

    # Save the metadata in the session to be used when form is submitted
    request.session["metadata"] = response

    data = {
        "title": response.get("title", None),
        "year": response.get("year", None),
        "media_type": response.get("media_type", None),
        "original_type": response.get("original_type", None),
    }

    media["response"]["media_type"] = media_type
    data["html"] = render_to_string("app/edit.html", {"media": media}, request=request)

    if "seasons" in response and len(response["seasons"]) > 1:
        data["seasons"] = response["seasons"]

    if "database" in media:
        database = media["database"]

        data["in_db"] = True
        data["media_seasons"] = list(
            Season.objects.filter(media=database).values(
                "number",
                "score",
                "status",
                "progress",
                "start_date",
                "end_date",
            )
        )
        data["score"] = database.score
        data["status"] = database.status
        data["progress"] = database.progress
        data["start_date"] = database.start_date
        data["end_date"] = database.end_date
    else:
        data["in_db"] = False

    return JsonResponse(data)


def redirect_after_login(request):
    next = request.GET.get("next", None)
    if next is None:
        return redirect(settings.LOGIN_REDIRECT_URL)
    elif not url_has_allowed_host_and_scheme(
        url=next,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(settings.LOGIN_REDIRECT_URL)
    else:
        return redirect(next)


def error_view(request, exception=None, status_code=None):
    return render(
        request,
        "app/error.html",
        {"status_code": status_code},
        status=status_code,
    )
