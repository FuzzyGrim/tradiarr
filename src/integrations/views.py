"""Contains views for importing and exporting media data from various sources."""

import json
import logging
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpResponse
from django.shortcuts import redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

import app
import users
from integrations import exports, tasks
from integrations.imports import simkl

logger = logging.getLogger(__name__)


@require_GET
def import_trakt(request):
    """View for importing anime and manga data from Trakt."""
    username = request.GET["trakt"]
    tasks.import_trakt.delay(username, request.user)
    messages.success(request, "Trakt import task queued.")
    return redirect("profile")


@require_GET
def simkl_oauth(request):
    """View for initiating the SIMKL OAuth2 authorization flow."""
    domain = request.get_host()
    scheme = request.scheme
    url = "https://simkl.com/oauth/authorize"

    return redirect(
        f"{url}?client_id={settings.SIMKL_ID}&redirect_uri={scheme}://{domain}/import/simkl&response_type=code",
    )


@require_GET
def import_simkl(request):
    """View for getting the SIMKL OAuth2 token."""
    token = simkl.get_token(request)
    tasks.import_simkl.delay(token, request.user)
    messages.success(request, "SIMKL import task queued.")
    return redirect("profile")


@require_GET
def import_mal(request):
    """View for importing anime and manga data from MyAnimeList."""
    username = request.GET["mal"]
    tasks.import_mal.delay(username, request.user)
    messages.success(request, "MyAnimeList import task queued.")
    return redirect("profile")


@require_POST
def import_tmdb_ratings(request):
    """View for importing TMDB movie and TV ratings."""
    tasks.import_tmdb.delay(
        request.FILES["tmdb_ratings"],
        request.user,
        "Completed",
    )
    messages.success(request, "TMDB ratings import task queued.")
    return redirect("profile")


@require_POST
def import_tmdb_watchlist(request):
    """View for importing TMDB movie and TV watchlist."""
    tasks.import_tmdb.delay(
        request.FILES["tmdb_watchlist"],
        request.user,
        "Planning",
    )
    messages.success(request, "TMDB watchlist import task queued.")
    return redirect("profile")


@require_GET
def import_anilist(request):
    """View for importing anime and manga data from AniList."""
    username = request.GET["anilist"]
    tasks.import_anilist.delay(username, request.user)
    messages.success(request, "AniList import task queued.")
    return redirect("profile")


@require_GET
def import_kitsu_name(request):
    """View for importing anime and manga data from Kitsu by username."""
    username = request.GET["kitsu_username"]
    tasks.import_kitsu_name.delay(username, request.user)
    messages.success(request, "Kitsu import task queued.")
    return redirect("profile")


@require_GET
def import_kitsu_id(request):
    """View for importing anime and manga data from Kitsu by user ID."""
    user_id = request.GET["kitsu_id"]
    tasks.import_kitsu_id.delay(user_id, request.user)
    messages.success(request, "Kitsu import task queued.")
    return redirect("profile")


@require_POST
def import_yamtrack(request):
    """View for importing anime and manga data from Yamtrack CSV."""
    tasks.import_yamtrack.delay(request.FILES["yamtrack_csv"], request.user)
    messages.success(request, "Yamtrack import task queued.")
    return redirect("profile")


@require_GET
def export_csv(request):
    """View for exporting all media data to a CSV file."""
    today = datetime.now(tz=settings.TZ).strftime("%Y-%m-%d")
    # Create the HttpResponse object with the appropriate CSV header.
    response = HttpResponse(
        content_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="yamtrack_{today}.csv"'},
    )

    response = exports.db_to_csv(response, request.user)

    logger.info("User %s successfully exported their data", request.user.username)

    return response


@csrf_exempt
@require_POST
def jellyfin_webhook(request, token):
    """Handle Jellyfin webhook notifications for media playback."""
    try:
        user = users.models.User.objects.get(token=token)
    except ObjectDoesNotExist:
        logger.warning(
            "Could not process Jellyfin webhook: Invalid token: %s",
            token,
        )
        return HttpResponse(status=401)

    payload = json.loads(request.body)
    event_type = payload["Event"]

    if event_type not in ("Stop", "MarkPlayed"):
        logger.info("Ignoring Jellyfin webhook event: %s", event_type)
        return HttpResponse(status=200)

    if payload["Item"]["Type"] == "Episode":
        media_type = "tv"
    elif payload["Item"]["Type"] == "Movie":
        media_type = "movie"
    else:
        logger.info("Ignoring Jellyfin webhook event: %s", media_type)
        return HttpResponse(status=200)

    media_id = payload["Item"]["ProviderIds"].get("Tmdb")
    if media_id is None:
        series = payload.get("Series")
        if series:
            media_id = series.get("ProviderIds").get("Tmdb")

    if media_id is None:
        logger.info(
            "Ignoring Jellyfin webhook call because no TMDB ID was found.",
        )
        return HttpResponse(status=200)

    played = payload["Item"]["UserData"]["Played"]

    if media_type == "tv":
        tv_metadata = app.providers.tmdb.tv_with_seasons(
            media_id,
            [payload["Item"]["ParentIndexNumber"]],
        )
        season_metadata = tv_metadata[f"season/{payload['Item']['ParentIndexNumber']}"]

        tv_item, _ = app.models.Item.objects.get_or_create(
            media_id=media_id,
            source="tmdb",
            media_type="tv",
            defaults={
                "title": tv_metadata["title"],
                "image": tv_metadata["image"],
            },
        )

        tv_instance, _ = app.models.TV.objects.update_or_create(
            item=tv_item,
            user=user,
            defaults={
                "status": app.models.STATUS_IN_PROGRESS,
            },
        )

        season_item, _ = app.models.Item.objects.get_or_create(
            media_id=media_id,
            source="tmdb",
            media_type="season",
            season_number=payload["Item"]["ParentIndexNumber"],
            defaults={
                "title": tv_metadata["title"],
                "image": season_metadata["image"],
            },
        )

        season_instance, _ = app.models.Season.objects.update_or_create(
            item=season_item,
            user=user,
            related_tv=tv_instance,
            defaults={
                "status": app.models.STATUS_IN_PROGRESS,
            },
        )

        episode_item, _ = app.models.Item.objects.get_or_create(
            media_id=media_id,
            source="tmdb",
            media_type="episode",
            season_number=payload["Item"]["ParentIndexNumber"],
            episode_number=payload["Item"]["IndexNumber"],
            defaults={
                "title": tv_metadata["title"],
                "image": season_metadata["image"],
            },
        )

        if played:
            app.models.Episode.objects.get_or_create(
                item=episode_item,
                related_season=season_instance,
                defaults={
                    "watch_date": datetime.now(tz=settings.TZ),
                },
            )

    elif media_type == "movie":
        media_metadata = app.providers.tmdb.movie(media_id)
        image = media_metadata["image"]

        # Get or create item
        item, _ = app.models.Item.objects.get_or_create(
            media_id=media_id,
            source="tmdb",
            media_type=media_type,
            defaults={
                "title": media_metadata["title"],
                "image": image,
            },
        )

        app.models.Movie.objects.update_or_create(
            item=item,
            user=user,
            defaults={
                "progress": 1 if played else 0,
                "status": app.models.STATUS_COMPLETED
                if played
                else app.odels.STATUS_IN_PROGRESS,
            },
        )

    return HttpResponse(status=200)
