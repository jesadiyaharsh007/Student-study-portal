from django.urls import reverse

# Single source of truth for navigation, the home grid and the command palette.
TOOLS = (
    # key, url name, label, icon, tone, description
    ("notes", "notes", "Notes", "note", "amber", "Capture ideas and organise them by subject."),
    ("homework", "homework", "Homework", "clipboard", "violet", "Track assignments and never miss a deadline."),
    ("todo", "todo", "To-do", "checks", "green", "A fast checklist for everything else."),
    ("chatbot", "chatbot", "Lexi", "cap", "pink", "Ask anything and get a clear explanation."),
    ("dictionary", "dictionary", "Dictionary", "book-a", "teal", "Definitions, phonetics and synonyms."),
    ("books", "books", "Books", "book-open", "sky", "Search a huge open library of books."),
    ("wiki", "wiki", "Encyclopedia", "globe", "slate", "Quick, trustworthy summaries of any topic."),
    ("youtube", "youtube", "Videos", "play", "red", "Under construction. Coming soon."),
    ("conversion", "conversion", "Converter", "swap", "orange", "Length, mass, temperature and more."),
)

NAV_DROPDOWN = ("notes", "homework", "todo", "dictionary", "conversion")
NAV_TOP = ("chatbot", "books", "youtube", "wiki")

_TOOLS_CACHE = None


def _get_tools():
    global _TOOLS_CACHE
    if _TOOLS_CACHE is None:
        _TOOLS_CACHE = [
            {
                "key": k, "url": reverse(u), "label": label, "icon": icon, "tone": tone, "desc": desc,
            }
            for k, u, label, icon, tone, desc in TOOLS
        ]
    return _TOOLS_CACHE


def navigation(request):
    match = getattr(request, "resolver_match", None)
    tools = _get_tools()
    return {
        "tools": tools,
        # The Tools dropdown only holds the everyday tools; the rest sit directly in the top bar.
        "nav_tools": [t for t in tools if t["key"] in NAV_DROPDOWN],
        "nav_main": [t for t in tools if t["key"] in NAV_TOP],
        "current": match.url_name if match else "",
    }
