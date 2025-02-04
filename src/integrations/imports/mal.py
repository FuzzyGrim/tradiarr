import logging

from django.apps import apps
from django.conf import settings

import app
from app.models import Media
from integrations import helpers

logger = logging.getLogger(__name__)

base_url = "https://api.myanimelist.net/v2/users"


def importer(username, user, mode):
    """Import anime and manga from MyAnimeList."""
    anime_imported = import_media(username, user, "anime", mode)
    manga_imported = import_media(username, user, "manga", mode)
    return anime_imported, manga_imported


def import_media(username, user, media_type, mode):
    """Import media of a specific type from MyAnimeList."""
    logger.info("Fetching %s from MyAnimeList", media_type)
    params = {
        "fields": "list_status{comments,num_times_rewatched,num_times_reread}",
        "nsfw": "true",
        "limit": 1000,
    }
    url = f"{base_url}/{username}/{media_type}list"
    media_data = get_whole_response(url, params)
    bulk_media = add_media_list(media_data, media_type, user)

    model = apps.get_model(app_label="app", model_name=media_type)
    num_imported = helpers.bulk_chunk_import(bulk_media, model, user, mode)
    logger.info("Imported %s %s", num_imported, media_type)

    return num_imported


def get_whole_response(url, params):
    """Fetch whole data from user."""
    headers = {"X-MAL-CLIENT-ID": settings.MAL_API}
    data = app.providers.services.api_request(
        "MAL",
        "GET",
        url,
        params=params,
        headers=headers,
    )

    while "next" in data["paging"]:
        next_url = data["paging"]["next"]
        next_data = app.providers.services.api_request(
            "MAL",
            "GET",
            next_url,
            params=params,
            headers=headers,
        )
        data["data"].extend(next_data["data"])
        data["paging"] = next_data["paging"]

    return data


def add_media_list(response, media_type, user):
    """Add media to list for bulk creation."""
    logger.info("Importing %s from MyAnimeList", media_type)
    bulk_media = []

    for content in response["data"]:
        list_status = content["list_status"]
        status = get_status(list_status["status"])

        if media_type == "anime":
            progress = list_status["num_episodes_watched"]
            repeats = list_status["num_times_rewatched"]
            if list_status["is_rewatching"]:
                status = "Repeating"
        else:
            progress = list_status["num_chapters_read"]
            repeats = list_status["num_times_reread"]
            if list_status["is_rereading"]:
                status = "Repeating"

        try:
            image_url = content["node"]["main_picture"]["large"]
        except KeyError:
            image_url = settings.IMG_NONE

        item, _ = app.models.Item.objects.get_or_create(
            media_id=content["node"]["id"],
            source="mal",
            media_type=media_type,
            defaults={
                "title": content["node"]["title"],
                "image": image_url,
            },
        )

        model = apps.get_model(app_label="app", model_name=media_type)
        instance = model(
            item=item,
            user=user,
            score=list_status["score"],
            progress=progress,
            status=status,
            repeats=repeats,
            start_date=list_status.get("start_date", None),
            end_date=list_status.get("finish_date", None),
            notes=list_status["comments"],
        )
        bulk_media.append(instance)

    return bulk_media


def get_status(status):
    """Convert the status from MyAnimeList to the status used in the app."""
    status_mapping = {
        "completed": Media.Status.COMPLETED.value,
        "reading": Media.Status.IN_PROGRESS.value,
        "watching": Media.Status.IN_PROGRESS.value,
        "plan_to_watch": Media.Status.PLANNING.value,
        "plan_to_read": Media.Status.PLANNING.value,
        "on_hold": Media.Status.PAUSED.value,
        "dropped": Media.Status.DROPPED.value,
    }
    return status_mapping[status]
