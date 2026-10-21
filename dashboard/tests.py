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
        for url in (reverse('books'), reverse('youtube'), reverse('book-read', args=[9]), reverse('book-data', args=[9])):
            self.assertEqual(self.client.get(url).status_code, 302, url)

    SAMPLE_VIDEO = {
        'id': 'WUvTyaaNkzM', 'title': 'The Essence of Calculus', 'channel': '3Blue1Brown', 'duration': '17:05',
        'views': '11.8M views', 'published': '9 years ago', 'thumbnail': 'https://i.ytimg.com/vi/WUvTyaaNkzM/mqdefault.jpg',
    }

    def test_youtube_cold_start_shows_feed_without_ad_wording(self):
        with mock.patch('dashboard.videos.home_feed', return_value=[self.SAMPLE_VIDEO]):
            res = self.client.get(reverse('youtube'))
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Suggested for you')
        self.assertContains(res, 'The Essence of Calculus')
        self.assertContains(res, 'data-id="WUvTyaaNkzM"')
        self.assertNotIn('ad-free', res.content.decode().lower())

    def test_youtube_topic_chip_filter(self):
        with mock.patch('dashboard.videos.search_videos', return_value=([self.SAMPLE_VIDEO], None)) as search:
            res = self.client.get(reverse('youtube') + '?topic=calculus')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'Calculus')
        self.assertEqual(search.call_args[0][0], 'calculus explained')

    def test_youtube_deep_link_opens_the_watch_view(self):
        with mock.patch('dashboard.videos.home_feed', return_value=[self.SAMPLE_VIDEO]):
            res = self.client.get(reverse('youtube') + '?v=WUvTyaaNkzM')
            bad = self.client.get(reverse('youtube') + '?v=<script>')
        self.assertContains(res, 'data-start="WUvTyaaNkzM"')
        self.assertContains(bad, 'data-start=""')

    def test_youtube_watch_data(self):
        info = dict(self.SAMPLE_VIDEO, description='x', related=[], subscribers='1M', link='https://youtu.be/x')
        with mock.patch('dashboard.videos.video_details', return_value=info):
            ok = self.client.get(reverse('youtube-watch', args=['WUvTyaaNkzM']))
        self.assertEqual(ok.status_code, 200)
        self.assertEqual(ok.json()['title'], 'The Essence of Calculus')
        with mock.patch('dashboard.videos.video_details', return_value=None):
            gone = self.client.get(reverse('youtube-watch', args=['WUvTyaaNkzM']))
        self.assertEqual(gone.status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('youtube-watch', args=['WUvTyaaNkzM'])).status_code, 302)

    def test_youtube_results_fragment_for_in_page_search(self):
        with mock.patch('dashboard.videos.search_videos', return_value=([self.SAMPLE_VIDEO], None)):
            res = self.client.get(reverse('youtube') + '?q=calculus&_part=1')
        self.assertEqual(res.status_code, 200)
        self.assertContains(res, 'data-id="WUvTyaaNkzM"')
        self.assertNotContains(res, '<html')

    def test_youtube_lexi_answers_about_the_video(self):
        info = dict(self.SAMPLE_VIDEO, description='Limits and derivatives', related=[])
        with mock.patch('dashboard.videos.video_details', return_value=info),                 mock.patch('dashboard.videos.transcript_text', return_value='We start with limits.'),                 mock.patch('dashboard.views._query_gemini_tutor', return_value='A short summary.') as ask,                 self.settings(GEMINI_API_KEY='test-key'):
            res = self.client.post(reverse('youtube-lexi'), {'video': 'WUvTyaaNkzM', 'question': 'Summarize'})
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertTrue(data['ok'])
        self.assertTrue(data['captions'])
        prompt = ask.call_args[0][2]
        self.assertIn('We start with limits.', prompt)
        self.assertIn('The Essence of Calculus', prompt)
        bad = self.client.post(reverse('youtube-lexi'), {'video': 'nope', 'question': 'x'})
        self.assertEqual(bad.status_code, 400)
        self.assertEqual(self.client.get(reverse('youtube-lexi')).status_code, 405)

    SAMPLE_MANIFEST = {
        'at': 0, 'public': {'id': 'WUvTyaaNkzM', 'title': 'The Essence of Calculus', 'channel': '3Blue1Brown', 'duration': 1024,
                            'video': [{'itag': '136', 'height': 720, 'fps': 30, 'codec': 'avc1.4D401F', 'bitrate': 1000000, 'size': 1}],
                            'audio': {'itag': '140', 'codec': 'mp4a.40.2', 'bitrate': 128000, 'size': 1}},
        'urls': {'136': 'https://example.com/v', '140': 'https://example.com/a'},
    }

    def test_youtube_stream_manifest_hides_the_links(self):
        with mock.patch('dashboard.videos.stream_manifest', return_value=self.SAMPLE_MANIFEST):
            ok = self.client.get(reverse('youtube-stream', args=['WUvTyaaNkzM']))
        self.assertEqual(ok.status_code, 200)
        data = ok.json()
        self.assertEqual(data['video'][0]['height'], 720)
        self.assertNotIn('example.com', ok.content.decode())
        with mock.patch('dashboard.videos.stream_manifest', side_effect=__import__('dashboard.videos', fromlist=['x']).StreamUnavailable('nope')):
            gone = self.client.get(reverse('youtube-stream', args=['WUvTyaaNkzM']))
        self.assertEqual(gone.status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('youtube-stream', args=['WUvTyaaNkzM'])).status_code, 302)

    def test_youtube_media_relays_ranges(self):
        class Upstream:
            status_code = 206
            headers = {'Content-Type': 'video/mp4', 'Content-Length': '4', 'Content-Range': 'bytes 0-3/10'}
            def iter_content(self, n): yield b'abcd'
            def close(self): pass
        with mock.patch('dashboard.videos.media_url', return_value='https://example.com/v'), \
                mock.patch('dashboard.videos._HTTP_SESSION.get', return_value=Upstream()) as get:
            res = self.client.get(reverse('youtube-media', args=['WUvTyaaNkzM', '136']), HTTP_RANGE='bytes=0-3')
            body = b''.join(res.streaming_content)
        self.assertEqual(res.status_code, 206)
        self.assertEqual(body, b'abcd')
        self.assertEqual(res['Content-Range'], 'bytes 0-3/10')
        self.assertEqual(get.call_args[1]['headers']['Range'], 'bytes=0-3')
        self.assertEqual(self.client.get(reverse('youtube-media', args=['WUvTyaaNkzM', 'abc'])).status_code, 400)

    def test_youtube_captions_endpoints(self):
        with mock.patch('dashboard.videos.caption_tracks', return_value=[{'lang': 'en', 'name': 'English', 'auto': False}]):
            tracks = self.client.get(reverse('youtube-captions', args=['WUvTyaaNkzM'])).json()
        self.assertEqual(tracks['tracks'][0]['lang'], 'en')
        with mock.patch('dashboard.videos.caption_cues', return_value=[[0, 2, 'Hello']]):
            cues = self.client.get(reverse('youtube-caption-cues', args=['WUvTyaaNkzM', 'en'])).json()
        self.assertEqual(cues['cues'][0][2], 'Hello')

    def test_youtube_download_sets_a_filename(self):
        class Upstream:
            status_code = 200
            headers = {'Content-Type': 'audio/mp4', 'Content-Length': '3'}
            def iter_content(self, n): yield b'abc'
        with mock.patch('dashboard.videos.stream_manifest', return_value=self.SAMPLE_MANIFEST), \
                mock.patch('dashboard.videos._HTTP_SESSION.get', return_value=Upstream()):
            res = self.client.get(reverse('youtube-download', args=['WUvTyaaNkzM', 'audio']))
            b''.join(res.streaming_content)
        self.assertEqual(res.status_code, 200)
        self.assertIn('attachment', res['Content-Disposition'])
        self.assertIn('.m4a', res['Content-Disposition'])

    def test_youtube_token_only_with_a_configured_service(self):
        self.assertEqual(self.client.get(reverse('youtube-token')).status_code, 404)
        with self.settings(MEDIA_SERVICE_URL='https://media.example.com', MEDIA_SERVICE_SECRET='s3cret'):
            res = self.client.get(reverse('youtube-token'))
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['base'], 'https://media.example.com')
        import hashlib, hmac
        exp, sig = data['token'].split('.')
        self.assertEqual(sig, hmac.new(b's3cret', exp.encode(), hashlib.sha256).hexdigest())
        self.assertEqual(res['Cache-Control'], 'no-store')
        self.client.logout()
        self.assertEqual(self.client.get(reverse('youtube-token')).status_code, 302)

    def test_player_mode_defaults(self):
        self.assertContains(self.client.get(reverse('youtube')), 'data-mode="auto"')
        with self.settings(PLAYER_MODE='embed'):
            self.assertContains(self.client.get(reverse('youtube')), 'data-mode="embed"')
