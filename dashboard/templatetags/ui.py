from django import template
import unicodedata
from django.templatetags.static import static
from django.utils.html import format_html
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag
def icon(name, extra=""):
    """Inline reference to the SVG sprite rendered once in base.html."""
    return format_html('<svg class="ic {}" aria-hidden="true"><use href="#i-{}"/></svg>', extra, name)


@register.filter
def subject_tone(subject):
    return {
        "Java": "red", "PHP": "violet", "Python": "sky", "ADBMS": "teal", "Spring": "green",
        "C": "slate", "C++": "primary", "ML": "pink", "Docker": "sky", "Other": "amber",
    }.get(subject, "primary")


@register.simple_tag
def photo(name, alt="", sizes="(min-width: 1000px) 50vw, 100vw", eager=False, pos="center"):
    """Responsive WebP version of one of the portal's photographs."""
    return format_html(
        '<img src="{lg}" srcset="{sm} 640w, {lg} 1400w" sizes="{sizes}" alt="{alt}" style="object-position:{pos}" '
        'decoding="async" {load}>',
        lg=static(f"images/{name}-lg.webp"), sm=static(f"images/{name}-sm.webp"), sizes=sizes, alt=alt, pos=pos,
        load=mark_safe('fetchpriority="high"' if eager else 'loading="lazy"'),
    )


_ZWJ = "\u200d"


def _first_grapheme(text):
    """First user-perceived character: handles combining marks, emoji modifiers/ZWJ sequences and flags."""
    text = (text or "").strip()
    if not text:
        return ""
    out = text[0]
    i = 1
    regional = 0x1F1E6 <= ord(text[0]) <= 0x1F1FF
    if regional and len(text) > 1 and 0x1F1E6 <= ord(text[1]) <= 0x1F1FF:
        return text[:2]
    while i < len(text):
        ch = text[i]
        cp = ord(ch)
        if unicodedata.category(ch).startswith("M") or cp == 0xFE0F or 0x1F3FB <= cp <= 0x1F3FF:
            out += ch
            i += 1
        elif ch == _ZWJ and i + 1 < len(text):
            out += ch + text[i + 1]
            i += 2
        else:
            break
    return out


@register.filter
def initial(value):
    """Avatar initial that is safe for emoji and non-Latin usernames."""
    g = _first_grapheme(str(value))
    return g.upper() if g else "?"
