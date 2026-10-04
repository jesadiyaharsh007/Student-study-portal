from functools import wraps
import requests
import re
from django.contrib import messages
from django.shortcuts import redirect, render
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views import generic
from youtube_search import YoutubeSearch
import wikipedia as wiki_api

from .forms import (
    Notesform,
    HomeworkForm,
    DashboardForm,
    TodoForm,
    ConversionForm,
    ConversionLengthForm,
    ConversionMassForm,
    UserRegistrationForm,
    StudentLoginForm,
)
from .models import Notes, Homework, Todo

def student_required(view_func):
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')
        return view_func(request, *args, **kwargs)
    return _wrapped_view

def login_view(request):
    if request.user.is_authenticated:
        if not (request.user.is_staff or request.user.is_superuser):
            return redirect('home')
        logout(request)

    if request.method == "POST":
        form = StudentLoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.username}!")
            return redirect('home')
    else:
        form = StudentLoginForm()

    return render(request, "dashboard/login.html", {'form': form})

def home(request):
    return render(request, 'dashboard/home.html')

def about(request):
    return render(request, 'dashboard/about.html')

@student_required
def notes(request):
    if request.method == "POST":
        form = Notesform(request.POST)
        if form.is_valid():
            note = form.save(commit=False)
            note.user = request.user
            note.save()
            messages.success(request, f"Notes added from {request.user.username} Successfully!")
            return redirect('notes')
    else:
        form = Notesform()
    notes = Notes.objects.filter(user=request.user)
    context = {'notes': notes, 'form': form}
    return render(request, 'dashboard/notes.html', context)

@student_required
def delete_note(request, pk=None):
    Notes.objects.get(id=pk).delete()
    return redirect("notes")

class NoteDetailview(LoginRequiredMixin, generic.DetailView):
    model = Notes

@student_required
def homework(request):
    if request.method == "POST":
        form = HomeworkForm(request.POST)
        if form.is_valid():
            finished = request.POST.get('is_finished') == 'on'
            homework = Homework(
                user = request.user,
                subject = request.POST['subject'],
                title = request.POST['title'],
                description = request.POST['description'],
                due = request.POST['due'],
                is_finished = finished,
            )
            homework.save()
            messages.success(request,f"Homework added from {request.user.username} Successfully!")
    else:
        form = HomeworkForm()
    homework = Homework.objects.filter(user=request.user)
    if len(homework) == 0:
        homework_done = True
    else:
        homework_done = False

    context = {
            'homework' :homework,
            'homework_done':homework_done,
            'form':form
    }
    return render(request,'dashboard/homework.html',context)

@student_required
def update_homework(request, pk=None):
    homework = Homework.objects.get(id=pk)
    homework.is_finished = not homework.is_finished
    homework.save()
    return redirect('homework')  

@student_required
def delete_homework(request, pk=None):
    Homework.objects.get(id=pk).delete()
    return redirect('homework')          


@login_required
def youtube(request):
    if request.method == "POST":
        form = DashboardForm(request.POST)
        text = request.POST['text']
        video = YoutubeSearch(text, max_results=10).to_dict()
        result_list = []
        for v in video:
            result_dict = {
                'input':text,
                'title':v['title'],
                'thumbnail':v['thumbnails'][0],
                'channel':v['channel'],
                'duration':v['duration'],
                'views':v['views'],
                'published':v['publish_time'],
                'link':f"https://www.youtube.com{v['url_suffix']}",
                'description': v.get('long_desc') or 'No description available'
            }
            result_list.append(result_dict)
        context={
            'form':form,
            'results':result_list
        }
        return render(request,'dashboard/youtube.html',context)
    else:
        form = DashboardForm()
    context = {'form':form}
    return render(request, "dashboard/youtube.html", context)

@student_required
def todo(request):
    if request.method == "POST":
        form = TodoForm(request.POST)

        if form.is_valid():
            finished = request.POST.get("is_finished") == "on"

            todo = Todo(
                user=request.user,
                title=request.POST["title"],
                is_finished=finished,
            )

            todo.save()
            messages.success(request, f"Todo added from {request.user.username} Successfully!")
            return redirect("todo")

    else:
        form = TodoForm()

    todos = Todo.objects.filter(user=request.user)

    if len(todos) == 0:
        todo_done = True
    else:
        todo_done = False

    context = {
        "form": form,
        "todos": todos,
        "todo_done": todo_done,
    }

    return render(request, "dashboard/todo.html", context)

@student_required
def update_todo(request, pk=None):
    todo = Todo.objects.get(id=pk)
    todo.is_finished = not todo.is_finished
    todo.save()
    return redirect("todo") 

@student_required
def delete_todo(request, pk=None):
    Todo.objects.get(id=pk).delete()
    return redirect("todo")

