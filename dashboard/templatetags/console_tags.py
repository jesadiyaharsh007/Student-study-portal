from django import template
from django.utils.timesince import timesince

register = template.Library()


def _first_unit(value):
    return timesince(value).replace("\xa0", " ").split(",")[0]


@register.filter
def ago(value):
    """'5 hours ago' instead of '5 hours, 30 minutes ago'."""
    if not value:
        return ""
    text = _first_unit(value)
    return "just now" if text.startswith("0 ") else f"{text} ago"


@register.filter
def span(value):
    """'5 hours' (one unit) for account ages."""
    if not value:
        return ""
    text = _first_unit(value)
    return "less than a minute" if text.startswith("0 ") else text
