import datetime

from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.models import User

from .models import Homework, Notes, Todo


class DateInput(forms.DateInput):
    input_type = "date"


def _style(form, placeholders=None):
    """Give every widget the portal's input styling (kept out of the templates)."""
    placeholders = placeholders or {}
    for name, field in form.fields.items():
        widget = field.widget
        if isinstance(widget, forms.CheckboxInput):
            continue
        widget.attrs["class"] = (widget.attrs.get("class", "") + " input").strip()
        if name in placeholders:
            widget.attrs["placeholder"] = placeholders[name]


class StudentLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Username or email",
        widget=forms.TextInput(attrs={"autofocus": True, "autocomplete": "username"}),
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self, {"username": "you@school.edu", "password": "Your password"})

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")

        if username and password:
            clean_username = username.strip()
            user = User.objects.filter(email__iexact=clean_username).only("username").first() or \
                User.objects.filter(username__iexact=clean_username).only("username").first()
            auth_username = user.username if user else clean_username

            self.user_cache = authenticate(self.request, username=auth_username, password=password)
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.is_staff or user.is_superuser:
            raise forms.ValidationError(
                "Administrator accounts can't sign in as a student.",
                code="admin_not_allowed",
            )


class Notesform(forms.ModelForm):
    class Meta:
        model = Notes
        fields = ["subject", "title", "description"]
        widgets = {"description": forms.Textarea(attrs={"rows": 6})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self, {"title": "e.g. Binary trees, key ideas", "description": "Write your note…"})


class HomeworkForm(forms.ModelForm):
    class Meta:
        model = Homework
        fields = ["subject", "title", "description", "due"]
        widgets = {"due": DateInput(), "description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["due"].initial = datetime.date.today() + datetime.timedelta(days=1)
        self.fields["description"].required = False
        _style(self, {"title": "e.g. Chapter 4 problems", "description": "Anything worth remembering (optional)"})


class DashboardForm(forms.Form):
    text = forms.CharField(max_length=100, label="Search")


class TodoForm(forms.ModelForm):
    class Meta:
        model = Todo
        fields = ["title"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _style(self, {"title": "Add a task and press Enter"})


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=False, label="Email (optional)", help_text="Lets you sign in with your email too.")

    class Meta:
        model = User
        fields = ["username", "email"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password1"].help_text = ""
        self.fields["password2"].help_text = ""
        self.fields["username"].help_text = ""
        _style(self, {"username": "Pick a username", "email": "you@school.edu",
                      "password1": "Create a password", "password2": "Repeat the password"})
        self.fields["username"].widget.attrs["autofocus"] = True
