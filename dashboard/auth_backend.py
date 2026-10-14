from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save

_TTL = 120


def _key(user_id):
    return f"auth-user-{user_id}"


class CachedUserBackend(ModelBackend):
    """Same as ModelBackend, but request.user is served from the in-memory cache
    while the serverless instance is warm, so most page loads skip the database."""

    def get_user(self, user_id):
        user = cache.get(_key(user_id))
        if user is None:
            user = super().get_user(user_id)
            if user is not None:
                cache.set(_key(user_id), user, _TTL)
        return user


def _evict(sender, instance, **kwargs):
    cache.delete(_key(instance.pk))


post_save.connect(_evict, sender=User, dispatch_uid="evict-user-cache-save")
post_delete.connect(_evict, sender=User, dispatch_uid="evict-user-cache-delete")
