from datetime import timedelta
from itertools import chain

from django.apps import apps
from django.db.models import Count, F
from django.db.models.functions import TruncDate
from django.utils import timezone

from app.models import Item, Media


def get_media_list(user, media_type, status_filter, sort_filter):
    """Get media list based on filters and sorting."""
    model = apps.get_model(app_label="app", model_name=media_type)
    queryset = model.objects.filter(user=user.id)

    if "All" not in status_filter:
        queryset = queryset.filter(status__in=status_filter)

    # Apply prefetch related based on media type
    prefetch_map = {
        "tv": ["seasons", "seasons__episodes"],
        "season": ["episodes", "episodes__item"],
        "default": [None],
    }
    prefetch_related_fields = prefetch_map.get(media_type, prefetch_map["default"])
    queryset = queryset.prefetch_related(*prefetch_related_fields).select_related(
        "item",
    )

    sort_is_property = sort_filter in get_properties(model)
    sort_is_item_field = sort_filter in get_fields(Item)
    if media_type in ("tv", "season") and sort_is_property:
        return sorted(queryset, key=lambda x: getattr(x, sort_filter), reverse=True)

    if sort_is_item_field:
        sort_field = f"item__{sort_filter}"
        return queryset.order_by(
            F(sort_field).asc() if sort_filter == "title" else F(sort_field).desc(),
        )
    return queryset.order_by(F(sort_filter).desc(nulls_last=True))


def get_fields(model):
    """Get fields of a model."""
    return [f.name for f in model._meta.fields]  # noqa: SLF001


def get_properties(model):
    """Get properties of a model."""
    return [name for name in dir(model) if isinstance(getattr(model, name), property)]


def get_historical_models():
    """Return list of historical model names."""
    media_types = Item.MediaTypes.values
    return [f"historical{media_type}" for media_type in media_types]


def get_in_progress(user):
    """Get a media list of in progress media by type."""
    list_by_type = {}

    for media_type in Item.MediaTypes.values:
        # dont show tv and episodes in home page
        if media_type not in ("tv", "episode"):
            media_list = get_media_list(
                user=user,
                media_type=media_type,
                status_filter=[
                    Media.Status.IN_PROGRESS.value,
                    Media.Status.REPEATING.value,
                ],
                sort_filter="score",
            )
            if media_list:
                list_by_type[media_type] = media_list

    return list_by_type


def get_media(media_type, item, user):
    """Get user media object given the media type and item."""
    model = apps.get_model(app_label="app", model_name=media_type)
    params = {"item": item}

    if media_type == "episode":
        params["related_season__user"] = user
    else:
        params["user"] = user

    try:
        return model.objects.get(**params)
    except model.DoesNotExist:
        return None


def get_filtered_historical_data(start_date, end_date, user_id):
    """Get historical data filtered by date range."""
    historical_models = get_historical_models()
    combined_data = []

    for model_name in historical_models:
        historical_model = apps.get_model("app", model_name)
        main_model_name = model_name.replace("historical", "")
        main_model = apps.get_model("app", main_model_name)

        # Get IDs of instances belonging to the user
        if main_model_name == "episode":
            instance_ids = main_model.objects.filter(
                related_season__user=user_id,
            ).values_list(
                "id",
                flat=True,
            )
        else:
            instance_ids = main_model.objects.filter(user=user_id).values_list(
                "id",
                flat=True,
            )

        # Filter historical records
        data = (
            historical_model.objects.filter(
                id__in=instance_ids,  # This is the key part
                history_date__date__gte=start_date,
                history_date__date__lte=end_date,
            )
            .annotate(date=TruncDate("history_date"))
            .values("date")
            .annotate(count=Count("id"))
        )
        combined_data = chain(combined_data, data)

    return combined_data


def get_activity_data(user_id):
    """Get daily activity counts for the last year."""
    end_date = timezone.now().date()
    start_date = end_date - timedelta(days=365)

    # First align to Monday
    start_date = start_date - timedelta(days=start_date.weekday())

    # Check if it's too close to the end of the month
    next_month = (start_date.replace(day=1) + timedelta(days=32)).replace(day=1)
    days_until_next_month = (next_month - start_date).days

    # If less than 2 weeks until next month, move back to previous Monday
    # it's so there is enough space for month labels
    two_weeks = 14
    if days_until_next_month < two_weeks:
        start_date = start_date - timedelta(days=7)

    combined_data = get_filtered_historical_data(start_date, end_date, user_id)

    # Aggregate counts by date
    date_counts = {}
    for item in combined_data:
        date = item["date"]
        if date in date_counts:
            date_counts[date] += item["count"]
        else:
            date_counts[date] = item["count"]

    # Create complete date range including padding days
    activity_data = []
    current_date = start_date

    while current_date <= end_date:
        count = date_counts.get(current_date, 0)
        activity_data.append(
            {
                "date": current_date.strftime("%Y-%m-%d"),
                "count": count,
                "level": get_level(count),
            },
        )
        current_date += timedelta(days=1)

    # Format data into calendar weeks
    calendar_weeks = [activity_data[i : i + 7] for i in range(0, len(activity_data), 7)]

    # Generate months list with their Monday counts
    months = []
    mondays_per_month = []
    current_date = start_date

    while current_date <= end_date:
        month = current_date.strftime("%b")
        # Calculate number of Mondays for this month
        month_start = current_date.replace(day=1)
        if current_date == start_date:
            month_start = current_date

        next_month = (current_date.replace(day=1) + timedelta(days=32)).replace(day=1)
        if next_month > end_date:
            month_end = end_date
        else:
            month_end = next_month - timedelta(days=1)

        # Count Mondays in this month range
        monday_count = 0
        check_date = month_start
        while check_date <= month_end:
            if check_date.weekday() == 0:  # Monday is 0
                monday_count += 1
            check_date += timedelta(days=1)

        months.append(month)
        mondays_per_month.append(monday_count)

        current_date = next_month

    return calendar_weeks, list(zip(months, mondays_per_month, strict=False))


def get_level(count):
    """Calculate intensity level (0-4) based on count."""
    thresholds = [0, 3, 6, 9]
    for i, threshold in enumerate(thresholds):
        if count <= threshold:
            return i
    return 4
