import datetime

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Column, Layout, Row
from django import forms

from app.utils import metadata

from .models import TV, Anime, Episode, Manga, Movie, Season


class MediaForm(forms.ModelForm):
    media_type = forms.CharField(
        max_length=20,
        widget=forms.HiddenInput(),
    )

    def clean(self):
        cleaned_data = super().clean()
        if self.post_processing:
            media_id = cleaned_data.get("media_id")
            media_type = cleaned_data.get("media_type")
            progress = cleaned_data.get("progress")
            status = cleaned_data.get("status")
            start_date = cleaned_data.get("start_date")
            end_date = cleaned_data.get("end_date")

            # if status is changed or media is being added
            if "status" in self.changed_data or self.instance.pk is None:
                if status == "Completed":
                    if not end_date:
                        cleaned_data["end_date"] = datetime.date.today()

                    if isinstance(self, AnimeForm) or isinstance(self, MangaForm):
                        cleaned_data["progress"] = metadata.anime_manga(
                            media_type, media_id
                        )["num_episodes"]

                elif status == "Watching" and not start_date:
                    cleaned_data["start_date"] = datetime.date.today()

            if "progress" in self.changed_data:
                total_episodes = metadata.get_media_metadata(media_type, media_id)[
                    "num_episodes"
                ]

                # limit progress to total_episodes
                if progress > total_episodes:
                    cleaned_data["progress"] = total_episodes

                # If progress == total_episodes and status not explicitly changed
                if progress == total_episodes and "status" not in self.changed_data:
                    cleaned_data["status"] = "Completed"
                    cleaned_data["end_date"] = datetime.date.today()

        return cleaned_data

    def __init__(self, *args, **kwargs):
        self.post_processing = kwargs.pop("post_processing", True)
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "media_id",
            "media_type",
            Row(
                Column("score", css_class="form-group col-md-6 pe-1"),
                Column("progress", css_class="form-group col-md-6 ps-1"),
                css_class="form-row",
            ),
            "status",
            Row(
                Column("start_date", css_class="form-group col-md-6 pe-1"),
                Column("end_date", css_class="form-group col-md-6 ps-1"),
                css_class="form-row",
            ),
            "notes",
        )

    class Meta:
        fields = [
            "media_id",
            "media_type",
            "score",
            "progress",
            "status",
            "start_date",
            "end_date",
            "notes",
        ]
        widgets = {
            "media_id": forms.HiddenInput(),
            "score": forms.NumberInput(attrs={"min": 0, "max": 10, "step": 0.1}),
            "progress": forms.NumberInput(attrs={"min": 0}),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
        }


class MangaForm(MediaForm):
    class Meta(MediaForm.Meta):
        model = Manga


class AnimeForm(MediaForm):
    class Meta(MediaForm.Meta):
        model = Anime


class MovieForm(MediaForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        # movies don"t have progress, score will fill whole row
        self.helper.layout = Layout(
            "media_id",
            "media_type",
            "score",
            "status",
            "end_date",
            "notes",
        )

    class Meta(MediaForm.Meta):
        model = Movie
        exclude = ("progress", "start_date")


class TVForm(MediaForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "media_id",
            "media_type",
            "score",
            "notes",
        )

    class Meta(MediaForm.Meta):
        model = TV
        exclude = ("progress", "status", "start_date", "end_date")


class SeasonForm(MediaForm):
    season_number = forms.IntegerField(
        min_value=0,
        step_size=1,
        widget=forms.HiddenInput(),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.helper = FormHelper()
        self.helper.layout = Layout(
            "media_id",
            "media_type",
            "season_number",
            "score",
            "status",
            "notes",
        )

    class Meta(MediaForm.Meta):
        model = Season
        exclude = ("progress", "start_date", "end_date")


class EpisodeForm(forms.ModelForm):
    class Meta:
        model = Episode
        fields = ("episode_number", "watch_date")


class FilterForm(forms.Form):
    status = forms.ChoiceField(
        choices=[
            ("all", "All"),
            ("completed", "Completed"),
            ("watching", "Watching"),
            ("paused", "Paused"),
            ("dropped", "Dropped"),
            ("planning", "Planning"),
        ],
    )

    sort = forms.ChoiceField(choices=[])

    def __init__(self, *args, **kwargs):
        sort_choices = kwargs.pop("sort_choices")

        super().__init__(*args, **kwargs)
        # add extra sort choices
        self.fields["sort"].choices = [choice for choice in sort_choices]
