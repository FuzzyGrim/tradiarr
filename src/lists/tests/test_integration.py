import os

from django.contrib.auth import get_user_model
from django.contrib.staticfiles.testing import StaticLiveServerTestCase
from playwright.sync_api import expect, sync_playwright


class IntegrationTest(StaticLiveServerTestCase):
    """Integration tests for the application."""

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

    def test_blank_modal(self):
        """Test the register and login pages."""
        self.page.get_by_role("combobox").select_option("anime")
        self.page.get_by_placeholder("Search").click()
        self.page.get_by_placeholder("Search").fill("perfect blue")
        self.page.get_by_placeholder("Search").press("Enter")
        self.page.get_by_placeholder("Search").press("Enter")
        self.page.get_by_role("button", name="").click()
        self.page.get_by_role("link", name="Perfect Blue").click()
        self.page.get_by_role("button", name="").click()
        expect(self.page.get_by_text("No custom lists found.")).to_be_visible()

    def test_flow(self):
        """Test the flow of adding an item to a list and editing the list."""
        # create list
        self.page.goto(f"{self.live_server_url}/lists")
        self.page.get_by_role("button", name="Create List").click()
        self.page.get_by_label("Name*").click()
        self.page.get_by_label("Name*").fill("test")
        self.page.get_by_label("Name*").press("Tab")
        self.page.get_by_label("Description").fill("test description")
        self.page.get_by_role("button", name="Save").click()
        expect(self.page.get_by_text("test (0 items) test")).to_be_visible()

        # add item to list
        self.page.get_by_role("combobox").select_option("anime")
        self.page.get_by_placeholder("Search").click()
        self.page.get_by_placeholder("Search").fill("perfect blue")
        self.page.get_by_role("button", name="").click()
        self.page.get_by_role("link", name="Perfect Blue").click()
        self.page.get_by_role("button", name="").click()
        expect(self.page.get_by_role("button", name=" test")).to_be_visible()
        self.page.get_by_role("button", name=" test").click()
        self.page.get_by_label("Close").click()
        self.page.get_by_role("link", name=" Lists").click()
        expect(self.page.get_by_text("test (1 item) test description")).to_be_visible()

        # check item
        self.page.locator("a").filter(has_text="test").click()
        expect(self.page.get_by_role("link", name="Perfect Blue")).to_be_visible()
        expect(self.page.get_by_text("Last added 0 minutes ago")).to_be_visible()
        self.page.get_by_role("button", name="").click()
        expect(
            self.page.locator("#filter-modal div")
            .filter(has_text="Media type* All Movie TV Show")
            .nth(2),
        ).to_be_visible()
        # wait for the filter modal to load
        self.page.wait_for_timeout(100)
        self.page.locator("#filter-modal").press("Escape")
        self.page.get_by_role("button", name="Edit List").click()

        # edit list
        expect(
            self.page.locator("#edit-list div")
            .filter(has_text="Name* Description test")
            .nth(2),
        ).to_be_visible()
        self.page.get_by_label("Name*").click()
        self.page.get_by_label("Name*").fill("test rename")
        self.page.get_by_role("button", name="Save").click()
        expect(self.page.get_by_role("heading", name="test rename")).to_be_visible()
