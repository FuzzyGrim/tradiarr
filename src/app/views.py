import logging

from django.apps import apps
from django.contrib import messages
from django.db.models import F
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from app.forms import FilterForm, get_form_class
from app.models import Anime, Episode, Manga, Movie, Season
from app.utils import form_handlers, metadata, search

logger = logging.getLogger(__name__)


def home(request: HttpRequest) -> HttpResponse:
    """Return the home page."""
    in_progress = {}

    movies = Movie.objects.filter(user=request.user, status="In progress")
    if movies.exists():
        in_progress["movie"] = movies

    seasons = Season.objects.filter(
        user=request.user,
        status="In progress",
    ).prefetch_related("episodes")

    if seasons.exists():
        in_progress["season"] = seasons

    animes = Anime.objects.filter(user=request.user, status="In progress")
    if animes.exists():
        in_progress["anime"] = animes

    mangas = Manga.objects.filter(user=request.user, status="In progress")
    if mangas.exists():
        in_progress["manga"] = mangas

    context = {
        "in_progress": in_progress,
    }
    return render(request, "app/home.html", context)


def progress_edit(request: HttpRequest) -> HttpResponse:
    """Increase or decrease the progress of a media item from home page."""

    media_type = request.POST.get("media_type")
    media_id = request.POST.get("media_id")
    operation = request.POST.get("operation")

    if media_type == "season":
        season_number = request.POST.get("season_number")
        season_metadata = metadata.season(media_id, season_number)
        max_progress = len(season_metadata["episodes"])
        search_params = {
            "media_id": media_id,
            "user": request.user,
            "season_number": season_number,
        }

    else:
        media_metadata = metadata.get_media_metadata(media_type, media_id)
        max_progress = media_metadata.get("num_episodes", 1)
        search_params = {"media_id": media_id, "user": request.user}

    model = apps.get_model(app_label="app", model_name=media_type)

    try:
        media = model.objects.get(**search_params)

        if operation == "increase":
            media.increase_progress()

        elif operation == "decrease":
            media.decrease_progress()

        response = {
            "media_id": media_id,
            "progress": media.progress,
            "max": media.progress == max_progress,
        }

        if media_type == "season":
            response["season_number"] = season_number

        return render(
            request,
            "app/components/progress_changer.html",
            {"media": response, "media_type": media_type},
        )
    except model.DoesNotExist:
        messages.error(
            request, "Media item was deleted before trying to change progress"
        )
        logger.exception("Media item was deleted before trying to change progress")

        response = HttpResponse()
        response["HX-Redirect"] = reverse("home")
        return response


def media_list(request: HttpRequest, media_type: str) -> HttpResponse:
    """Return the media list page."""

    if request.method == "POST":
        form_handlers.media_form_handler(request)
        return redirect("medialist", media_type=media_type)

    filter_params = {"user": request.user.id}

    # filter by status if status is not "all", default to "all"
    status_filter = request.GET.get("status", "all")
    if status_filter != "all":
        filter_params["status"] = status_filter.capitalize()

    # default sort by descending score
    sort_filter = request.GET.get("sort", "score")

    # update user default layout for media type
    default_layout = request.user.default_layout[media_type]
    current_layout = request.GET.get("layout", default_layout)
    request.user.default_layout[media_type] = current_layout
    request.user.save()

    # fill form with current values if they exist
    filter_form = FilterForm(request.GET or None, default_layout=current_layout)

    # if form valid or no form submitted
    if filter_form.is_valid() or not request.GET:

        model = apps.get_model(app_label="app", model_name=media_type)

        if media_type == "tv" and (
            current_layout == "app/media_table.html"
            or sort_filter in ("progress", "start_date", "end_date")
        ):
            media_list = model.objects.filter(**filter_params).prefetch_related(
                "seasons",
                "seasons__episodes",
            )
        elif media_type == "season" and (
            current_layout == "app/media_table.html"
            or sort_filter in ("progress", "start_date", "end_date")
        ):
            media_list = Season.objects.filter(**filter_params).prefetch_related(
                "episodes",
            )
        else:
            media_list = model.objects.filter(**filter_params)

        # python for @property sorting
        if media_type in ("tv", "season") and sort_filter in (
            "progress",
            "start_date",
            "end_date",
        ):
            media_list = sorted(
                media_list,
                key=lambda x: getattr(x, sort_filter),
                reverse=True,
            )
        else:
            model = apps.get_model(app_label="app", model_name=media_type)
            # asc order
            if sort_filter == "title":
                media_list = media_list.order_by(
                    F(sort_filter).asc(),
                )
            # desc order
            else:
                media_list = media_list.order_by(
                    F(sort_filter).desc(),
                )

        return render(
            request,
            request.user.default_layout[media_type],
            {
                "media_type": media_type,
                "media_list": media_list,
                "filter_form": filter_form,
            },
        )

    logger.error("Invalid filter parameters: %s", {filter_form.errors.as_data})
    return redirect("medialist", media_type=media_type)


