import datetime
import logging

from django.conf import settings
from django.core.validators import (
    DecimalValidator,
    MaxValueValidator,
    MinValueValidator,
)
from django.db import models
from django.db.models import CheckConstraint, Max, Q, Sum, UniqueConstraint
from django.urls import reverse
from django.utils import timezone
from model_utils import FieldTracker
from simple_history.models import HistoricalRecords
from simple_history.utils import bulk_create_with_history, bulk_update_with_history

import events
from app.providers import services, tmdb
from app.templatetags.app_tags import slug

logger = logging.getLogger(__name__)


class Item(models.Model):
    """Model for items in custom lists."""

    class Sources(models.TextChoices):
        """Choices for the source of the item."""

        TMDB = "tmdb", "The Movie Database"
        MAL = "mal", "MyAnimeList"
        MANGAUPDATES = "mangaupdates", "MangaUpdates"
        IGDB = "igdb", "Internet Game Database"
        OPENLIBRARY = "openlibrary", "Open Library"
        MANUAL = "manual", "Manual"

    class MediaTypes(models.TextChoices):
        """Choices for the media type of the item."""

        TV = "tv", "TV Show"
        SEASON = "season", "Season"
        EPISODE = "episode", "Episode"
        MOVIE = "movie", "Movie"
        ANIME = "anime", "Anime"
        MANGA = "manga", "Manga"
        GAME = "game", "Game"
        BOOK = "book", "Book"

    media_id = models.CharField(max_length=20)
    source = models.CharField(
        max_length=20,
        choices=Sources,
    )
    media_type = models.CharField(
        max_length=10,
        choices=MediaTypes,
        default=MediaTypes.MOVIE.value,
    )
    title = models.CharField(max_length=255)
    image = models.URLField()  # if add default, custom media entry will show the value
    season_number = models.PositiveIntegerField(null=True, blank=True)
    episode_number = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        """Meta options for the model."""

        constraints = [
            UniqueConstraint(
                fields=["media_id", "source", "media_type"],
                condition=Q(season_number__isnull=True, episode_number__isnull=True),
                name="unique_item_without_season_episode",
            ),
            UniqueConstraint(
                fields=["media_id", "source", "media_type", "season_number"],
                condition=Q(season_number__isnull=False, episode_number__isnull=True),
                name="unique_item_with_season",
            ),
            UniqueConstraint(
                fields=[
                    "media_id",
                    "source",
                    "media_type",
                    "season_number",
                    "episode_number",
                ],
                condition=Q(season_number__isnull=False, episode_number__isnull=False),
                name="unique_item_with_season_episode",
            ),
            CheckConstraint(
                check=Q(
                    media_type="season",
                    season_number__isnull=False,
                    episode_number__isnull=True,
                )
                | ~Q(media_type="season"),
                name="season_number_required_for_season",
            ),
            CheckConstraint(
                check=Q(
                    media_type="episode",
                    season_number__isnull=False,
                    episode_number__isnull=False,
                )
                | ~Q(media_type="episode"),
                name="season_and_episode_required_for_episode",
            ),
            CheckConstraint(
                check=Q(
                    ~Q(media_type__in=["season", "episode"]),
                    season_number__isnull=True,
                    episode_number__isnull=True,
                )
                | Q(media_type__in=["season", "episode"]),
                name="no_season_episode_for_other_types",
            ),
        ]
        ordering = ["media_id"]

    def __str__(self):
        """Return the name of the item."""
        name = self.title
        if self.season_number is not None:
            name += f" S{self.season_number}"
            if self.episode_number is not None:
                name += f"E{self.episode_number}"
        return name

    @classmethod
    def generate_manual_id(cls, media_type):
        """Generate a new ID for manual items."""
        latest_item = (
            cls.objects.filter(source="manual", media_type=media_type)
            .order_by("-media_id")
            .first()
        )

        if latest_item is None:
            return 1

        return int(latest_item.media_id) + 1

    @property
    def url(self):
        """Return the URL of the item."""
        if self.media_type in ["season", "episode"]:
            return reverse(
                "season_details",
                kwargs={
                    "source": self.source,
                    "media_id": self.media_id,
                    "title": slug(self.title),
                    "season_number": self.season_number,
                },
            )
        return reverse(
            "media_details",
            kwargs={
                "source": self.source,
                "media_type": self.media_type,
                "media_id": self.media_id,
                "title": slug(self.title),
            },
        )

    @property
    def event_color(self):
        """Return the color of the item for the calendar."""
        colors = {
            "anime": "#0d6efd",  # blue
            "manga": "#dc3545",  # red
            "game": "#d63384",  # pink
            "tv": "#198754",  # green
            "season": "#6f42c1",  # purple
            "episode": "#6610f2",  # indigo
            "movie": "#fd7e14",  # orange
            "book": "#ffc107",  # yellow
        }
        return colors[self.media_type]

    @property
    def media_type_readable(self):
        """Return the readable media type."""
        return self.MediaTypes(self.media_type).label


