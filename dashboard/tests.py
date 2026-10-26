from unittest import mock

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
        from .lexi import SYSTEM_PROMPT as AI_TUTOR_SYSTEM_PROMPT
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
        return client.post('/admin/login/', {'username': 'boss', 'password': self.PASSWORD, **extra})

    # ---- access ----
    def test_student_site_does_not_advertise_the_admin(self):
        for url in ('/login/', '/register/', '/'):
            self.assertNotContains(self.client.get(url), '/admin/')
        self.client.login(username='asha', password='Student-pass-123')
        self.assertNotContains(self.client.get('/profile/'), '/admin/')
        # staff are told nothing about where to sign in either
        res = Client().post('/login/', {'username': 'boss', 'password': self.PASSWORD})
        self.assertNotContains(res, '/admin/')

    def test_django_admin_is_not_installed(self):
        from django.apps import apps
        self.assertFalse(apps.is_installed('django.contrib.admin'))

    def test_pages_require_sign_in(self):
        for url in ('/admin/', '/admin/users/', f'/admin/users/{self.asha.pk}/', '/admin/security/'):
            res = self.client.get(url)
            self.assertEqual(res.status_code, 302, url)
            self.assertIn('/admin/login/', res['Location'])

    def test_students_cannot_sign_in(self):
        res = self.client.post('/admin/login/', {'username': 'asha', 'password': 'Student-pass-123'})
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'not allowed in the console')
        self.assertNotIn('sd_rt', res.cookies)

    def test_sign_in_sets_httponly_cookies_scoped_to_console(self):
        from .models import AdminSession
        res = self.signin()
        self.assertEqual(res.status_code, 302)
        for name in ('sd_at', 'sd_rt'):
            self.assertTrue(res.cookies[name]['httponly'])
            self.assertEqual(res.cookies[name]['path'], '/admin/')
        self.assertEqual(AdminSession.objects.filter(user=self.admin, revoked_at__isnull=True).count(), 1)
        self.assertEqual(self.client.get('/admin/').status_code, 200)

    def test_sign_in_with_email_and_safe_next(self):
        res = self.client.post('/admin/login/', {'username': 'BOSS@example.com', 'password': self.PASSWORD, 'next': '/admin/users/'})
        self.assertEqual(res['Location'], '/admin/users/')
        self.client.cookies.clear()
        res = self.client.post('/admin/login/', {'username': 'boss', 'password': self.PASSWORD, 'next': 'https://evil.example/'})
        self.assertEqual(res['Location'], '/admin/')

    def test_brute_force_lockout(self):
        for _ in range(5):
            res = self.client.post('/admin/login/', {'username': 'boss', 'password': 'nope'})
            self.assertEqual(res.status_code, 200)
        locked = self.client.post('/admin/login/', {'username': 'boss', 'password': self.PASSWORD})
        self.assertEqual(locked.status_code, 429)
        self.assertNotIn('sd_rt', locked.cookies)

    # ---- token refresh ----
    def test_expired_access_token_is_refreshed_without_signing_out(self):
        from .models import AdminSession
        self.signin()
        del self.client.cookies['sd_at']             # the 15 minute access token ran out
        res = self.client.get('/admin/users/')
        self.assertEqual(res.status_code, 200)       # still signed in
        self.assertIn('sd_at', res.cookies)          # new pair issued
        self.assertIn('sd_rt', res.cookies)
        rows = AdminSession.objects.filter(user=self.admin).order_by('id')
        self.assertEqual(rows.count(), 2)
        self.assertIsNotNone(rows[0].revoked_at)     # old refresh token rotated out
        self.assertEqual(rows[0].replaced_by, rows[1].jti)
        self.assertIsNone(rows[1].revoked_at)
        self.assertEqual(self.client.get('/admin/').status_code, 200)

    def test_parallel_request_with_just_rotated_token_is_tolerated(self):
        self.signin()
        old_refresh = self.client.cookies['sd_rt'].value
        del self.client.cookies['sd_at']
        self.assertEqual(self.client.get('/admin/').status_code, 200)           # rotates
        other = Client()
        other.cookies['sd_rt'] = old_refresh                                       # raced request, same old token
        res = other.get('/admin/')
        self.assertEqual(res.status_code, 200)
        self.assertNotIn('sd_rt', res.cookies)

    def test_replayed_refresh_token_revokes_every_session(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import AdminSession
        self.signin()
        stolen = self.client.cookies['sd_rt'].value
        del self.client.cookies['sd_at']
        self.client.get('/admin/')                                               # legitimate rotation
        AdminSession.objects.filter(replaced_by__gt='').update(revoked_at=timezone.now() - timedelta(minutes=5))
        thief = Client()
        thief.cookies['sd_rt'] = stolen
        res = thief.get('/admin/')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(AdminSession.objects.filter(user=self.admin, revoked_at__isnull=True).count(), 0)
        del self.client.cookies['sd_at']
        self.assertEqual(self.client.get('/admin/').status_code, 302)           # the real owner must sign in again

    def test_session_is_capped_by_absolute_lifetime(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import AdminSession
        self.signin()
        AdminSession.objects.update(origin_at=timezone.now() - timedelta(days=31))
        del self.client.cookies['sd_at']
        self.assertEqual(self.client.get('/admin/').status_code, 302)

    def test_disabled_staff_cannot_refresh(self):
        self.signin()
        User.objects.filter(pk=self.admin.pk).update(is_active=False)
        from django.core.cache import cache
        cache.clear()
        del self.client.cookies['sd_at']
        self.assertEqual(self.client.get('/admin/').status_code, 302)

    def test_sign_out_revokes_the_session(self):
        from .models import AdminSession
        self.signin()
        old_refresh = self.client.cookies['sd_rt'].value
        res = self.client.post('/admin/logout/')
        self.assertEqual(res.status_code, 302)
        self.assertEqual(AdminSession.objects.filter(revoked_at__isnull=True).count(), 0)
        other = Client()
        other.cookies['sd_rt'] = old_refresh
        self.assertEqual(other.get('/admin/').status_code, 302)

    def test_console_and_student_site_sessions_are_independent(self):
        self.signin()
        self.client.get('/login/')                  # visiting the student login must not end the console session
        self.assertEqual(self.client.get('/admin/').status_code, 200)
        student = Client()
        student.login(username='asha', password='Student-pass-123')
        self.assertEqual(student.get('/admin/').status_code, 302)

    # ---- what the console shows ----
    def test_overview_numbers_and_no_content(self):
        self.signin()
        res = self.client.get('/admin/')
        self.assertContains(res, 'Total users')
        self.assertEqual(res.context['totals']['total'], 2)       # staff are not counted as users
        self.assertEqual(res.context['totals']['inactive'], 1)
        self.assertEqual(res.context['content']['notes'], 1)
        self.assertEqual(res.context['content']['homework']['total'], 2)
        for secret in ('Secret diary entry', 'private words', 'Confidential essay', 'Hidden errand'):
            self.assertNotContains(res, secret)

    def test_users_list_shows_account_facts_only(self):
        self.signin()
        res = self.client.get('/admin/users/')
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
        self.assertContains(self.client.get('/admin/users/?q=asha'), 'asha@example.com')
        self.assertNotContains(self.client.get('/admin/users/?q=asha'), 'ben@example.com')
        inactive = self.client.get('/admin/users/?status=inactive')
        self.assertContains(inactive, 'ben@example.com')
        self.assertNotContains(inactive, 'asha@example.com')
        self.assertEqual(self.client.get('/admin/users/?joined=7').context['total'], 22)
        page2 = self.client.get('/admin/users/?page=2&sort=name')
        self.assertEqual(page2.status_code, 200)
        self.assertEqual(page2.context['page'].number, 2)
        self.assertEqual(self.client.get('/admin/users/?sort=<script>').status_code, 200)

    def test_user_detail_has_counts_but_no_content_or_controls(self):
        self.signin()
        res = self.client.get(f'/admin/users/{self.asha.pk}/')
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
        self.assertIn('/admin/logout/', html)
        self.assertNotIn('Delete', html)
        self.assertNotIn('name="is_active"', html)

    def test_staff_accounts_are_not_viewable_as_users(self):
        self.signin()
        self.assertEqual(self.client.get(f'/admin/users/{self.admin.pk}/').status_code, 404)

    def test_console_is_read_only(self):
        self.signin()
        before = (User.objects.count(), Notes.objects.count())
        for url in ('/admin/', '/admin/users/', f'/admin/users/{self.asha.pk}/'):
            self.assertEqual(self.client.post(url, {'delete': '1'}).status_code, 405, url)
            self.assertEqual(self.client.delete(url).status_code, 405, url)
        self.assertEqual(before, (User.objects.count(), Notes.objects.count()))
        self.assertTrue(User.objects.get(pk=self.asha.pk).is_active)

    def test_security_page_lists_and_revokes_sessions(self):
        from .models import AdminSession
        self.signin()
        second = Client()
        self.signin(second)
        res = self.client.get('/admin/security/')
        self.assertContains(res, 'This device')
        self.assertEqual(len(res.context['sessions']), 2)
        self.client.post('/admin/security/', {'action': 'revoke_others'})
        self.assertEqual(AdminSession.objects.filter(user=self.admin, revoked_at__isnull=True).count(), 1)
        del second.cookies['sd_at']
        self.assertEqual(second.get('/admin/').status_code, 302)
        self.assertEqual(self.client.get('/admin/').status_code, 200)

    def test_responses_are_not_cached(self):
        self.signin()
        res = self.client.get('/admin/')
        self.assertIn('no-store', res['Cache-Control'])
        self.assertIn('noindex', res['X-Robots-Tag'])

    def test_missing_console_table_is_created_on_first_sign_in(self):
        from unittest import mock
        from django.db import DatabaseError
        from .console import tokens
        real = tokens.start_session
        calls = {'n': 0}

        def flaky(request, user, origin=None):
            calls['n'] += 1
            if calls['n'] == 1:
                raise DatabaseError('no such table: dashboard_adminsession')
            return real(request, user, origin)

        with mock.patch.object(tokens, 'start_session', side_effect=flaky),                 mock.patch.object(tokens, 'ensure_schema', return_value=True) as heal:
            res = self.signin()
        self.assertEqual(res.status_code, 302)
        self.assertEqual(calls['n'], 2)
        heal.assert_called_once()
        self.assertEqual(self.client.get('/admin/').status_code, 200)

    def test_sign_in_reports_a_friendly_error_if_the_table_cannot_be_created(self):
        from unittest import mock
        from django.db import DatabaseError
        from .console import tokens
        with mock.patch.object(tokens, 'start_session', side_effect=DatabaseError('boom')),                 mock.patch.object(tokens, 'ensure_schema', return_value=False):
            res = self.signin()
        self.assertEqual(res.status_code, 503)
        self.assertContains(res, 'could not set up', status_code=503)
        self.assertNotContains(res, 'migrate', status_code=503)



SAMPLE_BOOK = """The Project Gutenberg eBook of Tiny Tale

Title: Tiny Tale
Author: Doe, Jane, 1850-1920

*** START OF THE PROJECT GUTENBERG EBOOK TINY TALE ***

CONTENTS

CHAPTER I.
The Beginning

It was a bright cold day in April, and the clocks were striking
thirteen. She walked _slowly_ home & thought of tea <and> toast.
""" + ("A long paragraph of story text that goes on and on. " * 12 + "\n\n") * 3 + """
CHAPTER II.
The Middle

""" + ("More story text for the second chapter lives right here. " * 12 + "\n\n") * 3 + """
CHAPTER III.
The End

Roses are red,
Violets are blue,
Sugar is sweet,
And so are you.

""" + ("The very last part of the story, told at length. " * 12 + "\n\n") * 2 + """
*** END OF THE PROJECT GUTENBERG EBOOK TINY TALE ***

License text that must never reach the reader.
"""


class LibraryTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('reader', 'reader@example.com', 'Reader-pass-123')
        self.client.login(username='reader', password='Reader-pass-123')

    # ---- parser ----
    def test_parser_splits_chapters_and_strips_boilerplate(self):
        from .library import parse_gutenberg
        book = parse_gutenberg(SAMPLE_BOOK, 9)
        self.assertEqual(book['title'], 'Tiny Tale')
        self.assertEqual(book['author'], 'Jane Doe')
        titles = [c['t'] for c in book['chapters']]
        self.assertEqual(len(titles), 3)
        self.assertIn('chapter i', titles[0].lower())
        self.assertIn('The End', titles[2])
        everything = ''.join(c['html'] for c in book['chapters'])
        self.assertNotIn('License text', everything)
        self.assertNotIn('PROJECT GUTENBERG', everything)

    def test_parser_escapes_html_and_formats_emphasis_and_verse(self):
        from .library import parse_gutenberg
        html = ''.join(c['html'] for c in parse_gutenberg(SAMPLE_BOOK, 9)['chapters'])
        self.assertIn('<em>slowly</em>', html)
        self.assertIn('&lt;and&gt;', html)
        self.assertIn('&amp;', html)
        self.assertNotIn('<and>', html)
        self.assertIn('class="verse"', html)
        self.assertIn('Roses are red,<br>Violets are blue', html)

    def test_parser_falls_back_to_even_parts_without_headings(self):
        from .library import parse_gutenberg
        text = '*** START OF THE PROJECT GUTENBERG EBOOK X ***\n\n' + ('Plain flowing prose without any headings at all. ' * 25 + '\n\n') * 80
        book = parse_gutenberg(text, 5)
        self.assertGreater(len(book['chapters']), 2)
        self.assertTrue(book['chapters'][0]['t'].startswith('Part '))

    def test_parser_rejects_empty_text(self):
        from .library import BookUnavailable, parse_gutenberg
        with self.assertRaises(BookUnavailable):
            parse_gutenberg('*** START OF THE PROJECT GUTENBERG EBOOK X ***\n\n*** END OF THE PROJECT GUTENBERG EBOOK X ***', 5)

    # ---- pages (sources mocked) ----
    def test_books_page_is_an_instant_shell_then_loads_results(self):
        from unittest import mock
        found = {'books': [{'id': 1342, 'title': 'Pride and Prejudice', 'authors': 'Jane Austen', 'note': '', 'cover': 'https://example.org/c.jpg'}], 'has_next': True}
        with mock.patch('dashboard.library.search_books', return_value=found) as search:
            shell = self.client.get(reverse('books'))
            self.assertEqual(shell.status_code, 200)
            self.assertContains(shell, 'data-async')
            self.assertNotContains(shell, 'Pride and Prejudice')
            search.assert_not_called()                      # nothing slow happens before the page opens
            part = self.client.get(reverse('books') + '?q=austen&_part=1')
        self.assertContains(part, 'Pride and Prejudice')
        self.assertContains(part, 'Jane Austen')
        self.assertContains(part, '/books/read/1342/')
        self.assertContains(part, 'Next page')

    def test_books_page_survives_a_down_catalog(self):
        from unittest import mock
        from .library import LibraryError
        with mock.patch('dashboard.library.search_books', side_effect=LibraryError('down')):
            res = self.client.get(reverse('books') + '?q=x&_part=1')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'data-retry')
        self.assertContains(res, 'did not respond')

    def test_books_empty_search_state(self):
        from unittest import mock
        with mock.patch('dashboard.library.search_books', return_value={'books': [], 'has_next': False}):
            res = self.client.get(reverse('books') + '?q=zzzz&_part=1')
        self.assertContains(res, 'No books found')

    def test_books_topic_chip_uses_its_search_term(self):
        from unittest import mock
        with mock.patch('dashboard.library.search_books', return_value={'books': [], 'has_next': False}) as search:
            self.client.get(reverse('books') + '?topic=math&_part=1')
        search.assert_called_once_with('mathematics', 1)

    def test_reader_page_and_data_endpoint(self):
        from unittest import mock
        from .library import BookUnavailable, parse_gutenberg
        book = parse_gutenberg(SAMPLE_BOOK, 9)
        page = self.client.get(reverse('book-read', args=[9]) + '?t=Tiny+Tale&a=Jane+Doe')
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, 'Tiny Tale')
        self.assertContains(page, 'id="toc"')
        self.assertContains(page, 'data-src="/books/read/9/data/"')
        with mock.patch('dashboard.library.load_book', return_value=book):
            data = self.client.get(reverse('book-data', args=[9]))
        self.assertEqual(data.status_code, 200)
        self.assertEqual(data.json()['book']['chapters'][0]['i'], 0)
        self.assertIn('max-age', data['Cache-Control'])
        with mock.patch('dashboard.library.load_book', side_effect=BookUnavailable('nope')):
            bad = self.client.get(reverse('book-data', args=[9]))
        self.assertEqual(bad.status_code, 502)
        self.assertFalse(bad.json()['ok'])

    def test_reader_title_cannot_inject_html(self):
        res = self.client.get(reverse('book-read', args=[9]) + '?t=%3Cscript%3Ealert(1)%3C/script%3E')
        self.assertNotContains(res, '<script>alert(1)</script>')

    def test_library_pages_require_login(self):
        self.client.logout()
        for url in (reverse('books'), reverse('book-read', args=[9]), reverse('book-data', args=[9])):
            self.assertEqual(self.client.get(url).status_code, 302, url)


