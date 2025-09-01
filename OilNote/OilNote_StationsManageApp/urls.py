from django.urls import path
from . import views

app_name = 'stations_manage'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('business-registration/', views.business_registration, name='business_registration'),
    path('delete-business-info/', views.delete_business_info, name='delete_business_info'),
    path('product-registration/', views.product_registration, name='product_registration'),
    path('delete-product/', views.delete_product, name='delete_product'),
    path('tank-registration/', views.tank_registration, name='tank_registration'),
    path('delete-tank/', views.delete_tank, name='delete_tank'),
    path('nozzle-registration/', views.nozzle_registration, name='nozzle_registration'),
    path('homelori-registration/', views.homelori_registration, name='homelori_registration'),
    path('payment-registration/', views.payment_registration, name='payment_registration'),
] 