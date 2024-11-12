import logging
from datetime import datetime

from django.conf import settings
from django.core.cache import cache

import app

logger = logging.getLogger(__name__)


def process_payload(payload, user):
    """Process a Jellyfin webhook payload."""
    event_type = payload["Event"]

    if event_type not in ("Stop", "MarkPlayed", "MarkUnplayed"):
        logger.info("Ignoring Jellyfin webhook event: %s", event_type)
        return

    if payload["Item"]["Type"] == "Episode":
        media_type = "tv"
        tmdb_id = payload["Series"]["ProviderIds"].get("Tmdb")
    elif payload["Item"]["Type"] == "Movie":
        media_type = "movie"
        tmdb_id = payload["Item"]["ProviderIds"].get("Tmdb")
    else:
        logger.info("Ignoring Jellyfin webhook event: %s", media_type)
        return

    if tmdb_id is None:
        logger.info(
            "Ignoring Jellyfin webhook call because no TMDB ID was found.",
        )
        return

    tmdb_id = int(tmdb_id)
    mapping_data = fetch_mapping_data()

    if media_type == "tv":
        season_number = payload["Item"]["ParentIndexNumber"]
        episode_number = payload["Item"]["IndexNumber"]
        tvdb_id = payload["Series"]["ProviderIds"].get("Tvdb")
        title = payload["Series"]["Name"]

        if tvdb_id:
            tvdb_id = int(tvdb_id)
            mal_id, episode_offset = get_mal_id_from_tvdb(
                mapping_data,
                tvdb_id,
                season_number,
                episode_number,
            )
            if mal_id:
                logger.info("Detected anime: %s", title)
                add_anime(mal_id, episode_offset, payload, user)
                return

        logger.info("Detected TV show: %s", title)
        add_tv(tmdb_id, payload, user)

    elif media_type == "movie":
        title = payload["Item"]["Name"]
        mal_id = get_mal_id_from_tmdb_movie(mapping_data, tmdb_id)
        if mal_id:
            logger.info("Detected anime movie: %s", title)
            add_anime(mal_id, 1, payload, user)
        else:
            logger.info("Detected movie: %s", title)
            add_movie(tmdb_id, payload, user)


def add_anime(media_id, episode_number, payload, user):
    """Add an anime episode as watched."""
    anime_metadata = app.providers.mal.anime(media_id)
    episode_played = payload["Item"]["UserData"]["Played"]

    anime_item, _ = app.models.Item.objects.get_or_create(
        media_id=media_id,
        source="mal",
        media_type="anime",
        defaults={
            "title": anime_metadata["title"],
            "image": anime_metadata["image"],
        },
    )

    # set last episode as watched if current episode is not finished
    if not episode_played:
        episode_number = episode_number - 1

    try:
        anime_instance = app.models.Anime.objects.get(
            item=anime_item,
            user=user,
        )
        anime_instance.progress = episode_number

        if (
            anime_instance.status == app.models.STATUS_COMPLETED and episode_played
        ) or anime_instance.status == app.models.STATUS_REPEATING:
            anime_instance.status = app.models.STATUS_REPEATING
        else:
            anime_instance.status = app.models.STATUS_IN_PROGRESS
        anime_instance.save()
    except app.models.Anime.DoesNotExist:
        app.models.Anime.objects.create(
            item=anime_item,
            user=user,
            progress=episode_number,
            status=app.models.STATUS_IN_PROGRESS,
        )


def add_movie(media_id, payload, user):
    """Add a movie as watched."""
    movie_metadata = app.providers.tmdb.movie(media_id)
    movie_played = payload["Item"]["UserData"]["Played"]
    progress = 1 if movie_played else 0

    item, _ = app.models.Item.objects.get_or_create(
        media_id=media_id,
        source="tmdb",
        media_type="movie",
        defaults={
            "title": movie_metadata["title"],
            "image": movie_metadata["image"],
        },
    )

    try:
        movie_instance = app.models.Movie.objects.get(
            item=item,
            user=user,
        )
        movie_instance.progress = progress

        if (
            movie_instance.status == app.models.STATUS_COMPLETED and movie_played
        ) or movie_instance.status == app.models.STATUS_REPEATING:
            if movie_played:
                movie_instance.repeats += 1
            else:
                movie_instance.status = app.models.STATUS_REPEATING
            movie_instance.status = app.models.STATUS_REPEATING
        else:
            movie_instance.status = app.models.STATUS_IN_PROGRESS
        movie_instance.save()

    except app.models.Movie.DoesNotExist:
        app.models.Movie.objects.create(
            item=item,
            user=user,
            progress=progress,
            status=app.models.STATUS_IN_PROGRESS,
        )


def add_tv(media_id, payload, user):
    """Add a TV show episode as watched."""
    season_number = payload["Item"]["ParentIndexNumber"]
    episode_number = payload["Item"]["IndexNumber"]

    tv_metadata = app.providers.tmdb.tv_with_seasons(
        media_id,
        [payload["Item"]["ParentIndexNumber"]],
    )
    season_metadata = tv_metadata[f"season/{season_number}"]

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
        season_number=season_number,
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
        season_number=season_number,
        episode_number=episode_number,
        defaults={
            "title": tv_metadata["title"],
            "image": season_metadata["image"],
        },
    )

    if payload["Item"]["UserData"]["Played"]:
        app.models.Episode.objects.get_or_create(
            item=episode_item,
            related_season=season_instance,
            defaults={
                "watch_date": datetime.now(tz=settings.TZ),
            },
        )
    else:
        app.models.Episode.objects.filter(
            item=episode_item,
            related_season=season_instance,
        ).delete()


def fetch_mapping_data():
    """Fetch the anime mapping data from GitHub."""
    data = cache.get("jellyfin_anime_mapping")

    if data is None:
        url = "https://raw.githubusercontent.com/Kometa-Team/Anime-IDs/refs/heads/master/anime_ids.json"
        data = app.providers.services.api_request("GITHUB", "GET", url)
        cache.set("jellyfin_anime_mapping", data)

    return data


def get_mal_id_from_tvdb(mapping_data, tvdb_id, season_number, episode_number):
    """Find the appropriate MAL ID based on TVDB id."""
    matching_entries = [
        entry
        for entry in mapping_data.values()
        if entry.get("tvdb_id") == tvdb_id
        and entry.get("tvdb_season") == season_number
        and "mal_id" in entry
    ]

    if not matching_entries:
        return None, None

    # Sort entries by epoffset
    matching_entries.sort(key=lambda x: x.get("tvdb_epoffset", 0))

    # Find the appropriate entry based on episode number
    for i, entry in enumerate(matching_entries):
        current_offset = entry.get("tvdb_epoffset", 0)
        next_offset = float("inf")

        if i < len(matching_entries) - 1:
            next_offset = matching_entries[i + 1].get("tvdb_epoffset", float("inf"))

        if episode_number > current_offset and (
            episode_number <= next_offset or next_offset == float("inf")
        ):
            return entry["mal_id"], episode_number - current_offset

    return None, None


def get_mal_id_from_tmdb_movie(mapping_data, tmdb_movie_id):
    """Find the MAL ID for a given TMDB movie ID."""
    for entry in mapping_data.values():
        if entry.get("tmdb_movie_id") == tmdb_movie_id and "mal_id" in entry:
            return entry["mal_id"]
    return None