class VideosComingSoonTests(TestCase):
    """Videos are switched off: the page and every old video link only show the notice, with no player at all."""

    def test_videos_page_and_old_links_show_the_notice(self):
        for url in (reverse('youtube'), '/youtube/?q=perfect&v=2Vv-BfVoq4g', '/youtube/watch/2Vv-BfVoq4g/',
                    '/youtube/channel/UCYO_jab_esuFRV4b17AJtAw/', '/youtube/stream/2Vv-BfVoq4g/'):
            res = self.client.get(url)
            self.assertEqual(res.status_code, 200, url)
            self.assertContains(res, 'Under construction')
            self.assertNotContains(res, 'iframe')
            self.assertNotContains(res, 'youtube.com/embed')


class SecurityHeaderTests(TestCase):
    """Signed-in pages are never stored by shared caches, and the site only answers for its own hosts."""

    def test_signed_in_pages_are_private(self):
        User.objects.create_user('sec', 'sec@example.com', 'Sec-pass-12345')
        self.client.login(username='sec', password='Sec-pass-12345')
        res = self.client.get(reverse('notes'))
        self.assertIn('private', res['Cache-Control'])
        self.assertIn('camera=()', res['Permissions-Policy'])

    def test_unknown_host_is_refused(self):
        with self.settings(ALLOWED_HOSTS=['.vercel.app']):
            self.assertEqual(self.client.get('/', HTTP_HOST='evil.example.com').status_code, 400)
            self.assertNotEqual(self.client.get('/', HTTP_HOST='studentstudyportal-wheat.vercel.app').status_code, 400)


