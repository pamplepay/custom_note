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
    path('search-customer/', views.search_customer, name='search_customer'),
    
    # 폰번호-카드 연동 관련 URL
    path('check-phone-mapping/', views.check_phone_mapping, name='check_phone_mapping'),
    
    # 카드번호 조회 관련 URL
    path('search-card-by-number/', views.search_card_by_number, name='search_card_by_number'),
    path('search-cards-by-number-partial/', views.search_cards_by_number_partial, name='search_cards_by_number_partial'),
    
    # 멤버십 카드 관리 관련 URL
    path('register-card/', views.register_card, name='register_card'),
    path('get-unused-cards/', views.get_unused_cards, name='get_unused_cards'),
    
    # 매출 관리 관련 URL
    path('sales/', views.station_sales, name='sales'),
    path('sales/upload/', views.upload_sales_data, name='upload_sales'),
    path('sales/analyze/', views.analyze_sales_file, name='analyze_sales'),
    path('sales/download-uploaded/', views.download_uploaded_file, name='download_uploaded_file'),
    path('sales/delete/file/', views.delete_sales_file, name='delete_sales_file'),
    path('sales/details/', views.get_sales_details, name='get_sales_details'),
    path('sales/statistics-list/', views.get_sales_statistics_list, name='get_sales_statistics_list'),
    path('sales/sales-list/', views.get_sales_list, name='get_sales_list'),
    
    # 날짜별 판매 데이터 조회 API
    path('get-daily-sales-data/', views.get_daily_sales_data, name='get_daily_sales_data'),
    
    # 전월 방문 고객 정보 조회 API
    path('get-previous-month-visitors/', views.get_previous_month_visitors, name='get_previous_month_visitors'),
    
    # 금월 방문 고객 정보 조회 API
    path('get-current-month-visitors/', views.get_current_month_visitors, name='get_current_month_visitors'),
    
    # 그룹 관리 관련 URL
    path('groupmanage/', views.group_management, name='groupmanage'),
    path('create-group/', views.create_group, name='create_group'),
    path('update-group/<int:group_id>/', views.update_group, name='update_group'),
    path('delete-group/<int:group_id>/', views.delete_group, name='delete_group'),
    path('get-groups/', views.get_groups, name='get_groups'),
    
    # 쿠폰 관리 관련 URL
    path('create-coupon-type/', views.create_coupon_type, name='create_coupon_type'),
    path('create-coupon-template/', views.create_coupon_template, name='create_coupon_template'),
    path('get-coupon-templates/', views.get_coupon_templates, name='get_coupon_templates'),
    path('send-coupon/', views.send_coupon, name='send_coupon'),
    
    # 방문 기록 AJAX API
    path('api/visit-history/', views.api_visit_history, name='api_visit_history'),
] 