def _parse_openlibrary_docs(docs):
    result_list = []
    for doc in docs[:10]:
        try:
            thumbnail = ""
            if doc.get('cover_i'):
                thumbnail = f"https://covers.openlibrary.org/b/id/{doc.get('cover_i')}-M.jpg"

            authors = ", ".join(doc.get('author_name', []))
            subtitle = f"Author: {authors}" if authors else ""

            result_dict = {
                'title': doc.get('title'),
                'subtitle': subtitle,
                'description': f"First Published: {doc.get('first_publish_year', 'Unknown')}",
                'count': doc.get('number_of_pages_median'),
                'categories': doc.get('subject', [])[:3],
                'rating': round(doc.get('ratings_average'), 1) if doc.get('ratings_average') else None,
                'thumbnail': thumbnail,
                'preview': f"https://openlibrary.org{doc.get('key')}" if doc.get('key') else "#"
            }
            result_list.append(result_dict)
        except Exception:
            pass
    return result_list

@login_required
def books(request):
    if request.method == "POST":
        form = DashboardForm(request.POST)
        text = request.POST['text']
        url = "https://openlibrary.org/search.json?q=" + text
        r = requests.get(url)
        answer = r.json()
        docs = answer.get('docs', [])

        if not docs:
            messages.warning(request, 'No books found for your search.')
            result_list = []
        else:
            result_list = _parse_openlibrary_docs(docs)

        context = {
            'form': form,
            'results': result_list
        }
        return render(request, 'dashboard/books.html', context)
    else:
        form = DashboardForm()
        homework = Homework.objects.filter(user=request.user, is_finished=False).last()
        if homework:
            try:
                url = "https://openlibrary.org/search.json?q=" + homework.subject
                r = requests.get(url)
                answer = r.json()
                docs = answer.get('docs', [])
                if docs:
                    result_list = _parse_openlibrary_docs(docs)
                    context = {'form': form, 'results': result_list, 'is_recommendation': True}
                    return render(request, 'dashboard/books.html', context)
            except Exception:
                pass
    context = {'form': form}
    return render(request, "dashboard/books.html", context)

@login_required
def dictionary(request):
    form = DashboardForm()

    if request.method == "POST":
        form = DashboardForm(request.POST)

        if form.is_valid():
            text = form.cleaned_data["text"]
            clean_text = text.strip().lower()

            phonetics = ""
            audio = ""
            definition = ""
            example = ""
            synonyms = []
            found = False

            try:
                url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{clean_text}"
                r = requests.get(url, timeout=3, headers={"User-Agent": "Mozilla/5.0"})
                if r.status_code == 200:
                    answer = r.json()
                    for p in answer[0].get("phonetics", []):
                        if p.get("text") and not phonetics:
                            phonetics = p["text"]
                        if p.get("audio") and not audio:
                            audio = p["audio"]

                    if audio.startswith("//"):
                        audio = "https:" + audio

                    if answer[0].get("meanings"):
                        meanings = answer[0]["meanings"][0]
                        if meanings.get("definitions"):
                            defs = meanings["definitions"][0]
                            definition = defs.get("definition", "")
                            example = defs.get("example", "")
                        synonyms = meanings.get("synonyms", [])
                    found = True
            except Exception:
                pass

            if not found:
                try:
                    w_url = f"https://en.wiktionary.org/api/rest_v1/page/definition/{clean_text}"
                    wr = requests.get(w_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=4)
                    if wr.status_code == 200:
                        entries = wr.json().get("en", [])
                        if entries and entries[0].get("definitions"):
                            first_def = entries[0]["definitions"][0]
                            raw_def = first_def.get("definition", "")
                            definition = re.sub(r"<[^<]+?>", "", raw_def).strip()
                            if first_def.get("examples"):
                                example = re.sub(r"<[^<]+?>", "", first_def["examples"][0]).strip()
                            
                            phonetics = f"/{clean_text}/"
                            audio = f"https://translate.google.com/translate_tts?ie=UTF-8&tl=en&client=tw-ob&q={clean_text}"

                            try:
                                sr = requests.get(f"https://api.datamuse.com/words?rel_syn={clean_text}", timeout=3).json()
                                synonyms = [item["word"] for item in sr[:6]]
                            except Exception:
                                synonyms = []

                            found = True
                except Exception:
                    pass

            if found:
                context = {
                    "form": form,
                    "input": text,
                    "phonetics": phonetics,
                    "audio": audio,
                    "definition": definition,
                    "example": example,
                    "synonyms": synonyms,
                }
                return render(request, "dashboard/dictionary.html", context)
            else:
                context = {
                    "form": form,
                    "input": "",
                }
                return render(request, "dashboard/dictionary.html", context)

    context = {
        "form": form,
    }

    return render(request, "dashboard/dictionary.html", context)

