from django.urls import path
from . import views

app_name = 'station'

urlpatterns = [
    path('', views.station_main, name='main'),
    path('management/', views.station_management, name='management'),
    path('profile/', views.station_profile, name='profile'),
    path('cardmanage/', views.station_cardmanage, name='cardmanage'),
    path('usermanage/', views.station_usermanage, name='usermanage'),
    path('update-customer-info/', views.update_customer_info, name='update_customer_info'),
    path('couponmanage/', views.station_couponmanage, name='couponmanage'),
    
    # 카드 관리 API
    path('get-cards/', views.get_cards, name='get_cards'),
    path('get-unused-cards/', views.get_unused_cards, name='get_unused_cards'),
    path('register-customer/', views.register_customer, name='register_customer'),
    path('register-cards-bulk/', views.register_cards_bulk, name='register_cards_bulk'),
    path('register-cards-single/', views.register_cards_single, name='register_cards_single'),
    path('update-card-status/', views.update_card_status, name='update_card_status'),
    path('delete-card/', views.delete_card, name='delete_card'),
    path('delete-customer/', views.delete_customer, name='delete_customer'),
    path('check-customer/', views.check_customer_exists, name='check_customer'),
    
    # 멤버십 카드 관리 관련 URL
    path('register-card/', views.register_card, name='register_card'),
    path('get-unused-cards/', views.get_unused_cards, name='get_unused_cards'),
] 