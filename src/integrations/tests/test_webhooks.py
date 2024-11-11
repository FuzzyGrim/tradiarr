import json

from django.test import Client, TestCase
from django.urls import reverse

from app.models import TV, Episode, Item, Movie, Season
from users.models import User


class JellyfinWebhookTests(TestCase):
    """Tests for Jellyfin webhook."""

    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create(username="testuser", token="test-token")  # noqa: S106
        self.url = reverse("jellyfin_webhook", kwargs={"token": "test-token"})

    def test_invalid_token(self):
        """Test webhook with invalid token returns 401."""
        url = reverse("jellyfin_webhook", kwargs={"token": "invalid-token"})
        response = self.client.post(url, data={}, content_type="application/json")
        self.assertEqual(response.status_code, 401)

    def test_tv_episode_mark_played(self):
        """Test webhook handles TV episode mark played event."""
        payload = {
            "Event": "MarkPlayed",
            "Item": {
                "Type": "Episode",
                "ProviderIds": {"Tmdb": "1668"},
                "ParentIndexNumber": 1,
                "IndexNumber": 1,
                "UserData": {"Played": True},
            },
        }

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        # Verify objects were created
        tv_item = Item.objects.get(media_type="tv", media_id="1668")
        self.assertEqual(tv_item.title, "Friends")

        tv = TV.objects.get(item=tv_item, user=self.user)
        self.assertEqual(tv.status, "In progress")

        season = Season.objects.get(
            item__media_type="season",
            item__season_number=1,
        )
        self.assertEqual(season.status, "In progress")

        episode = Episode.objects.get(
            item__media_type="episode",
            item__season_number=1,
            item__episode_number=1,
        )
        self.assertIsNotNone(episode.watch_date)

    def test_movie_mark_played(self):
        """Test webhook handles movie mark played event."""
        payload = {
            "Event": "MarkPlayed",
            "Item": {
                "Type": "Movie",
                "ProviderIds": {"Tmdb": "10494"},
                "UserData": {"Played": True},
            },
        }

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)

        # Verify movie was created and marked as completed
        movie = Movie.objects.get(
            item__media_type="movie",
            item__media_id="10494",
        )
        self.assertEqual(movie.status, "Completed")
        self.assertEqual(movie.progress, 1)

    def test_ignored_event_types(self):
        """Test webhook ignores irrelevant event types."""
        payload = {
            "Event": "SomeOtherEvent",
            "Item": {
                "Type": "Movie",
                "ProviderIds": {"Tmdb": "12345"},
                "UserData": {"Played": True},
            },
        }

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Movie.objects.count(), 0)

    def test_missing_tmdb_id(self):
        """Test webhook handles missing TMDB ID gracefully."""
        payload = {
            "Event": "MarkPlayed",
            "Item": {
                "Type": "Movie",
                "ProviderIds": {},
                "UserData": {"Played": True},
            },
        }

        response = self.client.post(
            self.url,
            data=json.dumps(payload),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Movie.objects.count(), 0)
