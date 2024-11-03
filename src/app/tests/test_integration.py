import os

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import expect, sync_playwright


class IntegrationTest(StaticLiveServerTestCase):
    """Integration tests for the application."""

    # needed to reset the sequence of the auto incremented id
    # for select parent tv fields in manual creation
    reset_sequences = True

    @classmethod
    def setUpClass(cls):
        """Set up the test class."""
        os.environ["DJANGO_ALLOW_ASYNC_UNSAFE"] = "true"
        super().setUpClass()
        cls.playwright = sync_playwright().start()
        # use headless=False, slow_mo=400 to see the browser
        cls.browser = cls.playwright.chromium.launch()
        cls.page = cls.browser.new_page()

    def setUp(self):
        """Set up test data for CustomList model."""
        self.credentials = {"username": "test", "password": "12345"}
        self.user = get_user_model().objects.create_user(**self.credentials)
        self.page.goto(f"{self.live_server_url}/")
        self.page.get_by_label("Username*").fill(self.credentials["username"])
        self.page.get_by_label("Password*").fill(self.credentials["password"])
        self.page.get_by_role("button", name="Log In").click()

    @classmethod
    def tearDownClass(cls):
        """Tear down the test class."""
        super().tearDownClass()
        cls.browser.close()
        cls.playwright.stop()

    def test_season_progress_edit(self):
        """Test the progress edit of a season."""
        self.page.get_by_placeholder("Search").click()
        self.page.get_by_placeholder("Search").fill("breaking bad")
        self.page.get_by_role("button", name="").click()
        self.page.get_by_role("link", name="Breaking Bad", exact=True).click()
        self.page.get_by_role("link", name="Season 1").click()
        self.page.locator(".mt-auto > div > div > button").first.click()
        self.page.get_by_role("button", name="Release date").click()
        self.page.get_by_role("link", name=" Seasons").click()
        self.page.get_by_role("button", name="").click()
        self.page.get_by_label("Layout*").select_option("table")
        self.page.get_by_role("button", name="Filter").click()
        expect(self.page.get_by_role("cell", name="1", exact=True)).to_be_visible()
        self.page.get_by_role("link", name=" Home").click()
        self.page.get_by_role("button", name="").click()
        self.page.get_by_role("button", name="").click()
        self.page.get_by_role("link", name=" Seasons").click()
        expect(self.page.get_by_role("cell", name="3")).to_be_visible()
        self.page.get_by_role("link", name=" Home").click()
        self.page.get_by_role("button", name="").click()
        self.page.get_by_role("button", name="").click()
        self.page.get_by_role("button", name="").click()
        self.page.get_by_role("link", name=" Seasons").click()
        expect(self.page.get_by_role("cell", name="2", exact=True)).to_be_visible()
        self.page.get_by_role("link", name=" Home").click()
        self.page.get_by_role("button", name="").click()
        self.page.get_by_role("button", name="").click()
        self.page.get_by_role("button", name="").click()
        self.page.get_by_role("button", name="").click()
        self.page.get_by_role("button", name="").click()
        self.page.get_by_role("link", name=" Seasons").click()
        expect(self.page.get_by_role("cell", name="Completed")).to_be_visible()
        expect(self.page.get_by_role("cell", name="7")).to_be_visible()


    def test_tv_completed(self):
        """Test the completed status of a TV show."""
        self.page.get_by_placeholder("Search").click()
        self.page.get_by_placeholder("Search").fill("breaking bad")
        self.page.get_by_placeholder("Search").press("Enter")
        self.page.get_by_role("button", name="").click()
        self.page.get_by_role("button", name="").first.click()
        self.page.get_by_role("button", name="Save").click()
        self.page.get_by_role("link", name=" TV Shows").click()
        self.page.get_by_role("button", name="").click()
        self.page.get_by_label("Layout*").select_option("table")
        self.page.get_by_role("button", name="Filter").click()
        expect(self.page.locator("tbody")).to_contain_text("62")

    def test_season_completed(self):
        """Test the completed status of a season."""
        self.page.get_by_placeholder("Search").click()
        self.page.get_by_placeholder("Search").fill("friends")
        self.page.get_by_placeholder("Search").press("Enter")
        self.page.get_by_role("button", name="").click()
        self.page.get_by_role("link", name="Friends", exact=True).first.click()
        self.page.get_by_role("link", name="Season 1", exact=True).click()
        self.page.get_by_role("button", name="").click()
        self.page.get_by_role("button", name="Save").click()
        expect(self.page.get_by_text("S01.E01 - Pilot 1994-09-22 An")).to_be_visible()
        self.page.get_by_role("link", name=" TV Shows").click()
        self.page.get_by_role("button", name="").click()
        self.page.get_by_label("Layout*").select_option("table")
        self.page.get_by_role("button", name="Filter").click()
        expect(self.page.get_by_role("cell", name="24")).to_be_visible()
        expect(self.page.get_by_role("cell", name="In progress")).to_be_visible()
        self.page.get_by_role("link", name=" Seasons").click()
        self.page.get_by_role("button", name="").click()
        self.page.get_by_label("Layout*").select_option("table")
        self.page.get_by_role("button", name="Filter").click()
        expect(self.page.locator("tbody")).to_contain_text("Completed")

    def test_tv_manual(self):  # noqa: PLR0915
        """Test the manual creation of a TV show."""
        self.page.goto(f"{self.live_server_url}/create/item")
        # create tv show
        self.page.get_by_label("Media type*").select_option("tv")
        self.page.get_by_label("Title").click()
        self.page.get_by_label("Title").fill("example")
        self.page.get_by_label("Image").click()
        self.page.get_by_label("Image").fill(
            "https://media.themoviedb.org/t/p/w300_and_h450_bestv2/2koX1xLkpTQM4IZebYvKysFW1Nh.jpg",
        )
        self.page.get_by_label("Score").click()
        self.page.get_by_label("Score").fill("5")
        self.page.get_by_role("button", name="Submit").click()
        expect(self.page.get_by_text("example added successfully.")).to_be_visible()
        self.page.get_by_role("link", name=" TV Shows").click()
        self.page.get_by_role("button", name="").click()
        self.page.get_by_label("Layout*").select_option("table")
        self.page.get_by_role("button", name="Filter").click()
        expect(self.page.get_by_role("cell", name="5.0")).to_be_visible()
        expect(
            self.page.get_by_role(
                "row",
                name="img example 5.0 Completed 0 ",
            ).get_by_role("button"),
        ).to_be_visible()
        self.page.get_by_role("cell", name="example").click()
        self.page.get_by_role("link", name="example").click()

        # create S1
        self.page.get_by_role("link", name=" Create").click()
        self.page.get_by_label("Media type*").select_option("season")
        self.page.get_by_label("Parent TV Show").select_option("1")
        self.page.get_by_label("Image").click()
        self.page.get_by_label("Image").fill(
            "https://media.themoviedb.org/t/p/w130_and_h195_bestv2/odCW88Cq5hAF0ZFVOkeJmeQv1nV.jpg",
        )
        self.page.get_by_label("Season number").click()
        self.page.get_by_label("Season number").fill("1")
        self.page.get_by_label("Score").click()
        self.page.get_by_label("Score").fill("8")
        self.page.get_by_role("button", name="Submit").click()
        expect(self.page.get_by_text("example S1 added successfully.")).to_be_visible()

        # create S2
        self.page.get_by_label("Media type*").select_option("season")
        self.page.get_by_label("Parent TV Show").select_option("1")
        self.page.get_by_label("Image").click()
        self.page.get_by_label("Image").fill(
            "https://media.themoviedb.org/t/p/w130_and_h195_bestv2/kC9VHoMh1KkoAYfsY3QlHpZRxDy.jpg",
        )
        self.page.get_by_label("Season number").click()
        self.page.get_by_label("Season number").fill("2")
        self.page.get_by_label("Score").click()
        self.page.get_by_label("Score").fill("5")
        self.page.get_by_role("button", name="Submit").click()
        expect(self.page.get_by_text("example S2 added successfully.")).to_be_visible()

        # create S1E1
        self.page.get_by_label("Media type*").select_option("episode")
        self.page.get_by_label("Parent Season").select_option("1")
        self.page.get_by_label("Image").click()
        self.page.get_by_label("Image").fill(
            "https://media.themoviedb.org/t/p/w227_and_h127_bestv2/v6Elr1W2elOyGi1MClgV0mIBVHC.jpg",
        )
        self.page.get_by_label("Episode number").click()
        self.page.get_by_label("Episode number").fill("1")
        self.page.get_by_label("Watch date").fill("2024-10-30")
        self.page.get_by_role("button", name="Submit").click()
        expect(
            self.page.get_by_text("example S1E1 added successfully."),
        ).to_be_visible()

        # create S1E2
        self.page.get_by_label("Title").click()
        self.page.get_by_label("Media type*").select_option("episode")
        self.page.get_by_label("Parent Season").select_option("1")
        self.page.get_by_label("Image").click()
        self.page.get_by_label("Image").fill(
            "https://media.themoviedb.org/t/p/w227_and_h127_bestv2/sRCJ0D0NArqswoo6z26n6Ab11sc.jpg",
        )
        self.page.get_by_label("Episode number").click()
        self.page.get_by_label("Episode number").fill("2")
        self.page.get_by_role("button", name="Submit").click()
        expect(
            self.page.get_by_text("example S1E2 added successfully."),
        ).to_be_visible()

        # create S1E3
        self.page.get_by_label("Media type*").select_option("episode")
        self.page.get_by_label("Parent Season").select_option("1")
        self.page.get_by_label("Image").click()
        self.page.get_by_label("Image").fill(
            "https://media.themoviedb.org/t/p/w227_and_h127_bestv2/byLiFLL4q9MOJzv4SmqJDgkiYr0.jpg",
        )
        self.page.get_by_label("Episode number").click()
        self.page.get_by_label("Episode number").fill("3")
        self.page.get_by_role("button", name="Submit").click()
        expect(
            self.page.get_by_text("example S1E3 added successfully."),
        ).to_be_visible()

        # create S2E1
        self.page.get_by_label("Media type*").select_option("episode")
        self.page.get_by_label("Parent Season").select_option("2")
        self.page.get_by_label("Image").click()
        self.page.get_by_label("Image").fill(
            "https://media.themoviedb.org/t/p/w227_and_h127_bestv2/uovdoaMdaLnk6vKn2nU5QnyR3zW.jpg",
        )
        self.page.get_by_label("Episode number").click()
        self.page.get_by_label("Episode number").fill("1")
        self.page.get_by_label("Watch date").fill("2024-11-01")
        self.page.get_by_role("button", name="Submit").click()
        expect(
            self.page.get_by_text("example S2E1 added successfully."),
        ).to_be_visible()

        # create S2E2
        self.page.get_by_label("Media type*").select_option("episode")
        self.page.get_by_label("Parent Season").select_option("2")
        self.page.get_by_label("Image").click()
        self.page.get_by_label("Image").fill(
            "https://media.themoviedb.org/t/p/w227_and_h127_bestv2/dyBB19jEpwj6gzGA1IcXxj9kq1e.jpg",
        )
        self.page.get_by_label("Episode number").click()
        self.page.get_by_label("Episode number").fill("2")
        self.page.get_by_role("button", name="Submit").click()
        expect(
            self.page.get_by_text("example S2E2 added successfully."),
        ).to_be_visible()

        # check the tv show details page
        self.page.get_by_role("link", name=" TV Shows").click()
        self.page.get_by_role("link", name="example").click()
        self.page.get_by_role("link", name="example S1").click()
        expect(self.page.get_by_text("S01.E01 - example Unknown air")).to_be_visible()
        expect(
            self.page.get_by_role("heading", name="S01.E02 - example"),
        ).to_be_visible()
        expect(self.page.get_by_text("S01.E02 - example Unknown air")).to_be_visible()
        expect(self.page.get_by_text("S01.E03 - example Unknown air")).to_be_visible()

        # check the seasons list page
        self.page.get_by_role("link", name=" Seasons").click()
        self.page.get_by_role("button", name="").click()
        self.page.get_by_label("Layout*").select_option("table")
        self.page.get_by_role("button", name="Filter").click()
        expect(
            self.page.get_by_role(
                "row",
                name="img example S1 8.0 Completed",
            ).get_by_role("button"),
        ).to_be_visible()
        expect(
            self.page.get_by_role(
                "row",
                name="img example S2 5.0 Completed",
            ).get_by_role("button"),
        ).to_be_visible()
        expect(self.page.get_by_role("cell", name="3", exact=True)).to_be_visible()
        expect(self.page.get_by_role("cell", name="2", exact=True)).to_be_visible()

        # remove episode watched from S1 and set status to in progress
        self.page.get_by_role("link", name="example S1").click()
        self.page.get_by_role("button", name="").nth(2).click()
        self.page.get_by_role("button", name="Remove Last Watch").click()
        self.page.get_by_role("button", name="").click()
        self.page.get_by_label("Status*").select_option("In progress")
        self.page.get_by_role("button", name="Save").click()

        # check the seasons list page
        self.page.get_by_role("link", name=" Seasons").click()
        expect(self.page.get_by_role("cell", name="2").first).to_be_visible()

        # set status to completed
        self.page.get_by_role("link", name="example S1").click()
        self.page.get_by_role("button", name="").click()
        self.page.get_by_label("Status*").select_option("Completed")
        self.page.get_by_role("button", name="Save").click()

        # check the seasons list if added completed all episodes
        self.page.get_by_role("link", name=" Seasons").click()
        expect(self.page.locator("td:nth-child(4)").first).to_be_visible()
        expect(self.page.get_by_role("cell", name="3", exact=True)).to_be_visible()

        # remove episode watched from S1 and S2 and check the seasons list
        self.page.locator("td:nth-child(4)").first.click()
        self.page.get_by_role("link", name="example S1").click()
        self.page.get_by_role("button", name="").nth(2).click()
        self.page.get_by_role("button", name="Remove Last Watch").click()
        self.page.get_by_role("link", name=" Seasons").click()
        self.page.get_by_role("link", name="example S2").click()
        self.page.get_by_role("button", name="").nth(1).click()
        self.page.get_by_role("button", name="Remove Last Watch").click()
        self.page.get_by_role("button", name="example S2").click()
        self.page.get_by_role("link", name="example S1").click()

        # set tv show to in progress and check the tv show list
        self.page.get_by_role("link", name=" TV Shows").click()
        expect(self.page.get_by_role("cell", name="3")).to_be_visible()
        self.page.get_by_role("row", name="img example 5.0 Completed 3 ").get_by_role(
            "button",
        ).click()
        self.page.get_by_role("row", name="img example 5.0 Completed 3 ").locator(
            "#id_status",
        ).select_option("In progress")
        self.page.get_by_role("button", name="Save").click()

        # set tv show to completed and check the tv show list
        self.page.get_by_role("row", name="img example 5.0 In progress 3").get_by_role(
            "button",
        ).click()
        self.page.get_by_role("row", name="img example 5.0 In progress 3").locator(
            "#id_status",
        ).select_option("Completed")
        self.page.get_by_role("button", name="Save").click()
        expect(self.page.get_by_role("cell", name="5", exact=True)).to_be_visible()