class OwnershipTests(TestCase):
    """A student can never read, change or delete another student's notes, homework or to-dos."""

    def setUp(self):
        from datetime import timedelta
        from django.utils import timezone
        owner = User.objects.create_user('owner', 'owner@example.com', 'Owner-pass-123')
        self.note = Notes.objects.create(user=owner, title='Private note', description='mine')
        self.hw = Homework.objects.create(user=owner, subject='Java', title='Private hw', due=timezone.now() + timedelta(days=2))
        self.todo = Todo.objects.create(user=owner, title='Private todo')
        User.objects.create_user('intruder', 'intruder@example.com', 'Intruder-pass-123')
        self.client.login(username='intruder', password='Intruder-pass-123')

    def test_other_students_items_are_invisible_and_untouchable(self):
        self.assertEqual(self.client.get(reverse('notes-detail', args=[self.note.pk])).status_code, 404)
        for name, obj in (('delete-note', self.note), ('update-homework', self.hw), ('delete-homework', self.hw),
                          ('update-todo', self.todo), ('delete-todo', self.todo)):
            self.assertEqual(self.client.post(reverse(name, args=[obj.pk])).status_code, 404, name)
        self.assertTrue(Notes.objects.filter(pk=self.note.pk).exists())
        self.assertTrue(Homework.objects.filter(pk=self.hw.pk, is_finished=False).exists())
        self.assertTrue(Todo.objects.filter(pk=self.todo.pk).exists())

    def test_changes_need_a_post(self):
        self.client.logout()
        self.client.login(username='owner', password='Owner-pass-123')
        self.assertEqual(self.client.get(reverse('delete-note', args=[self.note.pk])).status_code, 405)
        self.assertTrue(Notes.objects.filter(pk=self.note.pk).exists())


