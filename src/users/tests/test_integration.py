import os

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
        cls.browser = cls.playwright.chromium.launch()

    @classmethod
    def tearDownClass(cls):
        """Tear down the test class."""
        super().tearDownClass()
        cls.browser.close()
        cls.playwright.stop()

    def test_register_login(self):
        """Test the register and login pages."""
        page = self.browser.new_page()
        page.goto(f"{self.live_server_url}/")

        # Register
        page.get_by_role("link", name="Register Now").click()
        page.get_by_label("Username*").fill("TEST")
        page.get_by_label("Username*").press("Tab")
        page.get_by_label("Password*").fill(
            "12341234",
        )
        page.get_by_label("Password*").press("Tab")
        page.get_by_label("Password confirmation*").fill(
            "12341234",
        )
        page.get_by_role("button", name="Sign Up").click()
        expect(
            page.get_by_text("Your account has been created, you can now log in!"),
        ).to_be_visible()

        # Login
        page.get_by_label("Username*").click()
        page.get_by_label("Username*").fill("TEST")
        page.get_by_label("Password*").click()
        page.get_by_label("Password*").fill(
            "12341234",
        )
        page.get_by_role("button", name="Log In").click()
        expect(
            page.get_by_role("heading", name="You don't have any media in"),
        ).to_be_visible()

        page.close()
