import datetime
import logging

import requests
from django.conf import settings

import app
from app.models import Media

logger = logging.getLogger(__name__)

SIMKL_API_BASE_URL = "https://api.simkl.com"


def get_token(request):
    """View for getting the SIMKL OAuth2 token."""
    domain = request.get_host()
    scheme = request.scheme
    code = request.GET["code"]
    url = f"{SIMKL_API_BASE_URL}/oauth/token"

    headers = {
        "Content-Type": "application/json",
    }

    params = {
        "client_id": settings.SIMKL_ID,
        "client_secret": settings.SIMKL_SECRET,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": f"{scheme}://{domain}",
    }

    try:
        request = app.providers.services.api_request(
            "SIMKL",
            "POST",
            url,
            headers=headers,
            params=params,
        )
    except requests.exceptions.HTTPError as error:
        if error.response.status_code == requests.codes.unauthorized:
            msg = "Invalid SIMKL secret key."
            raise ValueError(msg) from error
        raise

    return request["access_token"]


def importer(token, user):
    """Import tv shows, movies and anime from SIMKL."""
    data = get_user_list(token)

    # data None when empty profile
    if data:
        tv_count, tv_warnings = process_tv_list(data["shows"], user)
        movie_count, movie_warnings = process_movie_list(data["movies"], user)
        anime_count, anime_warnings = process_anime_list(data["anime"], user)

        warning_messages = tv_warnings + movie_warnings + anime_warnings
    else:
        tv_count, movie_count, anime_count = 0, 0, 0
        warning_messages = []

    return tv_count, movie_count, anime_count, "\n".join(warning_messages)


def get_user_list(token):
    """Get the user's list from SIMKL."""
    url = f"{SIMKL_API_BASE_URL}/sync/all-items/"
    headers = {
        "Authorization": f"Bearer: {token}",
        "simkl-api-key": settings.SIMKL_ID,
    }
    params = {
        "extended": "full",
        "episode_watched_at": "yes",
    }

    return app.providers.services.api_request(
        "SIMKL",
        "GET",
        url,
        headers=headers,
        params=params,
    )


def process_tv_list(tv_list, user):
    """Process TV list from SIMKL and add to database."""
    logger.info("Processing tv shows")
    warnings = []
    tv_count = 0

    for tv in tv_list:
        title = tv["show"]["title"]
        msg = f"Processing {title}"
        logger.debug(msg)
        tmdb_id = tv["show"]["ids"]["tmdb"]
        tv_status = get_status(tv["status"])

        try:
            season_numbers = [season["number"] for season in tv["seasons"]]
        except KeyError:
            warnings.append(
                f"{title}: It doesn't have data on episodes viewed.",
            )
            continue

        try:
            metadata = app.providers.tmdb.tv_with_seasons(tmdb_id, season_numbers)
        except requests.exceptions.HTTPError as error:
            if error.response.status_code == requests.codes.not_found:
                warnings.append(
                    f"{title}: Couldn't fetch metadata from TMDB ({tmdb_id})",
                )
                continue
            raise

        tv_item, _ = app.models.Item.objects.get_or_create(
            media_id=tmdb_id,
            source="tmdb",
            media_type="tv",
            defaults={
                "title": metadata["title"],
                "image": metadata["image"],
            },
        )

        tv_obj, tv_created = app.models.TV.objects.get_or_create(
            item=tv_item,
            user=user,
            defaults={
                "status": tv_status,
                "score": tv["user_rating"],
            },
        )

        if tv_created:
            tv_count += 1

        for season in tv["seasons"]:
            season_number = season["number"]
            episodes = season["episodes"]
            season_metadata = metadata[f"season/{season_number}"]

            season_item, _ = app.models.Item.objects.get_or_create(
                media_id=tmdb_id,
                source="tmdb",
                media_type="season",
                season_number=season_number,
                defaults={
                    "title": metadata["title"],
                    "image": season_metadata["image"],
                },
            )

            if season_number == season_numbers[-1]:  # if last iteration
                season_status = tv_status
            else:
                season_status = Media.Status.COMPLETED.value

            season_obj, _ = app.models.Season.objects.get_or_create(
                item=season_item,
                user=user,
                related_tv=tv_obj,
                defaults={
                    "status": season_status,
                },
            )

            for episode in episodes:
                ep_img = get_episode_image(episode, season_number, metadata)
                episode_item, _ = app.models.Item.objects.get_or_create(
                    media_id=tmdb_id,
                    source="tmdb",
                    media_type="episode",
                    season_number=season_number,
                    episode_number=episode["number"],
                    defaults={
                        "title": metadata["title"],
                        "image": ep_img,
                    },
                )

                app.models.Episode.objects.get_or_create(
                    item=episode_item,
                    related_season=season_obj,
                    defaults={
                        "end_date": get_date(episode["watched_at"]),
                    },
                )
    logger.info("Finished processing tv shows")
    return tv_count, warnings


