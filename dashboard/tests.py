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


class ConsoleTests(TestCase):
    PASSWORD = 'Console-pass-123'

    def setUp(self):
        from datetime import timedelta
        from django.core.cache import cache
        from django.utils import timezone
        cache.clear()
        self.admin = User.objects.create_user('boss', 'boss@example.com', self.PASSWORD, is_staff=True)
        self.asha = User.objects.create_user('asha', 'asha@example.com', 'Student-pass-123')
        self.ben = User.objects.create_user('ben', 'ben@example.com', 'Student-pass-123', is_active=False)
        Notes.objects.create(user=self.asha, subject='Python', title='Secret diary entry', description='private words')
        Homework.objects.create(user=self.asha, subject='Java', title='Confidential essay', due=timezone.now() + timedelta(days=2), is_finished=True)
        Homework.objects.create(user=self.asha, subject='Java', title='Another one', due=timezone.now() + timedelta(days=3))
        Todo.objects.create(user=self.asha, title='Hidden errand', is_finished=False)

    def signin(self, client=None, **extra):
        client = client or self.client
        return client.post('/console/login/', {'username': 'boss', 'password': self.PASSWORD, **extra})

    # ---- access ----
    def test_old_admin_is_gone(self):
        self.assertEqual(self.client.get('/admin/').status_code, 404)

    def test_pages_require_sign_in(self):
        for url in ('/console/', '/console/users/', f'/console/users/{self.asha.pk}/', '/console/security/'):
            res = self.client.get(url)
            self.assertEqual(res.status_code, 302, url)
            self.assertIn('/console/login/', res['Location'])

    def test_students_cannot_sign_in(self):
        res = self.client.post('/console/login/', {'username': 'asha', 'password': 'Student-pass-123'})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'not allowed in the console')
        self.assertNotIn('sd_rt', res.cookies)

    def test_sign_in_sets_httponly_cookies_scoped_to_console(self):
        from .models import AdminSession
        res = self.signin()
        self.assertEqual(res.status_code, 302)
        for name in ('sd_at', 'sd_rt'):
            self.assertTrue(res.cookies[name]['httponly'])
            self.assertEqual(res.cookies[name]['path'], '/console/')
        self.assertEqual(AdminSession.objects.filter(user=self.admin, revoked_at__isnull=True).count(), 1)
        self.assertEqual(self.client.get('/console/').status_code, 200)

    def test_sign_in_with_email_and_safe_next(self):
        res = self.client.post('/console/login/', {'username': 'BOSS@example.com', 'password': self.PASSWORD, 'next': '/console/users/'})
        self.assertEqual(res['Location'], '/console/users/')
        self.client.cookies.clear()
        res = self.client.post('/console/login/', {'username': 'boss', 'password': self.PASSWORD, 'next': 'https://evil.example/'})
        self.assertEqual(res['Location'], '/console/')

    def test_brute_force_lockout(self):
        for _ in range(5):
            res = self.client.post('/console/login/', {'username': 'boss', 'password': 'nope'})
            self.assertEqual(res.status_code, 200)
        locked = self.client.post('/console/login/', {'username': 'boss', 'password': self.PASSWORD})
        self.assertEqual(locked.status_code, 429)
        self.assertNotIn('sd_rt', locked.cookies)

    # ---- token refresh ----
    def test_expired_access_token_is_refreshed_without_signing_out(self):
        from .models import AdminSession
        self.signin()
        del self.client.cookies['sd_at']             # the 15 minute access token ran out
        res = self.client.get('/console/users/')
        self.assertEqual(res.status_code, 200)       # still signed in
        self.assertIn('sd_at', res.cookies)          # new pair issued
        self.assertIn('sd_rt', res.cookies)
        rows = AdminSession.objects.filter(user=self.admin).order_by('id')
        self.assertEqual(rows.count(), 2)
        self.assertIsNotNone(rows[0].revoked_at)     # old refresh token rotated out
        self.assertEqual(rows[0].replaced_by, rows[1].jti)
        self.assertIsNone(rows[1].revoked_at)
        self.assertEqual(self.client.get('/console/').status_code, 200)

    def test_parallel_request_with_just_rotated_token_is_tolerated(self):
        self.signin()
        old_refresh = self.client.cookies['sd_rt'].value
        del self.client.cookies['sd_at']
        self.assertEqual(self.client.get('/console/').status_code, 200)           # rotates
        other = Client()
        other.cookies['sd_rt'] = old_refresh                                       # raced request, same old token
        res = other.get('/console/')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn('sd_rt', res.cookies)

    def test_replayed_refresh_token_revokes_every_session(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import AdminSession
        self.signin()
        stolen = self.client.cookies['sd_rt'].value
        del self.client.cookies['sd_at']
        self.client.get('/console/')                                               # legitimate rotation
        AdminSession.objects.filter(replaced_by__gt='').update(revoked_at=timezone.now() - timedelta(minutes=5))
        thief = Client()
        thief.cookies['sd_rt'] = stolen
        res = thief.get('/console/')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(AdminSession.objects.filter(user=self.admin, revoked_at__isnull=True).count(), 0)
        del self.client.cookies['sd_at']
        self.assertEqual(self.client.get('/console/').status_code, 302)           # the real owner must sign in again

    def test_session_is_capped_by_absolute_lifetime(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import AdminSession
        self.signin()
        AdminSession.objects.update(origin_at=timezone.now() - timedelta(days=31))
        del self.client.cookies['sd_at']
        self.assertEqual(self.client.get('/console/').status_code, 302)

    def test_disabled_staff_cannot_refresh(self):
        self.signin()
        User.objects.filter(pk=self.admin.pk).update(is_active=False)
        from django.core.cache import cache
        cache.clear()
        del self.client.cookies['sd_at']
        self.assertEqual(self.client.get('/console/').status_code, 302)

    def test_sign_out_revokes_the_session(self):
        from .models import AdminSession
        self.signin()
        old_refresh = self.client.cookies['sd_rt'].value
        res = self.client.post('/console/logout/')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(AdminSession.objects.filter(revoked_at__isnull=True).count(), 0)
        other = Client()
        other.cookies['sd_rt'] = old_refresh
        self.assertEqual(other.get('/console/').status_code, 302)

    def test_console_and_student_site_sessions_are_independent(self):
        self.signin()
        self.client.get('/login/')                  # visiting the student login must not end the console session
        self.assertEqual(self.client.get('/console/').status_code, 200)
        student = Client()
        student.login(username='asha', password='Student-pass-123')
        self.assertEqual(student.get('/console/').status_code, 302)

    # ---- what the console shows ----
    def test_overview_numbers_and_no_content(self):
        self.signin()
        res = self.client.get('/console/')
        self.assertContains(res, 'Total users')
        self.assertEqual(res.context['totals']['total'], 2)       # staff are not counted as users
        self.assertEqual(res.context['totals']['inactive'], 1)
        self.assertEqual(res.context['content']['notes'], 1)
        self.assertEqual(res.context['content']['homework']['total'], 2)
        for secret in ('Secret diary entry', 'private words', 'Confidential essay', 'Hidden errand'):
            self.assertNotContains(res, secret)

    def test_users_list_shows_account_facts_only(self):
        self.signin()
        res = self.client.get('/console/users/')
        self.assertContains(res, 'asha@example.com')
        self.assertContains(res, 'ben@example.com')
        self.assertNotContains(res, 'boss@example.com')            # admins are not listed
        self.assertContains(res, 'Active')
        self.assertContains(res, 'Inactive')
        for banned in ('Admin</span>', 'Staff</span>', 'Student</span>', 'Secret diary entry', 'Hidden errand'):
            self.assertNotContains(res, banned)

    def test_users_search_filter_sort_and_pagination(self):
        for i in range(20):
            User.objects.create_user(f'kid{i:02d}', f'kid{i:02d}@example.com', 'Student-pass-123')
        self.signin()
        self.assertContains(self.client.get('/console/users/?q=asha'), 'asha@example.com')
        self.assertNotContains(self.client.get('/console/users/?q=asha'), 'ben@example.com')
        inactive = self.client.get('/console/users/?status=inactive')
        self.assertContains(inactive, 'ben@example.com')
        self.assertNotContains(inactive, 'asha@example.com')
        self.assertEqual(self.client.get('/console/users/?joined=7').context['total'], 22)
        page2 = self.client.get('/console/users/?page=2&sort=name')
        self.assertEqual(page2.status_code, 200)
        self.assertEqual(page2.context['page'].number, 2)
        self.assertEqual(self.client.get('/console/users/?sort=<script>').status_code, 200)

    def test_user_detail_has_counts_but_no_content_or_controls(self):
        self.signin()
        res = self.client.get(f'/console/users/{self.asha.pk}/')
        self.assertContains(res, 'asha@example.com')
        self.assertEqual(res.context['person'].n_notes, 1)
        self.assertEqual(res.context['person'].n_homework, 2)
        self.assertEqual(res.context['person'].n_homework_done, 1)
        self.assertEqual(res.context['person'].n_todos, 1)
        self.assertEqual(res.context['completion'], 33)
        for secret in ('Secret diary entry', 'private words', 'Confidential essay', 'Another one', 'Hidden errand'):
            self.assertNotContains(res, secret)
        html = res.content.decode()
        self.assertEqual(html.count('method="post"'), 1)      # only the sidebar sign-out button
        self.assertIn('/console/logout/', html)
        self.assertNotIn('Delete', html)
        self.assertNotIn('name="is_active"', html)

    def test_staff_accounts_are_not_viewable_as_users(self):
        self.signin()
        self.assertEqual(self.client.get(f'/console/users/{self.admin.pk}/').status_code, 404)

    def test_console_is_read_only(self):
        self.signin()
        before = (User.objects.count(), Notes.objects.count())
        for url in ('/console/', '/console/users/', f'/console/users/{self.asha.pk}/'):
            self.assertEqual(self.client.post(url, {'delete': '1'}).status_code, 405, url)
            self.assertEqual(self.client.delete(url).status_code, 405, url)
        self.assertEqual(before, (User.objects.count(), Notes.objects.count()))
        self.assertTrue(User.objects.get(pk=self.asha.pk).is_active)

    def test_security_page_lists_and_revokes_sessions(self):
        from .models import AdminSession
        self.signin()
        second = Client()
        self.signin(second)
        res = self.client.get('/console/security/')
        self.assertContains(res, 'This device')
        self.assertEqual(len(res.context['sessions']), 2)
        self.client.post('/console/security/', {'action': 'revoke_others'})
        self.assertEqual(AdminSession.objects.filter(user=self.admin, revoked_at__isnull=True).count(), 1)
        del second.cookies['sd_at']
        self.assertEqual(second.get('/console/').status_code, 302)
        self.assertEqual(self.client.get('/console/').status_code, 200)

    def test_responses_are_not_cached(self):
        self.signin()
        res = self.client.get('/console/')
        self.assertIn('no-store', res['Cache-Control'])
        self.assertIn('noindex', res['X-Robots-Tag'])