@login_required
def wiki(request):
    if request.method == "POST":
        form = DashboardForm(request.POST)
        if form.is_valid():
            text = form.cleaned_data['text']
            try:
                search = wiki_api.page(text)
                context = {
                    'form': form,
                    'title': search.title,
                    'link': search.url,
                    'details': search.summary
                }
                return render(request, "dashboard/wiki.html", context)
            except wiki_api.exceptions.DisambiguationError as e:
                try:
                    search = wiki_api.page(e.options[0])
                    context = {
                        'form': form,
                        'title': search.title,
                        'link': search.url,
                        'details': search.summary
                    }
                    return render(request, "dashboard/wiki.html", context)
                except Exception:
                    context = {'form': form, 'error': 'Query too broad, please be more specific.'}
                    return render(request, "dashboard/wiki.html", context)
            except wiki_api.exceptions.PageError:
                context = {'form': form, 'error': 'No results found on Wikipedia.'}
                return render(request, "dashboard/wiki.html", context)
            except Exception:
                context = {'form': form, 'error': 'An error occurred while fetching data.'}
                return render(request, "dashboard/wiki.html", context)
    else:
        form = DashboardForm()
    
    context = {'form': form}
    return render(request, 'dashboard/wiki.html', context)

@login_required
def conversion(request):
    if request.method == "POST":
        form = ConversionForm(request.POST)
        measurement = request.POST.get('measurement')
        if measurement == 'length':
            measurement_form = ConversionLengthForm(request.POST) if 'input' in request.POST else ConversionLengthForm()
            context = {
                'form': form,
                'm_form': measurement_form,
                'input': True
            }
            if 'input' in request.POST:
                first = request.POST.get('measure1')
                second = request.POST.get('measure2')
                input_val = request.POST.get('input')
                answer = ''
                if input_val and input_val.isdigit():
                    val = int(input_val)
                    if first == 'yard' and second == 'foot':
                        answer = f'{input_val} yard = {val * 3} foot'
                    elif first == 'foot' and second == 'yard':
                        answer = f'{input_val} foot = {val / 3} yard'
                    elif first == second:
                        answer = f'{input_val} {first} = {input_val} {first}'
                context['answer'] = answer
            return render(request, 'dashboard/conversion.html', context)
        elif measurement == 'mass':
            measurement_form = ConversionMassForm(request.POST) if 'input' in request.POST else ConversionMassForm()
            context = {
                'form': form,
                'm_form': measurement_form,
                'input': True
            }
            if 'input' in request.POST:
                first = request.POST.get('measure1')
                second = request.POST.get('measure2')
                input_val = request.POST.get('input')
                answer = ''
                if input_val and input_val.isdigit():
                    val = int(input_val)
                    if first == 'pound' and second == 'kilogram':
                        answer = f'{input_val} pound = {val * 0.453592} kilogram'
                    elif first == 'kilogram' and second == 'pound':
                        answer = f'{input_val} kilogram = {val * 2.20462} pound'
                    elif first == second:
                        answer = f'{input_val} {first} = {input_val} {first}'
                context['answer'] = answer
            return render(request, 'dashboard/conversion.html', context)
    else:
        form = ConversionForm()

    context = {
        'form': form,
        'input': False
    }
    return render(request, 'dashboard/conversion.html', context)

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}!')
            return redirect('login')
    else:
        form = UserRegistrationForm()
    context = {
        'form': form
    }
    return render(request, "dashboard/register.html", context)

def logout_view(request):
    logout(request)
    return render(request, "dashboard/logout.html")

@student_required
def profile(request):
    homework = Homework.objects.filter(is_finished=False, user=request.user)
    todos = Todo.objects.filter(is_finished=False, user=request.user)
    
    homework_done = len(homework) == 0
    todos_done = len(todos) == 0
        
    context = {
        'homework': homework,
        'todos': todos,
        'homework_done': homework_done,
        'todos_done': todos_done
    }
    
    return render(request, "dashboard/profile.html", context)

@login_required
def chatbot(request):
    import google.generativeai as genai
    from django.conf import settings
    
    if request.GET.get('clear') == 'true':
        if 'chat_history' in request.session:
            del request.session['chat_history']
        return redirect('chatbot')
    
    history = request.session.get('chat_history', [])
    
    if request.method == 'POST':
        prompt = request.POST.get('prompt')
        if not prompt:
            return render(request, 'dashboard/chatbot.html', {'chat_history': history, 'error': 'Please enter a prompt.'})
            
        gemini_history = []
        for msg in history:
            gemini_history.append({
                "role": msg['role'],
                "parts": [msg['text']]
            })
            
        try:
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel('gemini-flash-latest')
            chat = model.start_chat(history=gemini_history)
            
            if not history:
                context = "You are a helpful AI tutor for a student. Provide clear, educational, and encouraging answers.\n\nStudent asks: "
                response = chat.send_message(context + prompt)
            else:
                response = chat.send_message(prompt)
            
            history.append({'role': 'user', 'text': prompt})
            history.append({'role': 'model', 'text': response.text})
            
            if len(history) > 30:
                history = history[-30:]
                
            request.session['chat_history'] = history
            
            return render(request, 'dashboard/chatbot.html', {
                'chat_history': history
            })
        except Exception as e:
            return render(request, 'dashboard/chatbot.html', {
                'chat_history': history,
                'error': f'Error connecting to AI Tutor: {str(e)}'
            })
            
    return render(request, 'dashboard/chatbot.html', {'chat_history': history})
