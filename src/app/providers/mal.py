import requests
from django.conf import settings

from app.providers import services


def search(media_type: str, query: str) -> list:
    """Search for media on MyAnimeList."""

    url = f"https://api.myanimelist.net/v2/{media_type}?q={query}&nsfw=true&fields=media_type"

    try:
        response = services.api_request(
            url,
            "GET",
            headers={"X-MAL-CLIENT-ID": settings.MAL_API},
        )
    except requests.exceptions.HTTPError as error:
        # if the query is invalid, return an empty list
        if error.response.json().get("message") == "invalid q":
            return []

    response = response["data"]
    return [
        {
            "media_id": media["node"]["id"],
            "media_type": media_type,
            "original_type": get_original_type(media["node"]),
            "title": media["node"]["title"],
            "image": get_image_url(media["node"]),
        }
        for media in response
    ]


def anime(media_id: str) -> dict:
    """Return the metadata for the selected anime or manga from MyAnimeList."""

    url = f"https://api.myanimelist.net/v2/anime/{media_id}?fields=title,main_picture,media_type,start_date,end_date,synopsis,status,genres,num_episodes,average_episode_duration,related_anime,related_manga,recommendations"
    response = services.api_request(
        url,
        "GET",
        headers={"X-MAL-CLIENT-ID": settings.MAL_API},
    )

    return {
        "media_id": media_id,
        "media_type": "anime",
        "title": response["title"],
        "image": get_image_url(response),
        "details": {
            "original_type": get_original_type(response),
            "start_date": response.get("start_date", "Unknown"),
            "end_date": response.get("end_date", "Unknown"),
            "status": get_readable_status(response),
            "synopsis": get_synopsis(response),
            "number_of_episodes": response.get("num_episodes", "Unknown"),
            "runtime": get_runtime(response),
            "genres": get_genres(response),
        },
        "related": {
            "related_animes": get_related(response.get("related_anime")),
            "recommendations": get_related(response.get("recommendations")),
        },
    }


def manga(media_id: str) -> dict:
    """Return the metadata for the selected anime or manga from MyAnimeList."""

    url = f"https://api.myanimelist.net/v2/manga/{media_id}?fields=title,main_picture,media_type,start_date,end_date,synopsis,status,genres,num_chapters,average_episode_duration,related_anime,related_manga,recommendations"
    response = services.api_request(
        url,
        "GET",
        headers={"X-MAL-CLIENT-ID": settings.MAL_API},
    )

    return {
        "media_id": media_id,
        "media_type": "manga",
        "title": response["title"],
        "image": get_image_url(response),
        "details": {
            "original_type": get_original_type(response),
            "start_date": response.get("start_date", "Unknown"),
            "end_date": response.get("end_date", "Unknown"),
            "status": get_readable_status(response),
            "synopsis": get_synopsis(response),
            "number_of_episodes": response.get("num_chapters", "Unknown"),
            "runtime": get_runtime(response),
            "genres": get_genres(response),
        },
        "related": {
            "related_mangas": get_related(response.get("related_manga")),
            "recommendations": get_related(response.get("recommendations")),
        },
    }


def get_original_type(response: dict) -> dict:
    """Return the original type of the media."""

    # MAL return tv in metadata for anime
    if response["media_type"] == "tv":
        response["media_type"] = "anime"

    # for light_novel, tv_special, etc
    original_type = response["media_type"].replace("_", " ")
    if len(original_type) < 3:
        # ona, ova, etc
        return original_type.capitalize()
    return original_type.title()


def get_image_url(response: dict) -> dict:
    """Return the image URL for the media."""

    if "main_picture" in response:
        return response["main_picture"]["large"]
    return settings.IMG_NONE


def get_readable_status(response: dict) -> dict:
    """Return the status in human-readable format."""

    # Map status to human-readable values
    status_map = {
        "finished_airing": "Finished",
        "currently_airing": "Airing",
        "not_yet_aired": "Upcoming",
        "finished": "Finished",
        "currently_publishing": "Publishing",
        "not_yet_published": "Upcoming",
        "on_hiatus": "On Hiatus",
    }
    return status_map.get(response.get("status"), "Unknown")


def get_synopsis(response: dict) -> dict:
    """Add the synopsis to the response."""

    if response["synopsis"] == "":
        return "No synopsis available."

    return response["synopsis"]


def get_runtime(response: dict) -> dict:
    """Return the average episode duration."""

    # Convert average_episode_duration to hours and minutes
    if (
        "average_episode_duration" in response
        and response["average_episode_duration"] != 0
    ):
        duration = response["average_episode_duration"]
        # duration are in seconds
        hours, minutes = divmod(int(duration / 60), 60)
        return f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"
    return "Unknown"


def get_genres(response: dict) -> dict:
    """Return the genres for the media."""

    if "genres" in response:
        return ", ".join(genre["name"] for genre in response["genres"])

    return "Unknown"


def get_related(related_medias: list) -> dict:
    """Return list of related media for the selected media."""

    return [
        {
            "media_id": media["node"]["id"],
            "title": media["node"]["title"],
            "image": get_image_url(media["node"]),
        }
        for media in related_medias
    ]