class Media(models.Model):
    """Abstract model for all media types."""

    class Status(models.TextChoices):
        """Choices for item status."""

        IN_PROGRESS = "In progress", "In Progress"
        COMPLETED = "Completed", "Completed"
        REPEATING = "Repeating", "Repeating"
        PLANNING = "Planning", "Planning"
        PAUSED = "Paused", "Paused"
        DROPPED = "Dropped", "Dropped"

    history = HistoricalRecords(
        cascade_delete_history=True,
        inherit=True,
        excluded_fields=[
            "item",
            "user",
            "related_tv",
        ],
    )

    item = models.ForeignKey(Item, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    score = models.DecimalField(
        null=True,
        blank=True,
        max_digits=3,
        decimal_places=1,
        validators=[
            DecimalValidator(3, 1),
            MinValueValidator(0),
            MaxValueValidator(10),
        ],
    )
    progress = models.PositiveIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.COMPLETED.value,
    )
    repeats = models.PositiveIntegerField(default=0)
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        """Meta options for the model."""

        abstract = True
        ordering = ["-score"]
        unique_together = ["item", "user"]

    def __str__(self):
        """Return the title of the media."""
        return self.item.__str__()

    def save(self, *args, **kwargs):
        """Save the media instance."""
        if self.tracker.has_changed("progress"):
            self.process_progress()

        if self.tracker.has_changed("status"):
            self.process_status()

        super().save(*args, **kwargs)

    def process_progress(self):
        """Update fields depending on the progress of the media."""
        if self.progress < 0:
            self.progress = 0
        else:
            max_progress = services.get_media_metadata(
                self.item.media_type,
                self.item.media_id,
                self.item.source,
            )["max_progress"]

            if max_progress:
                self.progress = min(self.progress, max_progress)

                if self.progress == max_progress:
                    self.status = self.Status.COMPLETED.value

    def process_status(self):
        """Update fields depending on the status of the media."""
        now = timezone.now().date()

        if self.status == self.Status.IN_PROGRESS.value:
            if not self.start_date:
                self.start_date = now
            events.tasks.reload_calendar.delay(items_to_process=[self.item])

        elif self.status == self.Status.COMPLETED.value:
            if not self.end_date:
                self.end_date = now

            max_progress = services.get_media_metadata(
                self.item.media_type,
                self.item.media_id,
                self.item.source,
            )["max_progress"]

            if max_progress:
                self.progress = max_progress

            if self.tracker.previous("status") == self.Status.REPEATING.value:
                self.repeats += 1

        elif self.status in (self.Status.PLANNING.value, self.Status.PAUSED.value):
            events.tasks.reload_calendar.delay(items_to_process=[self.item])

    def increase_progress(self):
        """Increase the progress of the media by one."""
        self.progress += 1
        self.save()
        logger.info("Watched %s E%s", self, self.progress)

    def decrease_progress(self):
        """Decrease the progress of the media by one."""
        self.progress -= 1
        self.save()
        logger.info("Unwatched %s E%s", self, self.progress + 1)

    def progress_response(self):
        """Return the data needed to update the progress of the media."""
        media_metadata = services.get_media_metadata(
            self.item.media_type,
            self.item.media_id,
            self.item.source,
        )
        response = {"item": self.item}
        max_progress = media_metadata["max_progress"]

        response["progress"] = self.progress
        response["max"] = self.progress == max_progress
        response["min"] = self.progress == 0

        return response


