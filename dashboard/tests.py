from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from .models import Notes, Homework, Todo

class ModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='teststudent', password='password123')

    def test_notes_model(self):
        note = Notes.objects.create(
            user=self.user,
            title='Physics Chapter 1',
            description='Mechanics and Newton laws summary'
        )
        self.assertEqual(str(note), 'Physics Chapter 1')
        self.assertEqual(note.user.username, 'teststudent')

    def test_homework_model(self):
        hw = Homework.objects.create(
            user=self.user,
            subject='Math',
            title='Algebra Exercises',
            description='Pages 45-50',
            is_finished=False
        )
        self.assertEqual(str(hw), 'Algebra Exercises')
        self.assertFalse(hw.is_finished)

    def test_todo_model(self):
        todo = Todo.objects.create(
            user=self.user,
            title='Complete lab report',
            is_finished=False
        )
        self.assertEqual(str(todo), 'Complete lab report')
        self.assertFalse(todo.is_finished)

class ViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='teststudent', password='password123')

    def test_public_pages(self):
        # Home page
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)

        # About page
        response = self.client.get(reverse('about'))
        self.assertEqual(response.status_code, 200)

        # Login page
        response = self.client.get(reverse('login'))
        self.assertEqual(response.status_code, 200)

        # Register page
        response = self.client.get(reverse('register'))
        self.assertEqual(response.status_code, 200)

    def test_login_required_redirects(self):
        # Unauthenticated access to notes should redirect to login
        response = self.client.get(reverse('notes'))
        self.assertEqual(response.status_code, 302)

        # Unauthenticated access to homework should redirect to login
        response = self.client.get(reverse('homework'))
        self.assertEqual(response.status_code, 302)

        # Unauthenticated access to todo should redirect to login
        response = self.client.get(reverse('todo'))
        self.assertEqual(response.status_code, 302)
