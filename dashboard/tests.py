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

    def test_notes_creation_and_subject_choices(self):
        from .models import SUBJECT_CHOICES
        expected_subjects = ['Java', 'PHP', 'Python', 'ADBMS', 'Spring', 'C', 'C++', 'ML', 'Docker', 'Other']
        choice_keys = [c[0] for c in SUBJECT_CHOICES]
        for subj in expected_subjects:
            self.assertIn(subj, choice_keys)

        self.client.login(username='teststudent', password='password123')
        
        # Test creating note via POST with subject
        response = self.client.post(reverse('notes'), {
            'subject': 'Python',
            'title': 'Python OOP Concepts',
            'description': 'Classes, inheritance, and polymorphism'
        })
        self.assertEqual(response.status_code, 302)
        
        # Verify note saved
        note = Notes.objects.filter(title='Python OOP Concepts').first()
        self.assertIsNotNone(note)
        self.assertEqual(note.subject, 'Python')
        self.assertEqual(note.user, self.user)

        # Verify note appears on notes page
        page_res = self.client.get(reverse('notes'))
        self.assertContains(page_res, 'Python OOP Concepts')
        self.assertContains(page_res, 'Python')

        # Verify note detail page
        detail_res = self.client.get(reverse('notes-detail', args=[note.id]))
        self.assertContains(detail_res, 'Python OOP Concepts')
        self.assertContains(detail_res, 'Python')

    def test_homework_creation_and_subject_choices(self):
        self.client.login(username='teststudent', password='password123')
        
        # Homework form should have subject choices
        res = self.client.get(reverse('homework'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, '<select name="subject"')
        self.assertContains(res, 'Python')
        self.assertContains(res, 'Docker')

        # Test creating homework via POST with subject
        response = self.client.post(reverse('homework'), {
            'subject': 'Docker',
            'title': 'Containerization Assignment',
            'description': 'Create a Dockerfile and docker-compose.yml',
            'due': '2026-10-15',
            'is_finished': False
        })
        self.assertEqual(response.status_code, 200)
        
        hw = Homework.objects.filter(title='Containerization Assignment').first()
        self.assertIsNotNone(hw)
        self.assertEqual(hw.subject, 'Docker')