def get_episode_image(episode, season_number, metadata):
    """Get the image for the episode."""
    for episode_metadata in metadata[f"season/{season_number}"]["episodes"]:
        if episode_metadata["episode_number"] == episode["number"]:
            return f"https://image.tmdb.org/t/p/w500{episode_metadata['still_path']}"
    return settings.IMG_NONE


def process_movie_list(movie_list, user):
    """Process movie list from SIMKL and add to database."""
    logger.info("Processing movies")
    warnings = []
    movie_count = 0

    for movie in movie_list:
        title = movie["movie"]["title"]

        msg = f"Processing {title}"
        logger.debug(msg)

        tmdb_id = movie["movie"]["ids"]["tmdb"]
        movie_status = get_status(movie["status"])

        try:
            metadata = app.providers.tmdb.movie(tmdb_id)
        except requests.exceptions.HTTPError as error:
            if error.response.status_code == requests.codes.not_found:
                warnings.append(
                    f"{title}: Couldn't fetch metadata from TMDB ({tmdb_id})",
                )
                continue
            raise

        movie_item, _ = app.models.Item.objects.get_or_create(
            media_id=tmdb_id,
            source="tmdb",
            media_type="movie",
            defaults={
                "title": metadata["title"],
                "image": metadata["image"],
            },
        )

        _, movie_created = app.models.Movie.objects.get_or_create(
            item=movie_item,
            user=user,
            defaults={
                "status": movie_status,
                "score": movie["user_rating"],
                "start_date": get_date(movie["last_watched_at"]),
                "end_date": get_date(movie["last_watched_at"]),
            },
        )

        if movie_created:
            movie_count += 1

    logger.info("Finished processing movies")

    return movie_count, warnings


def process_anime_list(anime_list, user):
    """Process anime list from SIMKL and add to database."""
    logger.info("Processing anime")
    warnings = []
    anime_count = 0

    for anime in anime_list:
        title = anime["show"]["title"]
        msg = f"Processing {title}"
        logger.debug(msg)

        mal_id = anime["show"]["ids"]["mal"]
        anime_status = get_status(anime["status"])

        try:
            metadata = app.providers.mal.anime(mal_id)
        except requests.exceptions.HTTPError as error:
            if error.response.status_code == requests.codes.not_found:
                warnings.append(
                    f"{title}: Couldn't fetch metadata from TMDB ({mal_id})",
                )
                continue
            raise

        anime_item, _ = app.models.Item.objects.get_or_create(
            media_id=mal_id,
            source="mal",
            media_type="anime",
            defaults={
                "title": metadata["title"],
                "image": metadata["image"],
            },
        )

        _, anime_created = app.models.Anime.objects.get_or_create(
            item=anime_item,
            user=user,
            defaults={
                "status": anime_status,
                "score": anime["user_rating"],
                "progress": anime["watched_episodes_count"],
                "start_date": get_date(anime["last_watched_at"]),
                "end_date": get_date(anime["last_watched_at"])
                if anime_status == Media.Status.COMPLETED.value
                else None,
            },
        )

        if anime_created:
            anime_count += 1

    logger.info("Finished processing anime")
    return anime_count, warnings


def get_status(status):
    """Map SIMKL status to internal status."""
    status_mapping = {
        "completed": Media.Status.COMPLETED.value,
        "watching": Media.Status.IN_PROGRESS.value,
        "plantowatch": Media.Status.PLANNING.value,
        "hold": Media.Status.PAUSED.value,
        "dropped": Media.Status.DROPPED.value,
    }

    return status_mapping.get(status, Media.Status.IN_PROGRESS.value)


def get_date(date):
    """Convert the date from Trakt to a date object."""
    if date:
        return (
            datetime.datetime.strptime(date, "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=datetime.UTC)
            .astimezone(settings.TZ)
            .date()
        )
    return None
