"""
URL configuration for OilNote project.

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

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.views.static import serve
from django.conf.urls.static import static
from django.shortcuts import render, redirect
import os

def home(request):
    # 로그인한 사용자는 해당 메인 페이지로 리다이렉트
    if request.user.is_authenticated:
        # 어드민 계정(슈퍼유저)인 경우 OilNote_AdminApp 대시보드로 이동
        if request.user.is_superuser:
            return redirect('admin_panel:admin_dashboard')
        elif request.user.user_type == 'CUSTOMER':
            return redirect('customer:main')
        elif request.user.user_type == 'STATION':
            return redirect('station:main')
    
    return render(request, 'home.html')

urlpatterns = [
    path('', home, name='home'),
    path('admin/', admin.site.urls),
    path('station/', include('OilNote_StationApp.urls')),
    path('user/', include('OilNote_User.urls')),
    path('customer/', include('OilNote_UserApp.urls')),
    path('admin-panel/', include('OilNote_AdminApp.urls')),
    path('ftp/', include('ftp_data_loader.urls')),
    
    # Favicon
    path('favicon.ico', serve, {
        'path': 'favicon.ico',
        'document_root': os.path.join(settings.STATIC_ROOT, '')
    }),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
