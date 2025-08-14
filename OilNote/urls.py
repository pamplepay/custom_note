from django.contrib import admin
from django.urls import path, include
from django.shortcuts import render, redirect
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from OilNote_User.views import reset_password_admin

# Swagger 스키마 뷰 설정
schema_view = get_schema_view(
    openapi.Info(
        title="Oil Note API",
        default_version='v1',
        description="Oil Note 서비스의 API 문서입니다.",
        terms_of_service="https://www.google.com/policies/terms/",
        contact=openapi.Contact(email="contact@oilnote.com"),
        license=openapi.License(name="BSD License"),
    ),
    public=True,
    permission_classes=(permissions.AllowAny,),
)

def home(request):
    if request.user.is_authenticated:
        if request.user.user_type == 'CUSTOMER':
            return redirect('customer:main')
        elif request.user.user_type == 'STATION':
            return redirect('station:main')
    return render(request, 'home.html')

urlpatterns = [
    path('', home, name='home'),
    path('admin/reset-password/<int:user_id>/', reset_password_admin, name='admin_reset_password'),
    path('admin/', admin.site.urls),
    path('users/', include('OilNote_User.urls')),
    path('customer/', include('Cust_main.urls')),
    path('station/', include('Cust_Station.urls')),
    
    # Swagger URL
    path('swagger<format>/', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

# 개발 환경에서만 미디어 파일 서빙
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) 