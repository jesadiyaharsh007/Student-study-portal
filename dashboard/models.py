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


class AdminSession(models.Model):
    """One refresh token of the admin console (see dashboard/console/tokens.py).

    Refresh tokens rotate: each use revokes the row and creates a successor, so a stolen token
    that is replayed is detected. Access tokens are stateless and short-lived.
    """

    jti = models.CharField(max_length=64, unique=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="console_sessions")
    created_at = models.DateTimeField(default=timezone.now)
    last_used_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    origin_at = models.DateTimeField(default=timezone.now)  # when this chain started (absolute lifetime cap)
    revoked_at = models.DateTimeField(null=True, blank=True)
    replaced_by = models.CharField(max_length=64, blank=True, default="")
    user_agent = models.CharField(max_length=255, blank=True, default="")
    ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["user", "revoked_at"])]

    def __str__(self):
        return f"{self.user_id}:{self.jti[:6]}"


class Throttle(models.Model):
    """A counter for one kind of attempt (sign-in by name, sign-in by address, Lexi questions) in a time window.
    Kept in the database so every serverless instance sees the same count (see dashboard/throttle.py)."""
    key = models.CharField(max_length=80, unique=True)
    window_start = models.DateTimeField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "rate limit"
        verbose_name_plural = "rate limits"
