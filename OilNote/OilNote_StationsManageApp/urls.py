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
    path('delete-nozzle/', views.delete_nozzle, name='delete_nozzle'),
    path('homelori-registration/', views.homelori_registration, name='homelori_registration'),
    path('delete-homelori-vehicle/', views.delete_homelori_vehicle, name='delete_homelori_vehicle'),
    path('payment-registration/', views.payment_registration, name='payment_registration'),
    path('delete-payment-type/', views.delete_payment_type, name='delete_payment_type'),
    path('tank-inventory/', views.tank_inventory, name='tank_inventory'),
    path('dispenser-meter/', views.dispenser_meter, name='dispenser_meter'),
    path('product-inventory/', views.product_inventory, name='product_inventory'),
    path('receivables/', views.receivables, name='receivables'),
    path('customer-registration/', views.customer_registration, name='customer_registration'),
    path('vehicle-credit-registration/', views.vehicle_credit_registration, name='vehicle_credit_registration'),
    path('standard-price/', views.standard_price, name='standard_price'),
    path('factory-price/', views.factory_price, name='factory_price'),
    path('station-price/', views.station_price, name='station_price'),
    path('product-price-setting/', views.product_price_setting, name='product_price_setting'),
    path('closing-meter-data/', views.closing_meter_data, name='closing_meter_data'),
    path('daily-sales-data/', views.daily_sales_data, name='daily_sales_data'),
    path('purchase-data/', views.purchase_data, name='purchase_data'),
]
