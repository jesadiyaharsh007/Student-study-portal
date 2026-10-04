from django.contrib import admin
from django.urls import path, include
from dashboard import views as dash_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('dashboard.urls')),
    path('register/', dash_views.register, name="register"),
    path('login/', dash_views.login_view, name="login"),
    path('logout/', dash_views.logout_view, name="logout"),
]
