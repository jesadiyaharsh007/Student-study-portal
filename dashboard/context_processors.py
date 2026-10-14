from django.urls import reverse

# Single source of truth for navigation, the home grid and the command palette.
TOOLS = (
    # key, url name, label, icon, tone, description
    ("notes", "notes", "Notes", "note", "amber", "Capture ideas and organise them by subject."),
    ("homework", "homework", "Homework", "clipboard", "violet", "Track assignments and never miss a deadline."),
    ("todo", "todo", "To-do", "checks", "green", "A fast checklist for everything else."),
    ("chatbot", "chatbot", "Lexi", "bot", "pink", "Ask anything and get a clear explanation."),
    ("dictionary", "dictionary", "Dictionary", "book-a", "teal", "Definitions, phonetics and synonyms."),
    ("books", "books", "Books", "book-open", "sky", "Search a huge open library of books."),
    ("wiki", "wiki", "Wikipedia", "globe", "slate", "Quick, trustworthy summaries."),
    ("youtube", "youtube", "Videos", "play", "red", "Find lessons without the rabbit hole."),
    ("conversion", "conversion", "Converter", "swap", "orange", "Length, mass, temperature and more."),
)


def navigation(request):
    match = getattr(request, "resolver_match", None)
    tools = [
        {
            "key": k, "url": reverse(u), "label": label, "icon": icon, "tone": tone, "desc": desc,
        }
        for k, u, label, icon, tone, desc in TOOLS
    ]
    return {"tools": tools, "current": match.url_name if match else ""}
