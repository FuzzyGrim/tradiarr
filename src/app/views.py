import logging

from django.apps import apps
from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import (
    require_GET,
    require_http_methods,
    require_POST,
)

from app import database, helpers
from app.forms import CustomListForm, FilterForm, get_form_class
from app.models import STATUS_IN_PROGRESS, CustomList, Episode, ListItem, Season
from app.providers import igdb, mal, services, tmdb

logger = logging.getLogger(__name__)


@require_GET
def home(request):
    """Home page with media items in progress and repeating."""
    list_by_type = database.get_media_list_by_type(request.user)
    context = {"list_by_type": list_by_type}
    return render(request, "app/home.html", context)


@require_POST
def progress_edit(request):
    """Increase or decrease the progress of a media item from home page."""
    media_type = request.POST["media_type"]
    media_id = request.POST["media_id"]
    operation = request.POST["operation"]
    season_number = request.POST.get("season_number")

    model = apps.get_model(app_label="app", model_name=media_type)
    search_params = database.get_search_params(
        media_type,
        media_id,
        season_number,
        None,
        request.user,
    )

    try:
        media = model.objects.get(**search_params)

        if operation == "increase":
            media.increase_progress()
        elif operation == "decrease":
            media.decrease_progress()

        response = media.progress_response()

        return render(
            request,
            "app/components/progress_changer.html",
            {"media": response, "media_type": media_type},
        )
    except model.DoesNotExist:
        messages.error(
            request,
            "Media item was deleted before trying to change progress",
        )

        response = HttpResponse()
        response["HX-Redirect"] = reverse("home")
        return response


@require_GET
def media_list(request, media_type):
    """Return the media list page."""
    layout_user = request.user.get_layout(media_type)
    filter_form = FilterForm(layout=layout_user)

    if request.GET:
        layout_request = request.GET.get("layout", layout_user)
        filter_form = FilterForm(request.GET, layout=layout_request)
        if filter_form.is_valid() and layout_request != layout_user:
            request.user.set_layout(media_type, layout_request)

    status_filter = request.GET.get("status", "all")
    sort_filter = request.GET.get("sort", "score")

    media_list = database.get_media_list(
        user=request.user,
        media_type=media_type,
        status_filter=[status_filter.capitalize()],
        sort_filter=sort_filter,
    )

    return render(
        request,
        request.user.get_layout_template(media_type),
        {
            "media_type": media_type,
            "media_list": media_list,
            "filter_form": filter_form,
        },
    )


@require_GET
def media_search(request):
    """Return the media search page."""
    media_type = request.GET["media_type"]
    query = request.GET["q"]

    request.user.set_last_search_type(media_type)

    if media_type in ("anime", "manga"):
        query_list = mal.search(media_type, query)
    elif media_type in ("tv", "movie"):
        query_list = tmdb.search(media_type, query)
    elif media_type == "game":
        query_list = igdb.search(query)

    context = {"query_list": query_list}

    return render(request, "app/search.html", context)


@require_GET
def media_details(request, media_type, media_id, title):  # noqa: ARG001 title for URL
    """Return the details page for a media item."""
    media_metadata = services.get_media_metadata(media_type, media_id)

    context = {"media": media_metadata}
    return render(request, "app/media_details.html", context)


@require_GET
def season_details(request, media_id, title, season_number):  # noqa: ARG001 title for URL
    """Return the details page for a season."""
    tv_metadata = tmdb.tv_with_seasons(media_id, [season_number])
    season_metadata = tv_metadata[f"season/{season_number}"]

    episodes_in_db = Episode.objects.filter(
        related_season__media_id=media_id,
        related_season__season_number=season_number,
        related_season__user=request.user,
    ).values("episode_number", "watch_date", "repeats")

    season_metadata["episodes"] = tmdb.process_episodes(
        season_metadata,
        episodes_in_db,
    )

    context = {"season": season_metadata, "tv": tv_metadata}
    return render(request, "app/season_details.html", context)


