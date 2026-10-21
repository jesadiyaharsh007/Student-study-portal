from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name="home"),
    path('about/', views.about, name="about"),
    path('privacy/', views.privacy, name="privacy"),
    path('terms/', views.terms, name="terms"),
    path('notes/', views.notes, name="notes"),
    path('delete_note/<int:pk>', views.delete_note, name="delete-note"),
    path('notes_detail/<int:pk>', views.NoteDetailview.as_view(), name="notes-detail"),

    path('homework/', views.homework, name="homework"),
    path('update_homework/<int:pk>', views.update_homework, name="update-homework"),
    path('delete_homework/<int:pk>', views.delete_homework, name="delete-homework"),

    path('youtube/', views.youtube, name="youtube"),
    path('youtube/watch/<str:video_id>/', views.youtube_watch, name="youtube-watch"),
    path('youtube/lexi/', views.youtube_lexi, name="youtube-lexi"),
    path('youtube/stream/<str:video_id>/', views.youtube_stream, name="youtube-stream"),
    path('youtube/media/<str:video_id>/<str:itag>/', views.youtube_media, name="youtube-media"),
    path('youtube/download/<str:video_id>/<str:kind>/', views.youtube_download, name="youtube-download"),
    path('youtube/captions/<str:video_id>/', views.youtube_captions, name="youtube-captions"),
    path('youtube/captions/<str:video_id>/<str:lang>/', views.youtube_captions, name="youtube-caption-cues"),

    path('todo/', views.todo, name="todo"),
    path('update_todo/<int:pk>', views.update_todo, name="update-todo"),
    path('delete_todo/<int:pk>', views.delete_todo, name="delete-todo"),

    path('books/', views.books, name="books"),
    path('books/read/<int:pg_id>/', views.book_read, name="book-read"),
    path('books/read/<int:pg_id>/data/', views.book_data, name="book-data"),

    path('dictionary/', views.dictionary, name="dictionary"),

    path('wiki/', views.wiki, name="wiki"),
    path('conversion/', views.conversion, name="conversion"),
    path('chatbot/', views.chatbot, name="chatbot"),
    path('profile/', views.profile, name="profile"),
]