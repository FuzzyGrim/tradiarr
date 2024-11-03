import json

from django.contrib import auth
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django_celery_results.models import TaskResult


class Profile(TestCase):
    """Test profile page."""

    def setUp(self):
        """Create user for the tests."""
        self.credentials = {"username": "test", "password": "12345"}
        self.user = get_user_model().objects.create_user(**self.credentials)
        self.client.login(**self.credentials)

    def test_change_username(self):
        """Test changing username."""
        self.assertEqual(auth.get_user(self.client).username, "test")
        self.client.post(
            reverse("profile"),
            {
                "username": "new_test",
            },
        )
        self.assertEqual(auth.get_user(self.client).username, "new_test")

    def test_change_password(self):
        """Test changing password."""
        self.assertEqual(auth.get_user(self.client).check_password("12345"), True)
        self.client.post(
            reverse("profile"),
            {
                "old_password": "12345",
                "new_password1": "*FNoZN64",
                "new_password2": "*FNoZN64",
            },
        )
        self.assertEqual(auth.get_user(self.client).check_password("*FNoZN64"), True)


    def test_invalid_password_change(self):
        """Test password change with incorrect old password."""
        response = self.client.post(
            reverse("profile"),
            {
                "old_password": "wrongpass",
                "new_password1": "newpass123",
                "new_password2": "newpass123",
            },
        )
        self.assertTrue(auth.get_user(self.client).check_password("12345"))
        self.assertContains(response, "Your old password was entered incorrectly")



class TaskViewTests(TestCase):
    """Test user task views."""

    def setUp(self):
        """Create user for the tests."""
        self.credentials = {"username": "test", "password": "12345"}
        self.user = get_user_model().objects.create_user(**self.credentials)
        self.client.login(**self.credentials)

    def test_task_status_handling(self):
        """Test if view correctly modifies the task results based on their status."""
        TaskResult.objects.create(
            task_args=json.dumps(["<SimpleLazyObject: <User: test>>"]),
            result=json.dumps({"exc_message": ["Error occurred"]}),
            task_id="1",
            status="FAILURE",
        )
        TaskResult.objects.create(
            task_args=json.dumps(["<SimpleLazyObject: <User: test>>"]),
            result=json.dumps({}),
            task_id="2",
            status="STARTED",
        )
        TaskResult.objects.create(
            task_args=json.dumps(["<SimpleLazyObject: <User: test>>"]),
            result=None,
            task_id="3",
            status="PENDING",
        )

        response = self.client.get(reverse("tasks"))
        tasks = response.context["tasks"]

        self.assertEqual(tasks[2].result, "Error occurred")
        self.assertEqual(tasks[1].result, "Task in progress")
        self.assertEqual(tasks[0].result, "Waiting for task to start")


class RegisterViewTests(TestCase):
    """Test registration functionality."""

    def test_successful_registration(self):
        """Test successful user registration."""
        response = self.client.post(
            reverse("register"),
            {
                "username": "newuser",
                "password1": "testpass123",
                "password2": "testpass123",
            },
        )
        self.assertRedirects(response, reverse("login"))
        self.assertTrue(get_user_model().objects.filter(username="newuser").exists())

    def test_invalid_registration(self):
        """Test registration with invalid data."""
        response = self.client.post(
            reverse("register"),
            {
                "username": "newuser",
                "password1": "test",  # Too short password
                "password2": "test",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username="newuser").exists())


class LoginViewTests(TestCase):
    """Test login functionality."""

    def setUp(self):
        """Create user for the tests."""
        self.credentials = {"username": "testuser", "password": "testpass123"}
        self.user = get_user_model().objects.create_user(**self.credentials)

    def test_successful_login(self):
        """Test successful login."""
        response = self.client.post(reverse("login"), self.credentials)
        self.assertRedirects(response, reverse("home"))
        self.assertTrue(auth.get_user(self.client).is_authenticated)

    def test_invalid_login(self):
        """Test login with invalid credentials."""
        response = self.client.post(
            reverse("login"),
            {
                "username": "testuser",
                "password": "wrongpass",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(auth.get_user(self.client).is_authenticated)


class DemoProfileTests(TestCase):
    """Extended profile tests."""

    def setUp(self):
        """Create user for the tests."""
        self.credentials = {"username": "testuser", "password": "testpass123"}
        self.user = get_user_model().objects.create_user(**self.credentials)
        self.client.login(**self.credentials)

    def test_demo_user_cannot_change_username(self):
        """Test that demo users cannot change their username."""
        self.user.is_demo = True
        self.user.save()

        response = self.client.post(
            reverse("profile"),
            {
                "username": "new_username",
            },
        )
        self.assertEqual(auth.get_user(self.client).username, "testuser")
        self.assertContains(response, "not allowed for the demo account")

    def test_demo_user_cannot_change_password(self):
        """Test that demo users cannot change their password."""
        self.user.is_demo = True
        self.user.save()

        response = self.client.post(
            reverse("profile"),
            {
                "old_password": "testpass123",
                "new_password1": "newpass123",
                "new_password2": "newpass123",
            },
        )
        self.assertTrue(auth.get_user(self.client).check_password("testpass123"))
        self.assertContains(response, "not allowed for the demo account")