@require_GET
def track(request):
    """Return the tracking form for a media item."""
    media_type = request.GET["media_type"]
    media_id = request.GET["media_id"]
    season_number = request.GET.get("season_number")

    model = apps.get_model(app_label="app", model_name=media_type)
    search_params = database.get_search_params(
        media_type,
        media_id,
        season_number,
        None,
        request.user,
    )

    try:
        media = model.objects.get(**search_params)
        media_exists = True
    except model.DoesNotExist:
        media = None
        media_exists = False

    initial_data = {
        "media_id": media_id,
        "media_type": media_type,
        "season_number": season_number,
    }

    if media_type == "game" and media:
        initial_data["progress"] = helpers.minutes_to_hhmm(media.progress)

    form = get_form_class(media_type)(instance=media, initial=initial_data)

    title, form_id = helpers.get_form_title_and_id(
        media_type,
        media_id,
        season_number,
        request.GET["title"],
    )
    form.helper.form_id = form_id

    return render(
        request,
        "app/components/fill_track.html",
        {
            "title": title,
            "form_id": form_id,
            "form": form,
            "media_exists": media_exists,
            "return_url": request.GET["return_url"],
        },
    )


@require_POST
def media_save(request):
    """Save or update media data to the database."""
    media_id = request.POST["media_id"]
    media_type = request.POST["media_type"]
    model = apps.get_model(app_label="app", model_name=media_type)
    season_number = request.POST.get("season_number")

    search_params = database.get_search_params(
        media_type,
        media_id,
        season_number,
        None,
        request.user,
    )

    try:
        instance = model.objects.get(**search_params)
    except model.DoesNotExist:
        media_metadata = services.get_media_metadata(
            media_type,
            media_id,
            season_number,
        )
        default_params = {
            "title": media_metadata["title"],
            "image": media_metadata["image"],
            "user": request.user,
        }
        if media_type == "season":
            default_params["season_number"] = season_number
            default_params["title"] = media_metadata["tv_title"]

        instance = model(**default_params)

    # Validate the form and save the instance if it's valid
    form_class = get_form_class(media_type)
    form = form_class(request.POST, instance=instance)
    if form.is_valid():
        form.save()
        logger.info("%s saved successfully.", form.instance)
    else:
        logger.error(form.errors.as_json())
        messages.error(
            request,
            "Could not save the media item, there were errors in the form.",
        )

    return helpers.redirect_back(request)


@require_POST
def media_delete(request):
    """Delete media data from the database."""
    media_type = request.POST["media_type"]

    search_params = database.get_search_params(
        media_type,
        request.POST["media_id"],
        request.POST.get("season_number"),
        None,
        request.user,
    )

    model = apps.get_model(app_label="app", model_name=media_type)
    try:
        media = model.objects.get(**search_params)
        media.delete()
        logger.info("%s deleted successfully.", media)

    except model.DoesNotExist:
        logger.warning("The %s was already deleted before.", media_type)

    return helpers.redirect_back(request)


@require_POST
def episode_handler(request):
    """Handle the creation, deletion, and updating of episodes for a season."""
    media_id = request.POST["media_id"]
    season_number = request.POST["season_number"]

    try:
        related_season = Season.objects.get(
            media_id=media_id,
            user=request.user,
            season_number=season_number,
        )
    except Season.DoesNotExist:
        season_metadata = tmdb.season(media_id, season_number)
        related_season = Season(
            media_id=media_id,
            image=season_metadata["image"],
            score=None,
            status=STATUS_IN_PROGRESS,
            notes="",
            user=request.user,
            season_number=season_number,
        )
        related_season.related_tv = related_season.get_tv()
        related_season.title = related_season.related_tv.title

        Season.save(related_season)
        logger.info("%s did not exist, it was created successfully.", related_season)

    episode_number = request.POST["episode_number"]
    if "unwatch" in request.POST:
        related_season.unwatch(episode_number)

    else:
        if "release" in request.POST:
            watch_date = request.POST["release"]
        else:
            # set watch date from form
            watch_date = request.POST["date"]

        related_season.watch(episode_number, watch_date)

    return helpers.redirect_back(request)


