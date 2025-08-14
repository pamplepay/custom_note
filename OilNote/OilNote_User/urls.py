from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('api/auth/check/', views.check_auth, name='check_auth'),
    path('test-sw/', views.test_sw, name='test_sw'),
    path('signup/customer/', views.CustomerSignUpView.as_view(), name='customer_signup'),
    path('signup/station/', views.StationSignUpView.as_view(), name='station_signup'),
    path('login/', views.CustomLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('password-change/', views.CustomPasswordChangeView.as_view(), name='password_change'),
] 