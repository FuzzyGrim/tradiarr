from datetime import datetime
from zoneinfo import ZoneInfo

from app.models import MEDIA_TYPES, READABLE_MEDIA_TYPES, Item
from app.providers import services, tmdb
from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q

from events.models import Event


@shared_task(name="Reload calendar")
def reload_calendar(user=None):  # noqa:ARG001, used for metadata
    """Refresh the calendar with latest dates."""
    statuses = ["Planning", "In progress"]
    media_types_with_status = [media for media in MEDIA_TYPES if media != "episode"]

    query = Q()
    for media_type in media_types_with_status:
        query |= Q(**{f"{media_type}__status__in": statuses})

    items_with_status = Item.objects.filter(query).distinct()

    future_events = Event.objects.filter(date__gte=datetime.now(tz=settings.TZ))
    future_event_item_ids = set(future_events.values_list("item_id", flat=True))
    items_without_events = items_with_status.exclude(
        id__in=Event.objects.values_list("item_id", flat=True),
    )

    # Combine items with future events and items without any events
    items_to_process = items_with_status.filter(
        Q(id__in=future_event_item_ids) | Q(id__in=items_without_events),
    )

    event_list = []

    with transaction.atomic():
        # Delete all events related to items with at least one future event
        Event.objects.filter(item_id__in=future_event_item_ids).delete()

        result_msg = ""
        count = 0
        for item in items_to_process:
            reloaded = process_item(item, event_list)
            if reloaded:
                result_msg += f"{item} ({READABLE_MEDIA_TYPES[item.media_type]}).\n"
                count += 1

        Event.objects.bulk_create(event_list)

    return f"Reloaded {count} items with future events: \n\n {result_msg}"


def process_item(item, event_list):
    """Process each item and add events to the event list."""
    if item.media_type == "anime":
        reloaded = process_anime(item, event_list)
    elif item.media_type == "season":
        metadata = tmdb.season(item.media_id, item.season_number)
        reloaded = process_season(item, metadata, event_list)
    else:
        metadata = services.get_media_metadata(item.media_type, item.media_id)
        reloaded = process_other(item, metadata, event_list)
    return reloaded


def process_anime(item, event_list):
    """Process anime item and add events to the event list."""
    episodes = get_anime_schedule(item)

    for episode in episodes:
        air_date = datetime.fromtimestamp(episode["airingAt"], tz=ZoneInfo("UTC"))
        local_air_date = air_date.astimezone(settings.TZ)
        event_list.append(
            Event(
                item=item,
                episode_number=episode["episode"],
                date=local_air_date,
            ),
        )
    return bool(episodes)


def get_anime_schedule(item):
    """Get the airing schedule for the anime item from AniList API."""
    data = cache.get(f"schedule_anime_{item.media_id}")

    if data is None:
        query = """
        query ($idMal: Int){
            Media (idMal: $idMal, type: ANIME) {
                airingSchedule {
                    nodes {
                        episode
                        airingAt
                    }
                }
            }
        }
        """
        variables = {"idMal": item.media_id}
        url = "https://graphql.anilist.co"

        response = services.api_request(
            "ANILIST",
            "POST",
            url,
            params={"query": query, "variables": variables},
        )

        data = response["data"]["Media"]["airingSchedule"]["nodes"]
        cache.set(f"schedule_anime_{item.media_id}", data)

    return data


def process_season(item, metadata, event_list):
    """Process season item and add events to the event list."""
    for episode in reversed(metadata["episodes"]):
        if episode["air_date"]:
            try:
                air_date = date_parser(episode["air_date"])
                event_list.append(
                    Event(
                        item=item,
                        episode_number=episode["episode_number"],
                        date=air_date,
                    ),
                )
            except ValueError:
                pass
    return bool(metadata["episodes"])


def process_other(item, metadata, event_list):
    """Process other types of items and add events to the event list."""
    # it will have either of these keys
    date_keys = ["start_date", "release_date", "first_air_date"]
    for date_key in date_keys:
        if date_key in metadata["details"] and metadata["details"][date_key]:
            try:
                air_date = date_parser(metadata["details"][date_key])
                event_list.append(Event(item=item, date=air_date))
            except ValueError:
                return False
            else:
                return True

    return False


def date_parser(date_str):
    """Parse date string to datetime object. Raises ValueError if invalid."""
    year_only_parts = 1
    year_month_parts = 2
    default_month_day = "-01-01"
    default_day = "-01"
    # Preprocess the date string
    parts = date_str.split("-")
    if len(parts) == year_only_parts:
        date_str += default_month_day
    elif len(parts) == year_month_parts:
        # Year and month are provided, append "-01"
        date_str += default_day

    # Parse the date string
    return datetime.strptime(date_str, "%Y-%m-%d").replace(
        tzinfo=ZoneInfo("UTC"),
    )