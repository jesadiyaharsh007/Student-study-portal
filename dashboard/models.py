from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

SUBJECT_CHOICES = (
    ('Java', 'Java'),
    ('PHP', 'PHP'),
    ('Python', 'Python'),
    ('ADBMS', 'ADBMS'),
    ('Spring', 'Spring'),
    ('C', 'C'),
    ('C++', 'C++'),
    ('ML', 'ML'),
    ('Docker', 'Docker'),
    ('Other', 'Other'),
)

class Notes(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subject = models.CharField(max_length=50, choices=SUBJECT_CHOICES, default='Java')
    title = models.CharField(max_length=200)
    description = models.TextField()
    
    def __str__(self):
        return self.title
    
    class Meta:
        verbose_name = "note"
        verbose_name_plural = "notes"

class Homework(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    subject = models.CharField(max_length=50, choices=SUBJECT_CHOICES, default='Java')
    title = models.CharField(max_length=100, default='')
    description = models.TextField(default='')
    due = models.DateTimeField(default=timezone.now)
    is_finished = models.BooleanField(default=False)

    class Meta:
        verbose_name = "homework"
        verbose_name_plural = "homework"

    def __str__(self):
        return self.title

class Todo(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    is_finished = models.BooleanField(default=False)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = "to-do"
        verbose_name_plural = "to-dos"