class TV(Media):
    """Model for TV shows."""

    tracker = FieldTracker()

    @tracker  # postpone field reset until after the save
    def save(self, *args, **kwargs):
        """Save the media instance."""
        super(Media, self).save(*args, **kwargs)

        if self.tracker.has_changed("status"):
            if self.status == self.Status.COMPLETED.value:
                self.completed()
            elif self.status in (
                self.Status.IN_PROGRESS.value,
                self.Status.PLANNING.value,
                self.Status.PAUSED.value,
            ):
                events.tasks.reload_calendar.delay(items_to_process=[self.item])

    @property
    def progress(self):
        """Return the total episodes watched for the TV show."""
        return sum(season.progress for season in self.seasons.all())

    @property
    def repeats(self):
        """Return the number of max repeated episodes in the TV show."""
        return max((season.repeats for season in self.seasons.all()), default=0)

    @property
    def start_date(self):
        """Return the date of the first episode watched."""
        return min(
            (season.start_date for season in self.seasons.all()),
            default=datetime.date(datetime.MINYEAR, 1, 1),
        )

    @property
    def end_date(self):
        """Return the date of the last episode watched."""
        return max(
            (season.end_date for season in self.seasons.all()),
            default=datetime.date(datetime.MINYEAR, 1, 1),
        )

    def completed(self):
        """Create remaining seasons and episodes for a TV show."""
        tv_metadata = services.get_media_metadata(
            self.item.media_type,
            self.item.media_id,
            self.item.source,
        )
        max_progress = tv_metadata["max_progress"]

        if not max_progress or self.progress > max_progress:
            return

        seasons_to_update = []
        episodes_to_create = []

        season_numbers = [
            season["season_number"]
            for season in tv_metadata["related"]["seasons"]
            if season["season_number"] != 0
        ]
        tv_with_seasons_metadata = services.get_media_metadata(
            "tv_with_seasons",
            self.item.media_id,
            self.item.source,
            season_numbers,
        )
        for season_number in season_numbers:
            season_metadata = tv_with_seasons_metadata[f"season/{season_number}"]

            item, _ = Item.objects.get_or_create(
                media_id=self.item.media_id,
                source=self.item.source,
                media_type="season",
                season_number=season_number,
                defaults={
                    "title": self.item.title,
                    "image": season_metadata["image"],
                },
            )
            try:
                season_instance = Season.objects.get(
                    item=item,
                    user=self.user,
                )

                if season_instance.status != self.Status.COMPLETED.value:
                    season_instance.status = self.Status.COMPLETED.value
                    seasons_to_update.append(season_instance)

            except Season.DoesNotExist:
                season_instance = Season(
                    item=item,
                    score=None,
                    status=self.Status.COMPLETED.value,
                    notes="",
                    related_tv=self,
                    user=self.user,
                )
                Season.save_base(season_instance)
            episodes_to_create.extend(
                season_instance.get_remaining_eps(season_metadata),
            )
        bulk_update_with_history(seasons_to_update, Season, ["status"])
        bulk_create_with_history(episodes_to_create, Episode)


