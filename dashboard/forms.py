from django import forms
from .models import Notes, Homework, Todo
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import authenticate

class StudentLoginForm(AuthenticationForm):
    username = forms.CharField(
        label="Username or Email",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Username or Email', 'autofocus': True})
    )
    password = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Enter Password'})
    )

    def clean(self):
        username = self.cleaned_data.get('username')
        password = self.cleaned_data.get('password')

        if username and password:
            clean_username = username.strip()
            user_by_email = User.objects.filter(email__iexact=clean_username).first()
            if user_by_email:
                auth_username = user_by_email.username
            else:
                user_by_uname = User.objects.filter(username__iexact=clean_username).first()
                auth_username = user_by_uname.username if user_by_uname else clean_username

            self.user_cache = authenticate(self.request, username=auth_username, password=password)
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            else:
                self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        if user.is_staff or user.is_superuser:
            raise forms.ValidationError(
                "This account has Administrator privileges. Admin accounts cannot log in as a student. "
                "Please log in through the Admin Portal at /admin/.",
                code='admin_not_allowed',
            )

class Notesform(forms.ModelForm):
    class Meta:
        model = Notes
        fields = ['subject', 'title', 'description']
        widgets = {
            'subject': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Note Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Enter Note Description...', 'rows': 4}),
        }

class DateInput(forms.DateInput):
    input_type = 'date'

class HomeworkForm(forms.ModelForm):
    class Meta:
        model = Homework
        widgets = {
            'due': DateInput(),
            'subject': forms.Select(attrs={'class': 'form-control'}),
        }
        fields = ['subject', 'title', 'description', 'due', 'is_finished']

class DashboardForm(forms.Form):
    text = forms.CharField(max_length=100,label="Enter Your Search : ")

class TodoForm(forms.ModelForm):
    class Meta:
        model = Todo
        fields = ['title', 'is_finished']

class ConversionForm(forms.Form):
    CHOICES = [('length', 'Length'), ('mass', 'Mass')]
    measurement = forms.ChoiceField(choices=CHOICES, widget=forms.RadioSelect)

class ConversionLengthForm(forms.Form):
    CHOICES = [('yard', 'Yard'), ('foot', 'Foot')]
    measure1 = forms.ChoiceField(choices=CHOICES)
    measure2 = forms.ChoiceField(choices=CHOICES)
    input = forms.IntegerField(required=True)

class ConversionMassForm(forms.Form):
    CHOICES = [('pound', 'Pound'), ('kilogram', 'Kilogram')]
    measure1 = forms.ChoiceField(choices=CHOICES)
    measure2 = forms.ChoiceField(choices=CHOICES)
    input = forms.IntegerField(required=True)   

class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Enter Email (optional)'}),
        help_text="Optional. Used for logging in and password recovery."
    )

    class Meta:
        model = User
        fields = ['username', 'email']