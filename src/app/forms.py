from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Layout, Row
from django import forms
from django.conf import settings
from django.urls import reverse

from app import models
from app.models import Item


def get_form_class(media_type):
    """Return the form class for the media type."""
    class_name = media_type.capitalize() + "Form"
    return globals().get(class_name, None)


class CustomDurationField(forms.CharField):
    """Custom form field for duration input."""

    def clean(self, value):
        """Validate the time string."""
        cleaned_value = super().clean(value)
        msg = "Invalid time format. Please use hh:mm, [n]h [n]min or [n]h[n]min format."
        if not cleaned_value:
            return 0
        try:
            if ":" in cleaned_value:  # hh:mm format
                hours, minutes = map(int, cleaned_value.split(":"))
            elif " " in cleaned_value:  # [n]h [n]min format
                hours, minutes = cleaned_value.split(" ")
                hours = int(hours.strip("h"))
                minutes = int(minutes.strip("min"))
            elif "h" in cleaned_value and "min" in cleaned_value:  # [n]h[n]min format
                hours, minutes = cleaned_value.split("h")
                hours = int(hours)
                minutes = int(minutes.strip("min"))
            elif "min" in cleaned_value:  # [n]min format
                hours = 0
                minutes = int(cleaned_value.strip("min"))
            elif "h" in cleaned_value:  # [n]h format
                hours = int(cleaned_value.strip("h"))
                minutes = 0
            else:
                raise forms.ValidationError(msg)
        # error parsing the time string
        except ValueError as error:
            raise forms.ValidationError(msg) from error
        else:
            max_min = 59
            if not (0 <= minutes <= max_min):
                msg = f"Minutes must be between 0 and {max_min}."
                raise forms.ValidationError(msg)
            return hours * 60 + minutes


class ManualItemForm(forms.ModelForm):
    """Form for adding items to the database."""

    parent_tv = forms.ModelChoiceField(
        required=False,
        queryset=models.TV.objects.none(),
        empty_label="Select",
        label="Parent TV Show",
    )

    parent_season = forms.ModelChoiceField(
        required=False,
        queryset=models.Season.objects.none(),
        empty_label="Select",
        label="Parent Season",
    )

    class Meta:
        """Bind form to model."""

        model = models.Item
        fields = [
            "media_type",
            "title",
            "image",
            "season_number",
            "episode_number",
        ]

    def __init__(self, *args, **kwargs):
        """Initialize the form."""
        self.user = kwargs.pop("user", None)
        super().__init__(*args, **kwargs)
        if self.user:
            self.fields["parent_tv"].queryset = models.TV.objects.filter(
                user=self.user,
                item__source="manual",
                item__media_type="tv",
            )
            self.fields["parent_season"].queryset = models.Season.objects.filter(
                user=self.user,
                item__source="manual",
                item__media_type="season",
            )

        self.fields["media_type"].widget.attrs = {
            "hx-get": reverse("create_media"),
            "hx-target": "#media-form",
            "initial": "movie",
        }
        self.fields["image"].required = False
        self.fields["title"].required = False

        self.helper = FormHelper()

        self.helper.layout = Layout(
            "media_type",
            "parent_tv",
            "parent_season",
            "title",
            "image",
            "season_number",
            "episode_number",
        )

        self.helper.form_tag = False

    def clean(self):
        """Validate the form."""
        cleaned_data = super().clean()
        image = cleaned_data.get("image")
        media_type = cleaned_data.get("media_type")
        title = cleaned_data.get("title")

        if not image:
            cleaned_data["image"] = settings.IMG_NONE

        # Title not required for season/episode
        if media_type in ["season", "episode"] and not title:
            if media_type == "season":
                parent = cleaned_data.get("parent_tv")
                cleaned_data["title"] = parent.item.title
            else:  # episode
                parent = cleaned_data.get("parent_season")
                cleaned_data["title"] = parent.item.title
                cleaned_data["season_number"] = parent.item.season_number

        return cleaned_data

    def save(self, commit=True):  # noqa: FBT002
        """Save the form and handle manual media ID generation."""
        instance = super().save(commit=False)
        instance.source = "manual"

        if instance.media_type == "season":
            parent_tv = self.cleaned_data["parent_tv"]
            instance.media_id = parent_tv.item.media_id
        elif instance.media_type == "episode":
            parent_season = self.cleaned_data["parent_season"]
            instance.media_id = parent_season.item.media_id
            instance.season_number = parent_season.item.season_number
        else:
            instance.media_id = Item.generate_manual_id()

        if commit:
            instance.save()
        return instance


