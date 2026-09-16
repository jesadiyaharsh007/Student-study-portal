from django import forms
from .models import Notes, Homework, Todo
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm

class Notesform(forms.ModelForm):
    class Meta:
        model = Notes
        fields = ['title','description']

class DateInput(forms.DateInput):
    input_type = 'date'

class HomeworkForm(forms.ModelForm):
    class Meta:
        model = Homework
        widgets = {'due':DateInput()}
        fields = ['subject','title','description','due','is_finished']

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
    class Meta:
        model = User
        fields = ['username']