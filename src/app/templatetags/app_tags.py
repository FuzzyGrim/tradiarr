from decimal import Decimal

from django import template
from unidecode import unidecode

from app import helpers, models

register = template.Library()


@register.filter
def addslashes_double(arg1):
    """Add slashes before double quotes."""
    return arg1.replace('"', '\\"')


@register.filter()
def no_underscore(arg1):
    """Return the title case of the string."""
    return arg1.replace("_", " ")


@register.filter()
def slug(arg1):
    """Return the slug of the string.

    Sometimes slugify removes all characters from a string, so we need to
    urlencode the special characters first.
    e.g Anime: 31687
    """
    cleaned = template.defaultfilters.slugify(unidecode(arg1))
    if cleaned == "":
        return template.defaultfilters.slugify(
            template.defaultfilters.urlencode(unidecode(arg1)),
        )
    return cleaned


@register.filter()
def format_time(total_minutes):
    """Convert total minutes to HH:MM format."""
    return helpers.minutes_to_hhmm(total_minutes)


@register.filter()
def is_list(arg1):
    """Return True if the object is a list."""
    return isinstance(arg1, list)


@register.filter()
def icon(media_type):
    """Return the icon of the item for the calendar."""
    icons = {
        "anime": "bi bi-collection-play",
        "manga": "bi bi-book",
        "game": "bi bi-joystick",
        "tv": "bi bi-tv",
        "season": "bi bi-grid",
        "episode": "bi bi-tv",
        "movie": "bi bi-film",
        "book": "bi bi-journal",
    }
    return icons[media_type]


@register.filter()
def media_type_readable(media_type):
    """Return the readable media type."""
    return models.Item.MediaTypes(media_type).label


@register.filter
def media_color(media_type):
    """Return the color associated with the media type."""
    return models.Item.Colors[media_type.upper()].value


@register.filter
def percentage_ratio(value, total):
    """Calculate percentage, showing one decimal place for values between 0 and 1."""
    try:
        if total == 0:
            return "0"

        result = (Decimal(value) / Decimal(total)) * 100

        # If result is between 0 and 1, show one decimal
        if 0 < result < 1:
            return f"{result:.1f}"

        # For all other values, show as integer
        return str(int(round(result)))
    except (TypeError, ValueError):
        return "0"
