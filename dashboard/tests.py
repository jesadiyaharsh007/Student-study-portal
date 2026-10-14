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
        # (the page shell renders instantly; the list arrives from the data region endpoint)
        page_res = self.client.get(reverse('notes') + '?_part=1')
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
        self.assertEqual(response.status_code, 302)
        
        hw = Homework.objects.filter(title='Containerization Assignment').first()
        self.assertIsNotNone(hw)
        self.assertEqual(hw.subject, 'Docker')

    def test_chatbot_page_and_system_prompt(self):
        # Must redirect unauthenticated users
        res_anon = self.client.get(reverse('chatbot'))
        self.assertEqual(res_anon.status_code, 302)

        # Authenticated access
        self.client.login(username='teststudent', password='password123')
        res = self.client.get(reverse('chatbot'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Lexi')
        self.assertContains(res, 'composer-send')
        self.assertContains(res, 'arrow-up')

        # Clear chat history via post
        res_clear = self.client.post(reverse('chatbot'), {'clear': '1'})
        self.assertEqual(res_clear.status_code, 302)

        # Verify system prompt has security guardrails, identity rules, and multi-line rules
        from .views import AI_TUTOR_SYSTEM_PROMPT
        self.assertIn("You are Lexi", AI_TUTOR_SYSTEM_PROMPT)
        self.assertIn("Your name is Lexi", AI_TUTOR_SYSTEM_PROMPT)
        self.assertIn("STRICT SECURITY & PRIVACY GUARDRAILS", AI_TUTOR_SYSTEM_PROMPT)
        self.assertIn("CONFIDENTIAL PLATFORM CODE", AI_TUTOR_SYSTEM_PROMPT)
        self.assertIn("FORMATTING RULES", AI_TUTOR_SYSTEM_PROMPT)
        self.assertIn("fenced code block", AI_TUTOR_SYSTEM_PROMPT)

    def test_data_pages_render_shell_first_then_data(self):
        from .models import Todo
        self.client.login(username='teststudent', password='password123')
        Todo.objects.create(user=self.user, title='Read chapter nine')
        for name in ('notes', 'homework', 'todo', 'profile'):
            shell = self.client.get(reverse(name))
            self.assertEqual(shell.status_code, 200)
            self.assertContains(shell, 'data-async')
            self.assertContains(shell, 'async-skel')
            self.assertNotContains(shell, 'Read chapter nine')
            part = self.client.get(reverse(name) + '?_part=1')
            self.assertEqual(part.status_code, 200)
            self.assertNotContains(part, '<html')
            self.assertEqual(part['Cache-Control'], 'private, no-store')
        self.assertContains(self.client.get(reverse('todo') + '?_part=1'), 'Read chapter nine')

    def test_data_region_requires_login(self):
        res = self.client.get(reverse('todo') + '?_part=1')
        self.assertEqual(res.status_code, 302)


class AdminPanelTests(TestCase):
    def setUp(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import Homework, Notes, Todo
        self.admin = User.objects.create_superuser('boss', 'boss@example.com', 'Admin-pass-123')
        self.student = User.objects.create_user('stu', 'stu@example.com', 'Student-pass-123')
        self.note = Notes.objects.create(user=self.student, subject='Python', title='=cmd|calc', description='a b c')
        self.hw_late = Homework.objects.create(user=self.student, subject='Java', title='Late', due=timezone.now() - timedelta(days=2))
        self.hw_ok = Homework.objects.create(user=self.student, subject='Java', title='Later', due=timezone.now() + timedelta(days=3))
        self.todo = Todo.objects.create(user=self.student, title='Do it')

    def test_students_cannot_open_admin(self):
        self.client.login(username='stu', password='Student-pass-123')
        res = self.client.get('/admin/')
        self.assertEqual(res.status_code, 302)
        self.assertIn('/admin/login/', res['Location'])

    def test_overview_shows_live_numbers(self):
        self.client.login(username='boss', password='Admin-pass-123')
        res = self.client.get('/admin/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Overview')
        self.assertContains(res, 'sd-stat')
        self.assertEqual(res.context['ov_users']['total'], 2)
        self.assertEqual(res.context['ov_notes'], 1)
        self.assertEqual(res.context['ov_hw']['overdue'], 1)
        self.assertEqual(res.context['ov_hw']['open'], 2)
        self.assertEqual(res.context['ov_todo']['open'], 1)

    def test_every_changelist_and_form_renders(self):
        self.client.login(username='boss', password='Admin-pass-123')
        for url in ('/admin/auth/user/', '/admin/dashboard/notes/', '/admin/dashboard/homework/', '/admin/dashboard/todo/',
                    '/admin/dashboard/homework/?deadline=overdue', '/admin/dashboard/homework/?deadline=week',
                    '/admin/dashboard/notes/?q=cmd', f'/admin/dashboard/notes/{self.note.pk}/change/',
                    f'/admin/dashboard/homework/{self.hw_ok.pk}/change/', '/admin/auth/user/add/',
                    f'/admin/auth/user/{self.student.pk}/change/'):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_deadline_filter(self):
        self.client.login(username='boss', password='Admin-pass-123')
        res = self.client.get('/admin/dashboard/homework/?deadline=overdue')
        self.assertContains(res, 'Late')
        self.assertNotContains(res, 'Later')

    def test_mark_done_action(self):
        from .models import Homework
        self.client.login(username='boss', password='Admin-pass-123')
        self.client.post('/admin/dashboard/homework/', {
            'action': 'mark_done', '_selected_action': [self.hw_late.pk, self.hw_ok.pk],
        })
        self.assertEqual(Homework.objects.filter(is_finished=True).count(), 2)

    def test_csv_export_neutralises_formulas(self):
        self.client.login(username='boss', password='Admin-pass-123')
        res = self.client.post('/admin/dashboard/notes/', {'action': 'csv_export_action', '_selected_action': [self.note.pk]})
        if res.status_code != 200 or 'text/csv' not in res.get('Content-Type', ''):
            # action name is generated by the factory; find it from the changelist instead
            page = self.client.get('/admin/dashboard/notes/')
            name = [a for a in page.context['action_form'].fields['action'].choices if 'CSV' in a[1]][0][0]
            res = self.client.post('/admin/dashboard/notes/', {'action': name, '_selected_action': [self.note.pk]})
        self.assertIn('text/csv', res['Content-Type'])
        body = res.content.decode('utf-8')
        self.assertIn("'=cmd|calc", body)
        self.assertNotIn(',=cmd|calc', body)

    def test_cannot_disable_own_account(self):
        self.client.login(username='boss', password='Admin-pass-123')
        self.client.post('/admin/auth/user/', {'action': 'deactivate', '_selected_action': [self.admin.pk, self.student.pk]})
        self.admin.refresh_from_db(); self.student.refresh_from_db()
        self.assertTrue(self.admin.is_active)
        self.assertFalse(self.student.is_active)

    def test_login_page_uses_site_layout(self):
        res = self.client.get('/admin/login/')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'id="login-form"')
        self.assertContains(res, 'auth-form')
        self.assertContains(res, 'data-buddies')
        self.assertContains(res, 'Manage students')
        bad = self.client.post('/admin/login/', {'username': 'boss', 'password': 'wrong'})
        self.assertEqual(bad.status_code, 200)
        self.assertContains(bad, 'form-alert')
        ok = self.client.post('/admin/login/?next=/admin/', {'username': 'boss', 'password': 'Admin-pass-123', 'next': '/admin/'})
        self.assertEqual(ok.status_code, 302)

    def test_shell_has_nav_palette_and_guidance(self):
        self.client.login(username='boss', password='Admin-pass-123')
        res = self.client.get('/admin/')
        self.assertContains(res, 'nav-pill')
        self.assertContains(res, 'id="palette"')
        self.assertContains(res, 'Needs your attention')
        self.assertContains(res, 'Quick actions')
        self.assertContains(res, 'How this admin works')
        self.assertEqual([a['text'] for a in res.context['ov_attention']][:1], ['homework overdue'])
        hw = self.client.get('/admin/dashboard/homework/')
        self.assertContains(hw, 'sd-hint')
        self.assertContains(hw, 'Filter by deadline')

    def test_messages_become_toasts(self):
        self.client.login(username='boss', password='Admin-pass-123')
        res = self.client.post('/admin/dashboard/homework/', {'action': 'mark_done', '_selected_action': [self.hw_late.pk]}, follow=True)
        self.assertContains(res, 'class="toast success"')

    def test_admin_is_narrowed_to_what_is_needed(self):
        self.client.login(username='boss', password='Admin-pass-123')
        # students create content on the site, so the admin has no "Add" for it
        for url in ('/admin/dashboard/notes/add/', '/admin/dashboard/homework/add/', '/admin/dashboard/todo/add/'):
            self.assertEqual(self.client.get(url).status_code, 403, url)
        # no groups, no permission pickers, no duplicate save buttons
        self.assertEqual(self.client.get('/admin/auth/group/').status_code, 404)
        form = self.client.get(f'/admin/auth/user/{self.student.pk}/change/')
        self.assertNotContains(form, 'user_permissions')
        self.assertNotContains(form, 'groups')
        self.assertContains(form, 'name="_save"')
        # overview no longer repeats the full app list
        self.assertNotContains(self.client.get('/admin/'), 'All data')
        # filters use readable names instead of raw field lookups
        self.assertEqual(self.client.get('/admin/dashboard/homework/?state=open').status_code, 200)
        self.assertEqual(self.client.get('/admin/auth/user/?account=disabled').status_code, 200)
        self.assertEqual(self.client.get('/admin/auth/user/?role=staff').status_code, 200)
