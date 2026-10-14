from django.contrib import admin
from django.http import HttpResponse
from django.urls import path, include
from dashboard import views as dash_views

urlpatterns = [
    path('favicon.ico', lambda request: HttpResponse(status=204)),
    path('admin/', admin.site.urls),
    path('', include('dashboard.urls')),
    path('register/', dash_views.register, name="register"),
    path('login/', dash_views.login_view, name="login"),
    path('logout/', dash_views.logout_view, name="logout"),
]

handler400 = 'dashboard.views.handler400'
handler403 = 'dashboard.views.handler403'
handler404 = 'dashboard.views.handler404'
handler500 = 'dashboard.views.handler500'
