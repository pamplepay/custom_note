from django.urls import path
from . import views

app_name = 'customer'

urlpatterns = [
    path('', views.CustomerMainView.as_view(), name='main'),
    path('records/', views.CustomerRecordsView.as_view(), name='records'),
    path('profile/', views.CustomerProfileView.as_view(), name='profile'),
    path('coupons/', views.CustomerCouponsView.as_view(), name='coupons'),
    path('stations/', views.StationListView.as_view(), name='station_list'),
    path('stations/<int:station_id>/register/', views.register_station, name='register_station'),
    path('get-groups/', views.get_customer_groups, name='get_groups'),
    path('check-location-coupons/', views.check_location_coupons, name='check_location_coupons'),
] 