class Season(Media):
    """Model for seasons of TV shows."""

    related_tv = models.ForeignKey(
        TV,
        on_delete=models.CASCADE,
        related_name="seasons",
    )

    tracker = FieldTracker()

    class Meta:
        """Limit the uniqueness of seasons.

        Only one season per media can have the same season number.
        """

        unique_together = ["related_tv", "item"]

    def __str__(self):
        """Return the title of the media and season number."""
        return f"{self.item.title} S{self.item.season_number}"

    @tracker  # postpone field reset until after the save
    def save(self, *args, **kwargs):
        """Save the media instance."""
        # if related_tv is not set
        if self.related_tv_id is None:
            self.related_tv = self.get_tv()

        super(Media, self).save(*args, **kwargs)

        if self.tracker.has_changed("status"):
            if self.status == self.Status.COMPLETED.value:
                season_metadata = services.get_media_metadata(
                    "season",
                    self.item.media_id,
                    self.item.source,
                    [self.item.season_number],
                )
                bulk_create_with_history(
                    self.get_remaining_eps(season_metadata),
                    Episode,
                )
            elif self.status in (
                self.Status.IN_PROGRESS.value,
                self.Status.PLANNING.value,
                self.Status.PAUSED.value,
            ):
                events.tasks.reload_calendar.delay(items_to_process=[self.item])

    @property
    def progress(self):
        """Return the total episodes watched for the season."""
        return self.episodes.count()

    @property
    def current_episode(self):
        """Return the current episode of the season."""
        # continue initial watch
        if self.status == self.Status.IN_PROGRESS.value:
            sorted_episodes = sorted(
                self.episodes.all(),
                key=lambda e: e.item.episode_number,
                reverse=True,
            )
        else:
            # sort by repeats and then by episode_number
            sorted_episodes = sorted(
                self.episodes.all(),
                key=lambda e: (e.repeats, e.item.episode_number),
                reverse=True,
            )

        if sorted_episodes:
            return sorted_episodes[0]
        return None

    @property
    def repeats(self):
        """Return the number of max repeated episodes in the season."""
        return max((episodes.repeats for episodes in self.episodes.all()), default=0)

    @property
    def start_date(self):
        """Return the date of the first episode watched."""
        return min(
            (episode.watch_date for episode in self.episodes.all()),
            default=datetime.date(datetime.MINYEAR, 1, 1),
        )

    @property
    def end_date(self):
        """Return the date of the last episode watched."""
        return max(
            (episode.watch_date for episode in self.episodes.all()),
            default=datetime.date(datetime.MINYEAR, 1, 1),
        )

    def increase_progress(self):
        """Watch the next episode of the season."""
        current_episode = self.current_episode
        season_metadata = services.get_media_metadata(
            "season",
            self.item.media_id,
            self.item.source,
            [self.item.season_number],
        )
        episodes = season_metadata["episodes"]

        if current_episode:
            next_episode_number = tmdb.find_next_episode(
                current_episode.item.episode_number,
                episodes,
            )
        else:
            # start watching from the first episode
            next_episode_number = episodes[0]["episode_number"]

        today = timezone.now().date()

        if next_episode_number:
            self.watch(next_episode_number, today)
        else:
            logger.info("No more episodes to watch.")

    def watch(self, episode_number, watch_date):
        """Create or add a repeat to an episode of the season."""
        item = self.get_episode_item(episode_number)

        try:
            episode = Episode.objects.get(
                related_season=self,
                item=item,
            )
            episode.watch_date = watch_date
            episode.repeats += 1
            episode.save()
            logger.info(
                "%s rewatched successfully.",
                episode,
            )
        except Episode.DoesNotExist:
            # from the form, watch_date is a string
            if watch_date == "None":
                watch_date = None

            episode = Episode.objects.create(
                related_season=self,
                item=item,
                watch_date=watch_date,
            )
            logger.info(
                "%s created successfully.",
                episode,
            )

    def decrease_progress(self):
        """Unwatch the current episode of the season."""
        episode_number = self.current_episode.item.episode_number
        self.unwatch(episode_number)

    def unwatch(self, episode_number):
        """Unwatch the episode instance."""
        try:
            item = self.get_episode_item(episode_number)

            episode = Episode.objects.get(
                related_season=self,
                item=item,
            )

            if episode.repeats > 0:
                episode.repeats -= 1
                episode.save(update_fields=["repeats"])
                logger.info(
                    "%s watch count decreased.",
                    episode,
                )
            else:
                episode.delete()
                logger.info(
                    "%s deleted successfully.",
                    episode,
                )

        except Episode.DoesNotExist:
            logger.warning(
                "Episode %sE%s does not exist.",
                self,
                episode_number,
            )

    def progress_response(self):
        """Return the data needed to update the progress of the season."""
        media_metadata = services.get_media_metadata(
            self.item.media_type,
            self.item.media_id,
            self.item.source,
            [self.item.season_number],
        )
        response = {"item": self.item}
        max_progress = media_metadata["max_progress"]

        response["current_episode"] = self.current_episode
        if self.current_episode:
            response["max"] = self.current_episode.item.episode_number == max_progress
            response["min"] = False
        else:
            response["max"] = False
            response["min"] = True

        return response

    def get_tv(self):
        """Get related TV instance for a season and create it if it doesn't exist."""
        try:
            tv = TV.objects.get(
                item__media_id=self.item.media_id,
                item__media_type="tv",
                item__season_number=None,
                item__source=self.item.source,
                user=self.user,
            )
        except TV.DoesNotExist:
            tv_metadata = services.get_media_metadata(
                "tv",
                self.item.media_id,
                self.item.source,
            )

            # creating tv with multiple seasons from a completed season
            if (
                self.status == self.Status.COMPLETED.value
                and tv_metadata["details"]["seasons"] > 1
            ):
                status = self.Status.IN_PROGRESS.value
            else:
                status = self.status

            item, _ = Item.objects.get_or_create(
                media_id=self.item.media_id,
                source="tmdb",
                media_type="tv",
                defaults={
                    "title": tv_metadata["title"],
                    "image": tv_metadata["image"],
                },
            )

            tv = TV.objects.create(
                item=item,
                score=None,
                status=status,
                notes="",
                user=self.user,
            )

            logger.info("%s did not exist, it was created successfully.", tv)

        return tv

    def get_remaining_eps(self, season_metadata):
        """Return episodes needed to complete a season."""
        max_episode_number = Episode.objects.filter(related_season=self).aggregate(
            max_episode_number=Max("item__episode_number"),
        )["max_episode_number"]

        if max_episode_number is None:
            max_episode_number = 0

        episodes_to_create = []
        today = timezone.now().date()

        # Create Episode objects for the remaining episodes
        for episode in reversed(season_metadata["episodes"]):
            if episode["episode_number"] <= max_episode_number:
                break

            item = self.get_episode_item(episode["episode_number"], season_metadata)

            episode_db = Episode(
                related_season=self,
                item=item,
                watch_date=today,
            )
            episodes_to_create.append(episode_db)

        return episodes_to_create

    def get_episode_item(self, episode_number, season_metadata=None):
        """Get the episode item instance, create it if it doesn't exist."""
        if not season_metadata:
            season_metadata = services.get_media_metadata(
                "season",
                self.item.media_id,
                self.item.source,
                [self.item.season_number],
            )

        image = settings.IMG_NONE
        for episode in season_metadata["episodes"]:
            if episode["episode_number"] == episode_number:
                if episode.get("still_path"):
                    image = f"http://image.tmdb.org/t/p/original{episode['still_path']}"
                elif "image" in episode:
                    # for manual seasons
                    image = episode["image"]
                else:
                    image = settings.IMG_NONE
                break

        item, _ = Item.objects.get_or_create(
            media_id=self.item.media_id,
            source=self.item.source,
            media_type="episode",
            season_number=self.item.season_number,
            episode_number=episode_number,
            defaults={
                "title": self.item.title,
                "image": image,
            },
        )

        return item


