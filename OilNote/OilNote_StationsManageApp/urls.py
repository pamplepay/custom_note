from django.urls import path
from . import views

app_name = 'stations_manage'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('business-registration/', views.business_registration, name='business_registration'),
] 