@require_GET
def history(request):
    """Return the history page for a media item."""
    media_type = request.GET["media_type"]

    search_params = database.get_search_params(
        media_type,
        request.GET["media_id"],
        request.GET.get("season_number"),
        request.GET.get("episode_number"),
        request.user,
    )

    model = apps.get_model(app_label="app", model_name=media_type)

    changes = []
    try:
        media = model.objects.get(**search_params)
        history = media.history.all()
        if history is not None:
            last = history.first()
            for _ in range(history.count()):
                new_record, old_record = last, last.prev_record
                if old_record is not None:
                    delta = new_record.diff_against(old_record)
                    changes.append(delta)
                    last = old_record
                else:
                    # If there is no previous record, it's a creation entry
                    history_model = apps.get_model(
                        app_label="app",
                        model_name=f"historical{media_type}",
                    )
                    creation_changes = [
                        {
                            "field": field.verbose_name,
                            "new": getattr(new_record, field.attname),
                        }
                        for field in history_model._meta.get_fields()  # noqa: SLF001
                        if getattr(new_record, field.attname)  # not None/0/empty
                        and not field.name.startswith("history")
                        and field.name != "id"
                    ]
                    changes.append(
                        {
                            "new_record": new_record,
                            "changes": creation_changes,
                        },
                    )
    except model.DoesNotExist:
        pass

    return render(
        request,
        "app/components/fill_history.html",
        {
            "media_type": media_type,
            "changes": changes,
            "return_url": request.GET["return_url"],
        },
    )


@require_POST
def history_delete(request):
    """Delete a history record for a media item."""
    history_id = request.POST["history_id"]
    media_type = request.POST["media_type"]

    model_name = f"historical{media_type}"

    history = apps.get_model(app_label="app", model_name=model_name).objects.get(
        history_id=history_id,
    )

    if history.history_user_id == request.user.id:
        history.delete()
        logger.info("History record deleted successfully.")
    else:
        logger.warning("User does not have permission to delete this history record.")

    return helpers.redirect_back(request)


@require_http_methods(["GET", "POST"])
def lists(request):
    """Return the custom list page."""
    custom_lists = CustomList.objects.filter(user=request.user)

    if request.method == "POST":
        if "create" in request.POST:
            form = CustomListForm(request.POST)
            if form.is_valid():
                custom_list = form.save(commit=False)
                custom_list.user = request.user
                custom_list.save()
                logger.info("List: %s created successfully.", custom_list)
                return redirect("lists")
        elif "edit" in request.POST:
            list_id = request.POST.get("list_id")
            custom_list = get_object_or_404(CustomList, id=list_id, user=request.user)
            form = CustomListForm(request.POST, instance=custom_list)
            if form.is_valid():
                form.save()
                logger.info("List: %s edited successfully.", custom_list)
                return redirect("lists")
        elif "delete" in request.POST:
            list_id = request.POST.get("list_id")
            custom_list = get_object_or_404(CustomList, id=list_id, user=request.user)
            custom_list.delete()
            logger.info("List: %s deleted successfully.", custom_list)
            return redirect("lists")

    create_form = CustomListForm()

    # Create a form for each custom list to edit them
    for custom_list in custom_lists:
        custom_list.form = CustomListForm(instance=custom_list)

    return render(
        request,
        "app/custom_lists.html",
        {"custom_lists": custom_lists, "create_form": create_form},
    )


@require_GET
def lists_modal(request):
    """Return the modal showing all custom lists and allowing to add to them."""
    media_type = request.GET["media_type"]
    media_id = request.GET["media_id"]
    season_number = request.GET.get("season_number")
    episode_number = request.GET.get("episode_number")

    item, _ = ListItem.objects.get_or_create(
        media_id=media_id,
        media_type=media_type,
        season_number=season_number,
        episode_number=episode_number,
        defaults={
            "title": request.GET["title"],
            "image": request.GET["image"],
        },
    )

    custom_lists = CustomList.objects.filter(user=request.user)

    return render(
        request,
        "app/components/fill_lists.html",
        {"item": item, "custom_lists": custom_lists},
    )


@require_POST
def list_item_toggle(request):
    """Add or remove an item from a custom list."""
    item_id = request.POST["item_id"]
    custom_list_id = request.POST["custom_list_id"]

    item = get_object_or_404(ListItem, id=item_id)
    custom_list = get_object_or_404(CustomList, id=custom_list_id, user=request.user)

    if item in custom_list.items.all():
        custom_list.items.remove(item)
        logger.info("Item: %s removed from list: %s.", item, custom_list)
        icon_class = "bi bi-plus-square me-1"
    else:
        custom_list.items.add(item)
        logger.info("Item: %s added to list: %s.", item, custom_list)
        icon_class = "bi bi-check-square-fill me-1"

    return render(request, "app/components/list_icon.html", {"icon_class": icon_class})
