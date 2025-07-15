from django.urls import path
from . import views

app_name = 'customer'

urlpatterns = [
    path('', views.CustomerMainView.as_view(), name='main'),
    path('records/', views.CustomerRecordsView.as_view(), name='records'),
    path('stats/', views.CustomerStatsView.as_view(), name='stats'),
    path('profile/', views.CustomerProfileView.as_view(), name='profile'),
    path('stations/', views.StationListView.as_view(), name='station_list'),
    path('stations/<int:station_id>/register/', views.register_station, name='register_station'),
    path('get-groups/', views.get_customer_groups, name='get_groups'),
] 