class LoginThrottleTests(TestCase):
    """Password guessing is stopped after 5 wrong tries for one account, even if the 6th is right."""

    def setUp(self):
        User.objects.create_user('target', 'target@example.com', 'Right-pass-123')

    def test_lockout_after_five_failures_and_reset_on_success(self):
        url = reverse('login')
        for _ in range(5):
            self.assertEqual(self.client.post(url, {'username': 'target', 'password': 'wrong'}).status_code, 200)
        blocked = self.client.post(url, {'username': 'target', 'password': 'Right-pass-123'})
        self.assertEqual(blocked.status_code, 429)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_success_clears_earlier_failures(self):
        url = reverse('login')
        for _ in range(3):
            self.client.post(url, {'username': 'target', 'password': 'wrong'})
        self.assertEqual(self.client.post(url, {'username': 'target', 'password': 'Right-pass-123'}).status_code, 302)
        self.client.logout()
        for _ in range(4):
            self.client.post(url, {'username': 'target', 'password': 'wrong'})
        self.assertEqual(self.client.post(url, {'username': 'target', 'password': 'Right-pass-123'}).status_code, 302)


class FakeStream:
    """Stands in for Gemini's streamed answer (server-sent events)."""

    def __init__(self, pieces, fail_after=None, finish=None):
        self.pieces, self.fail_after, self.finish = pieces, fail_after, finish

    def iter_lines(self, decode_unicode=True):
        import json as _json
        import requests as _requests
        for n, p in enumerate(self.pieces):
            if self.fail_after is not None and n == self.fail_after:
                raise _requests.ConnectionError('dropped')
            cand = {'content': {'parts': [{'text': 'hidden', 'thought': True}, {'text': p}]}}
            if self.finish and n == len(self.pieces) - 1:
                cand['finishReason'] = self.finish
            yield 'data: ' + _json.dumps({'candidates': [cand]})

    def close(self):
        pass