def media_search(request: HttpRequest) -> HttpResponse:
    """Return the media search page."""

    media_type = request.GET.get("media_type")
    query = request.GET.get("q")

    if request.method == "POST":
        form_handlers.media_form_handler(request)
        return redirect("/search?media_type=" + media_type + "&q=" + query)

    if media_type and query:
        # update user default search type
        request.user.last_search_type = media_type
        request.user.save()

        if media_type in ("anime", "manga"):
            query_list = search.mal(media_type, query)
        elif media_type in ("tv", "movie"):
            query_list = search.tmdb(media_type, query)

        context = {"query_list": query_list}

    else:
        context = {}

    return render(request, "app/search.html", context)


def media_details(
    request: HttpRequest,
    media_type: str,
    media_id: str,
    title: str,
) -> HttpResponse:
    """Return the details page for a media item."""

    media_metadata = metadata.get_media_metadata(media_type, media_id)

    if request.method == "POST":
        form_handlers.media_form_handler(request, title=media_metadata["title"])
        return redirect("media_details", media_type, media_id, title)

    related_data_list = [
        {"name": "Related Animes", "data": media_metadata.get("related_anime")},
        {"name": "Related Mangas", "data": media_metadata.get("related_manga")},
        {"name": "Recommendations", "data": media_metadata.get("recommendations")},
    ]

    context = {
        "media": media_metadata,
        "seasons": media_metadata.get("seasons"),
        "related_data_list": related_data_list,
    }
    return render(request, "app/media_details.html", context)


def season_details(
    request: HttpRequest,
    media_id: str,
    title: str,
    season_number: str,
) -> HttpResponse:
    """Return the details page for a season."""

    season_metadata = metadata.season(media_id, season_number)
    tv_metadata = metadata.tv(media_id)

    if request.method == "POST":
        # add tv show title to season metadata
        season_metadata["title"] = tv_metadata["title"]
        form_handlers.media_form_handler(
            request,
            season_metadata,
            season_number,
        )

        return redirect("season_details", media_id, title, season_number)

    watched_episodes = Episode.objects.filter(
        related_season__media_id=media_id,
        related_season__season_number=season_number,
        related_season__user=request.user,
    ).values_list("episode_number", "watch_date")

    watched_episodes_dict = dict(watched_episodes)

    for episode in season_metadata["episodes"]:
        episode_number = episode["episode_number"]
        episode["watched"] = episode_number in watched_episodes_dict
        if episode["watched"]:
            episode["watch_date"] = watched_episodes_dict[episode_number]

    context = {
        "media_id": media_id,
        "media_title": tv_metadata["title"],
        "season": season_metadata,
        "tv": tv_metadata,
    }
    return render(request, "app/season_details.html", context)


def track_form(request: HttpRequest) -> HttpResponse:
    """Return the tracking form for a media item."""

    media_type = request.GET.get("media_type")
    media_id = request.GET.get("media_id")
    season_number = request.GET.get("season_number")

    if media_type == "season":
        # set up filters to retrieve the appropriate media object
        filters = {
            "media_id": media_id,
            "user": request.user,
            "season_number": season_number,
        }
        initial_data = {
            "media_id": media_id,
            "media_type": media_type,
            "season_number": season_number,
        }
        title = f"{request.GET.get('title')} S{season_number}"
        form_id = f"form-{media_type}_{media_id}_{season_number}"

    else:
        filters = {"media_id": media_id, "user": request.user}
        initial_data = {"media_id": media_id, "media_type": media_type}
        title = request.GET.get("title")
        form_id = f"form-{media_type}_{media_id}"

    model = apps.get_model(app_label="app", model_name=media_type)

    try:
        # try to retrieve the media object using the filters
        media = model.objects.get(**filters)
        form = get_form_class(media_type)(instance=media, initial=initial_data)
        form.helper.form_id = form_id
        allow_delete = True
    except model.DoesNotExist:
        form = get_form_class(media_type)(initial=initial_data)
        form.helper.form_id = form_id
        allow_delete = False

    return render(
        request,
        "app/components/fill_track_form.html",
        {
            "title": title,
            "form_id": form_id,
            "form": form,
            "allow_delete": allow_delete,
        },
    )
