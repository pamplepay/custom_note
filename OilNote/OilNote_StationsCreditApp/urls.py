from django.urls import path
from . import views

app_name = 'stations_credit'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
]