class Episode(models.Model):
    """Model for episodes of a season."""

    history = HistoricalRecords(
        cascade_delete_history=True,
        excluded_fields=["item", "related_season"],
    )

    item = models.ForeignKey(Item, on_delete=models.CASCADE, null=True)
    related_season = models.ForeignKey(
        Season,
        on_delete=models.CASCADE,
        related_name="episodes",
    )
    watch_date = models.DateField(null=True, blank=True)
    repeats = models.PositiveIntegerField(default=0)

    class Meta:
        """Limit the uniqueness of episodes.

        Only one episode per season can have the same episode number.
        """

        unique_together = ["related_season", "item"]
        ordering = ["related_season", "item"]

    def __str__(self):
        """Return the season and episode number."""
        return self.item.__str__()

    def save(self, *args, **kwargs):
        """Save the episode instance."""
        super().save(*args, **kwargs)

        if self.related_season.status in (
            Media.Status.IN_PROGRESS.value,
            Media.Status.REPEATING.value,
        ):
            season_number = self.item.season_number
            tv_with_seasons_metadata = services.get_media_metadata(
                "tv_with_seasons",
                self.item.media_id,
                self.item.source,
                [season_number],
            )
            season_metadata = tv_with_seasons_metadata[f"season/{season_number}"]
            max_progress = len(season_metadata["episodes"])
            total_repeats = self.related_season.episodes.aggregate(
                total_repeats=Sum("repeats"),
            )["total_repeats"]

            total_watches = self.related_season.progress + total_repeats

            if total_watches >= max_progress * (self.related_season.repeats + 1):
                self.related_season.status = Media.Status.COMPLETED.value
                self.related_season.save_base(update_fields=["status"])

                last_season = tv_with_seasons_metadata["related"]["seasons"][-1][
                    "season_number"
                ]
                # mark the TV show as completed if it's the last season
                if season_number == last_season:
                    self.related_season.related_tv.status = Media.Status.COMPLETED.value
                    self.related_season.related_tv.save_base(update_fields=["status"])


class Manga(Media):
    """Model for manga."""

    tracker = FieldTracker()


class Anime(Media):
    """Model for anime."""

    tracker = FieldTracker()


class Movie(Media):
    """Model for movies."""

    tracker = FieldTracker()


class Game(Media):
    """Model for games."""

    tracker = FieldTracker()

    def increase_progress(self):
        """Increase the progress of the media by 30 minutes."""
        self.progress += 30
        self.save()
        logger.info("Watched %s E%s", self, self.progress)

    def decrease_progress(self):
        """Decrease the progress of the media by 30 minutes."""
        self.progress -= 30
        self.save()
        logger.info("Unwatched %s E%s", self, self.progress + 1)


class Book(Media):
    """Model for books."""

    tracker = FieldTracker()
