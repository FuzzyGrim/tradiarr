from collections import defaultdict
from datetime import timedelta

from django.apps import apps
from django.db.models import Count, F
from django.db.models.functions import TruncDate

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


def get_filtered_historical_data(start_date, end_date, user):
    """Get historical data filtered by date range."""
    historical_models = get_historical_models()
    combined_data = []

    for model_name in historical_models:
        historical_model = apps.get_model("app", model_name)

        # Filter historical records
        data = (
            historical_model.objects.filter(
                history_user_id=user,
                history_date__date__gte=start_date,
                history_date__date__lte=end_date,
            )
            .annotate(date=TruncDate("history_date"))
            .values("date")
            .annotate(count=Count("id"))
        )

        combined_data.extend(data)

    return combined_data


def calculate_day_of_week_stats(date_counts, start_date):
    """Calculate the most active day of the week based on activity frequency.

    Returns the day name and its percentage of total activity.
    """
    # Initialize counters for each day of the week
    day_counts = defaultdict(int)
    total_active_days = 0

    # Count occurrences of each day of the week where activity happened
    for date in date_counts:
        if date < start_date:
            continue
        if date_counts[date] > 0:
            day_name = date.strftime("%A")  # Get full day name
            day_counts[day_name] += 1
            total_active_days += 1

    if not total_active_days:
        return None, 0

    # Find the most active day
    most_active_day = max(day_counts.items(), key=lambda x: x[1])
    percentage = (most_active_day[1] / total_active_days) * 100

    return most_active_day[0], round(percentage)


def calculate_streaks(date_counts, start_date, end_date):
    """Calculate current and longest activity streaks.

    Returns tuple of (current_streak, longest_streak).
    """
    if not date_counts:
        return 0, 0

    current_streak = 0
    longest_streak = 0
    temp_streak = 0

    # Convert date_counts to sorted list of dates
    active_dates = sorted(date for date in date_counts if date >= start_date)

    # Calculate streaks
    for i in range(len(active_dates)):
        if i == 0:
            temp_streak = 1
            continue

        if (active_dates[i] - active_dates[i - 1]).days == 1:
            temp_streak += 1
        else:
            longest_streak = max(longest_streak, temp_streak)
            temp_streak = 1

    # Update longest streak one last time
    longest_streak = max(longest_streak, temp_streak)

    # Calculate current streak
    if active_dates:
        current_date = end_date
        current_streak = 0

        while current_date in date_counts and current_date >= start_date:
            current_streak += 1
            current_date -= timedelta(days=1)

    return current_streak, longest_streak


def get_activity_data(user, start_date, end_date):
    """Get daily activity counts for the last year."""
    # Get the Monday of the week containing start_date (for grid alignment)
    start_date_aligned = start_date - timedelta(days=start_date.weekday())

    combined_data = get_filtered_historical_data(start_date_aligned, end_date, user)

    # Aggregate counts by date
    date_counts = {}
    for item in combined_data:
        date = item["date"]
        date_counts[date] = date_counts.get(date, 0) + item["count"]

    date_range = [
        start_date_aligned + timedelta(days=x)
        for x in range((end_date - start_date_aligned).days + 1)
    ]

    # Calculate activity statistics
    most_active_day, day_percentage = calculate_day_of_week_stats(
        date_counts,
        start_date,
    )
    current_streak, longest_streak = calculate_streaks(
        date_counts,
        start_date,
        end_date,
    )

    # Create complete date range including padding days
    activity_data = [
        {
            "date": current_date.strftime("%Y-%m-%d"),
            "count": date_counts.get(current_date, 0),
            "level": get_level(date_counts.get(current_date, 0)),
            "disabled": current_date < start_date,
        }
        for current_date in date_range
    ]

    # Format data into calendar weeks
    calendar_weeks = [activity_data[i : i + 7] for i in range(0, len(activity_data), 7)]

    # Generate months list with their Monday counts
    months = []
    mondays_per_month = []
    current_month = date_range[0].strftime("%b")
    monday_count = 0

    for current_date in date_range:
        if current_date.weekday() == 0:  # Monday
            month = current_date.strftime("%b")

            if current_month != month:
                if current_month is not None:
                    if monday_count > 1:
                        months.append(current_month)
                        mondays_per_month.append(monday_count)
                    else:
                        months.append("")
                        mondays_per_month.append(monday_count)
                current_month = month
                monday_count = 0

            monday_count += 1
    # For the last month
    if monday_count > 1:
        months.append(current_month)
        mondays_per_month.append(monday_count)

    return {
        "weekdays": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "calendar_weeks": calendar_weeks,
        "months": list(zip(months, mondays_per_month, strict=False)),
        "stats": {
            "most_active_day": most_active_day,
            "most_active_day_percentage": day_percentage,
            "current_streak": current_streak,
            "compared_to_longest_streak": longest_streak - current_streak,
        },
    }


def get_level(count):
    """Calculate intensity level (0-4) based on count."""
    thresholds = [0, 3, 6, 9]
    for i, threshold in enumerate(thresholds):
        if count <= threshold:
            return i
    return 4