class MediaForm(forms.ModelForm):
    """Base form for all media types."""

    def __init__(self, *args, **kwargs):
        """Initialize the form."""
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()

        left_col = "form-group col-md-6 pe-md-1"
        right_col = "form-group col-md-6 ps-md-1"

        self.helper.layout = Layout(
            "item",
            Row(
                Column("score", css_class=left_col),
                Column("progress", css_class=right_col),
                css_class="form-row",
            ),
            Row(
                Column("status", css_class=left_col),
                Column("repeats", css_class=right_col),
                css_class="form-row",
            ),
            Row(
                Column("start_date", css_class=left_col),
                Column("end_date", css_class=right_col),
                css_class="form-row",
            ),
            "notes",
        )

    class Meta:
        """Define fields and input types."""

        fields = [
            "item",
            "score",
            "progress",
            "status",
            "repeats",
            "start_date",
            "end_date",
            "notes",
        ]
        widgets = {
            "item": forms.HiddenInput(),
            "score": forms.NumberInput(attrs={"min": 0, "max": 10, "step": 0.1}),
            "progress": forms.NumberInput(attrs={"min": 0}),
            "repeats": forms.NumberInput(attrs={"min": 0}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class MangaForm(MediaForm):
    """Form for manga."""

    class Meta(MediaForm.Meta):
        """Bind form to model."""

        model = models.Manga


class AnimeForm(MediaForm):
    """Form for anime."""

    class Meta(MediaForm.Meta):
        """Bind form to model."""

        model = models.Anime


class MovieForm(MediaForm):
    """Form for movies."""

    class Meta(MediaForm.Meta):
        """Bind form to model."""

        model = models.Movie


class TvForm(MediaForm):
    """Form for TV shows."""

    def __init__(self, *args, **kwargs):
        """Initialize the form."""
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()

    class Meta(MediaForm.Meta):
        """Bind form to model."""

        model = models.TV
        fields = ["item", "score", "status", "notes"]


class SeasonForm(MediaForm):
    """Form for seasons."""

    def __init__(self, *args, **kwargs):
        """Initialize the form."""
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()

    class Meta(MediaForm.Meta):
        """Bind form to model."""

        model = models.Season
        fields = [
            "item",
            "score",
            "status",
            "notes",
        ]


class EpisodeForm(forms.ModelForm):
    """Form for episodes."""

    class Meta:
        """Bind form to model."""

        model = models.Episode
        fields = ("item", "watch_date", "repeats")

        widgets = {
            "item": forms.HiddenInput(),
            "watch_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        """Initialize the form."""
        super().__init__(*args, **kwargs)


class GameForm(MediaForm):
    """Form for manga."""

    progress = CustomDurationField(
        required=False,
        label="Progress (hh:mm)",
        widget=forms.TextInput(attrs={"placeholder": "hh:mm"}),
    )

    class Meta(MediaForm.Meta):
        """Bind form to model."""

        model = models.Game


class FilterForm(forms.Form):
    """Form for filtering media on media list view."""

    status = forms.ChoiceField(
        choices=[
            # left side in lower case for better looking url when filtering
            ("all", "All"),
            ("completed", models.STATUS_COMPLETED),
            ("in progress", models.STATUS_IN_PROGRESS),
            ("repeating", models.STATUS_REPEATING),
            ("planning", models.STATUS_PLANNING),
            ("paused", models.STATUS_PAUSED),
            ("dropped", models.STATUS_DROPPED),
        ],
    )

    sort = forms.ChoiceField(
        choices=[
            ("score", "Score"),
            ("title", "Title"),
            ("progress", "Progress"),
            ("repeats", "Repeats"),
            ("start_date", "Start Date"),
            ("end_date", "End Date"),
        ],
    )

    layout = forms.ChoiceField(
        choices=[
            ("grid", "Grid"),
            ("table", "Table"),
        ],
    )

    def __init__(self, *args, **kwargs):
        """Initialize the form."""
        layout = kwargs.pop("layout")

        super().__init__(*args, **kwargs)

        self.fields["layout"].initial = layout