class LexiTests(TestCase):
    def setUp(self):
        User.objects.create_user('asker', 'asker@example.com', 'Asker-pass-123')
        self.client.login(username='asker', password='Asker-pass-123')

    def ask(self, HTTP_ACCEPT_ENCODING='', **extra):
        data = {'prompt': 'What is 2 + 2?', 'stream': '1', **extra}
        return self.client.post(reverse('chatbot'), data, HTTP_X_REQUESTED_WITH='XMLHttpRequest',
                                HTTP_ACCEPT_ENCODING=HTTP_ACCEPT_ENCODING)

    def test_answer_streams_without_thoughts(self):
        with self.settings(GEMINI_API_KEY='k'), mock.patch('dashboard.lexi.open_stream', return_value=FakeStream(['2 + 2 ', '= **4**'])):
            res = self.ask()
        self.assertTrue(res['Content-Type'].startswith('text/plain'))
        self.assertEqual(b''.join(res.streaming_content).decode(), '2 + 2 = **4**')

    def test_dropped_connection_says_so(self):
        with self.settings(GEMINI_API_KEY='k'), mock.patch('dashboard.lexi.open_stream', return_value=FakeStream(['Half', 'rest'], fail_after=1)):
            body = b''.join(self.ask().streaming_content).decode()
        self.assertTrue(body.startswith('Half'))
        self.assertIn('cut off', body)

    def test_service_down_is_a_json_error(self):
        from .lexi import LexiError
        with self.settings(GEMINI_API_KEY='k'), mock.patch('dashboard.lexi.open_stream', side_effect=LexiError('down')):
            res = self.ask()
        self.assertEqual(res.status_code, 503)
        self.assertFalse(res.json()['ok'])

    def test_questions_are_rate_limited_per_student(self):
        from . import views
        with self.settings(GEMINI_API_KEY='k'), mock.patch.object(views, 'LEXI_LIMIT_BURST', (2, 600)), \
                mock.patch('dashboard.lexi.open_stream', side_effect=lambda *a: FakeStream(['ok'])):
            self.assertEqual(self.ask().status_code, 200)
            self.assertEqual(self.ask().status_code, 200)
            third = self.ask()
        self.assertEqual(third.status_code, 429)
        self.assertIn('try again', third.json()['error'])

    def test_empty_question_and_missing_key(self):
        self.assertEqual(self.ask(prompt='  ').status_code, 400)
        with self.settings(GEMINI_API_KEY=''):
            self.assertEqual(self.ask().status_code, 503)

    def test_history_is_cleaned(self):
        from .lexi import clean_history
        raw = '[{"role":"user","text":"hi"},{"role":"evil","text":"x"},{"text":5},"junk",{"role":"model","text":"   "}]'
        self.assertEqual(clean_history(raw), [{'role': 'user', 'text': 'hi'}, {'role': 'model', 'text': 'x'}])
        self.assertEqual(clean_history('not json'), [])

    def test_prompt_guards_privacy_and_knows_the_site(self):
        from .lexi import SYSTEM_PROMPT
        self.assertIn('NO ACCESS TO ACCOUNTS', SYSTEM_PROMPT)
        self.assertIn('Never ask for a password', SYSTEM_PROMPT)
        for link in ('/homework/#hw-dialog', '/notes/#note-dialog', '/todo/#add', '/dictionary/?q=', '/wiki/?q=', '/books/?q='):
            self.assertIn(link, SYSTEM_PROMPT)


    def test_streamed_answers_are_not_held_back_by_gzip(self):
        with self.settings(GEMINI_API_KEY='k'), mock.patch('dashboard.lexi.open_stream', return_value=FakeStream(['a ' * 200])):
            res = self.ask(HTTP_ACCEPT_ENCODING='gzip')
        self.assertFalse(res.has_header('Content-Encoding'))
        page = self.client.get(reverse('chatbot'), HTTP_ACCEPT_ENCODING='gzip')
        self.assertEqual(page['Content-Encoding'], 'gzip')


    def _models(self, behaviour):
        """Patch the per-model call: behaviour(model) returns a FakeStream or raises."""
        from . import lexi
        return mock.patch.object(lexi, '_attempt', side_effect=lambda key, model, history, prompt: behaviour(model))

    def test_slow_first_model_is_overtaken_by_the_next(self):
        import time as _t
        from . import lexi

        def behaviour(model):
            if model == lexi.MODELS[0]:
                _t.sleep(0.8)
                return FakeStream(['slow'])
            return FakeStream(['fast'])
        with mock.patch.object(lexi, 'HEDGE_AFTER', 0.1), mock.patch.dict(lexi._SKIP_UNTIL, clear=True), self._models(behaviour):
            t0 = _t.monotonic()
            resp = lexi.open_stream('k', [], 'hi')
            waited = _t.monotonic() - t0
        self.assertEqual(''.join(lexi.iter_text(resp)), 'fast')
        self.assertLess(waited, 0.6)

    def test_failing_model_moves_on_at_once_and_all_failing_raises(self):
        from . import lexi

        def first_down(model):
            if model == lexi.MODELS[0]:
                raise lexi.LexiError('down')
            return FakeStream(['ok'])
        with mock.patch.dict(lexi._SKIP_UNTIL, clear=True), self._models(first_down):
            self.assertEqual(''.join(lexi.iter_text(lexi.open_stream('k', [], 'hi'))), 'ok')

        def all_down(model):
            raise lexi.LexiError(f'{model} down')
        with mock.patch.dict(lexi._SKIP_UNTIL, clear=True), self._models(all_down), self.assertRaises(lexi.LexiError):
            lexi.open_stream('k', [], 'hi')

    def test_warm_up_opens_the_connection_and_needs_sign_in(self):
        with self.settings(GEMINI_API_KEY='k'), mock.patch('dashboard.lexi.warm') as warm:
            res = self.client.get(reverse('chatbot-warm'))
        self.assertEqual(res.status_code, 200)
        warm.assert_called_once_with('k')
        self.client.logout()
        self.assertEqual(self.client.get(reverse('chatbot-warm')).status_code, 302)

    def test_stream_is_read_as_utf8(self):
        from . import lexi
        ok = mock.MagicMock(status_code=200)
        with mock.patch.object(lexi, '_session') as session:
            session.return_value.post.return_value = ok
            self.assertIs(lexi._attempt('k', lexi.MODELS[0], [], 'hi'), ok)
        self.assertEqual(ok.encoding, 'utf-8')

    def test_answer_stopped_for_recitation_is_continued(self):
        from . import lexi
        with mock.patch.object(lexi, 'open_stream', return_value=FakeStream([' and the rest.'])) as more:
            out = ''.join(lexi.stream_answer('k', [], 'Tell me about 9/11', FakeStream(['At 8:46 a.m.'], finish='RECITATION')))
        self.assertEqual(out, 'At 8:46 a.m. and the rest.')
        follow_up, again = more.call_args.args[1], more.call_args.args[2]
        self.assertEqual(follow_up[-1], {'role': 'model', 'text': 'At 8:46 a.m.'})
        self.assertIn('Continue', again)

    def test_answer_stopped_by_safety_says_so(self):
        from . import lexi
        out = ''.join(lexi.stream_answer('k', [], 'q', FakeStream(['Part'], finish='SAFETY')))
        self.assertTrue(out.startswith('Part'))
        self.assertIn('flagged', out)

    def test_continuing_stops_after_two_tries(self):
        from . import lexi
        with mock.patch.object(lexi, 'open_stream', side_effect=lambda *a: FakeStream([' more'], finish='MAX_TOKENS')) as more:
            out = ''.join(lexi.stream_answer('k', [], 'q', FakeStream(['Start'], finish='MAX_TOKENS')))
        self.assertEqual(more.call_count, 2)
        self.assertIn('cut short', out)

class ContentSecurityPolicyTests(TestCase):
    def test_policy_header_and_nonce_on_inline_scripts(self):
        res = self.client.get(reverse('home'))
        policy = res['Content-Security-Policy']
        self.assertIn("script-src 'self' 'nonce-", policy)
        self.assertIn("frame-ancestors 'none'", policy)
        nonce = policy.split("'nonce-")[1].split("'")[0]
        self.assertContains(res, f'<script nonce="{nonce}">')
        self.assertNotContains(res, '<script>')


class ThrottleTests(TestCase):
    def test_limits_fail_open_when_the_table_is_missing(self):
        from django.db import ProgrammingError
        from . import throttle
        with mock.patch('dashboard.throttle.Throttle.objects') as objects:
            objects.filter.side_effect = ProgrammingError('no such table')
            objects.select_for_update.side_effect = ProgrammingError('no such table')
            self.assertFalse(throttle.blocked('k', 1, 60))
            self.assertTrue(throttle.allowed('k', 1, 60))
