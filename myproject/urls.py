"""
URL configuration for pickleball project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include

from apps.team import views
from django.shortcuts import render

def index(req):
    return render(req, "index/index.html")

def privacy_policy(req):
    return render(req, "index/privacy-policy.html")

def terms_conditions(req):
    return render(req, "index/terms-conditions.html")

urlpatterns = [
    path('', index, name="index"),
    path('privacy_policy/', privacy_policy, name="privacy_policy"),
    path('terms_conditions/', terms_conditions, name="terms_conditions"),
    path('pickleit-admin-main/', admin.site.urls),
    path('api_list/', views.api_list,name="api_list"),
    path('user/', include('apps.user.urls')),
    path('team/', include('apps.team.urls')),
    path('accessories/', include('apps.pickleitcollection.urls')),
    path('chat/', include('apps.chat.urls')),
    path('admin/', include('apps.admin_side.urls')),
    path('accessories/', include('apps.store.urls')),
]


if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)