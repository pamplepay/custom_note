from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, FileResponse
from django.contrib import messages
from django.db.models import Q, Sum
from Cust_User.models import CustomUser, CustomerProfile, CustomerStationRelation
from .models import PointCard, StationCardMapping, SalesData, ExcelSalesData, MonthlySalesStatistics, SalesStatistics, Group, PhoneCardMapping, CouponType, CouponTemplate, CustomerCoupon
from datetime import datetime, timedelta
import json
import logging
import re
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.db.transaction import TransactionManagementError
from django.views.decorators.http import require_http_methods, require_GET
from django.views.decorators.csrf import csrf_exempt
import os
from django.conf import settings
from django.db.utils import IntegrityError
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from decimal import Decimal

logger = logging.getLogger(__name__)


def update_monthly_statistics(tid, sale_date, daily_transactions, daily_quantity, daily_amount, daily_avg_price, top_product, top_product_count, product_counts, product_amounts=None):
    """월별 누적 매출 통계 업데이트 (월 전체 데이터 합산)"""
    year_month = sale_date.strftime('%Y-%m')
    # 해당 월의 모든 날짜별 SalesStatistics 합산
    stats = SalesStatistics.objects.filter(
        tid=tid,
        sale_date__startswith=year_month
    )
    total_transactions = stats.aggregate(Sum('total_transactions'))['total_transactions__sum'] or 0
    total_quantity = stats.aggregate(Sum('total_quantity'))['total_quantity__sum'] or 0
    total_amount = stats.aggregate(Sum('total_amount'))['total_amount__sum'] or 0
    avg_unit_price = (Decimal(str(total_amount)) / Decimal(str(total_quantity))) if total_quantity else Decimal('0')
    # 제품별 집계 (ExcelSalesData에서 월 전체 데이터 집계)
    excel_rows = ExcelSalesData.objects.filter(
        tid=tid,
        sale_date__startswith=year_month
    )
    product_counts = {}
    product_quantities = {}
    product_amounts = {}
    for row in excel_rows:
        product = (row.product_pack or '').strip()
        if not product:
            continue
        product_counts[product] = product_counts.get(product, 0) + 1
        product_quantities[product] = product_quantities.get(product, 0) + float(row.quantity or 0)
        product_amounts[product] = product_amounts.get(product, 0) + float(row.total_amount or 0)
    # 월별 통계 덮어쓰기
    monthly_stat, created = MonthlySalesStatistics.objects.get_or_create(
        tid=tid,
        year_month=year_month,
        defaults={
            'total_transactions': 0,
            'total_quantity': Decimal('0'),
            'total_amount': Decimal('0'),
            'avg_unit_price': Decimal('0'),
            'top_product': '',
            'top_product_count': 0,
            'product_breakdown': {},
            'product_sales_count': {},
            'product_sales_quantity': {},
            'product_sales_amount': {},
        }
    )
    monthly_stat.total_transactions = int(total_transactions)
    monthly_stat.total_quantity = Decimal(str(total_quantity))
    monthly_stat.total_amount = Decimal(str(total_amount))
    monthly_stat.avg_unit_price = avg_unit_price
    monthly_stat.product_breakdown = {}
    monthly_stat.product_sales_count = product_counts
    monthly_stat.product_sales_quantity = product_quantities
    monthly_stat.product_sales_amount = product_amounts
    # 최다 판매 제품
    if product_counts:
        top_product_monthly = max(product_counts.items(), key=lambda x: x[1])
        monthly_stat.top_product = top_product_monthly[0]
        monthly_stat.top_product_count = top_product_monthly[1]
    else:
        monthly_stat.top_product = ''
        monthly_stat.top_product_count = 0
    monthly_stat.save()


@login_required
def station_main(request):
    """주유소 메인 페이지"""
    if not request.user.is_station:
        messages.error(request, '주유소 회원만 접근할 수 있습니다.')
        return redirect('home')
    
    # 카드 통계
    total_cards = StationCardMapping.objects.filter(station=request.user, tid=request.user.station_profile.tid, is_active=True).count()
    active_cards = StationCardMapping.objects.filter(station=request.user, tid=request.user.station_profile.tid, card__is_used=False).count()
    inactive_cards = StationCardMapping.objects.filter(station=request.user, tid=request.user.station_profile.tid, card__is_used=True).count()
    
    # VIP 고객수 (현재 주유소에 등록된 고객수)
    total_customers = CustomerStationRelation.objects.filter(station=request.user, is_active=True).count()
    
    # 전월/금월 방문횟수 및 주유금액 계산
    from datetime import datetime
    from django.utils import timezone
    from Cust_UserApp.models import CustomerVisitHistory
    
    current_month = timezone.now().month
    current_year = timezone.now().year
    
    # 이전 월 계산
    if current_month == 1:
        previous_month = 12
        previous_year = current_year - 1
    else:
        previous_month = current_month - 1
        previous_year = current_year
    
    # 금월 방문횟수 및 주유금액
    current_month_visits = CustomerVisitHistory.objects.filter(
        station=request.user,
        visit_date__year=current_year,
        visit_date__month=current_month
    )
    current_month_visitors = current_month_visits.count()
    current_month_amount = current_month_visits.aggregate(
        total_amount=Sum('sale_amount')
    )['total_amount'] or 0
    # 소수점 이하 제거
    current_month_amount = int(current_month_amount) if current_month_amount else 0
    
    # 전월 방문횟수 및 주유금액
    previous_month_visits = CustomerVisitHistory.objects.filter(
        station=request.user,
        visit_date__year=previous_year,
        visit_date__month=previous_month
    )
    previous_month_visitors = previous_month_visits.count()
    previous_month_amount = previous_month_visits.aggregate(
        total_amount=Sum('sale_amount')
    )['total_amount'] or 0
    # 소수점 이하 제거
    previous_month_amount = int(previous_month_amount) if previous_month_amount else 0
    
    # 월별 매출 통계 데이터 가져오기
    monthly_stats = None
    try:
        from .models import MonthlySalesStatistics
        from datetime import datetime
        
        # TID 가져오기
        tid = getattr(getattr(request.user, 'station_profile', None), 'tid', None)
        if tid:
            current_month_str = timezone.now().strftime('%Y-%m')
            previous_month_str = (timezone.now().replace(day=1) - timedelta(days=1)).strftime('%Y-%m')
            
            # 현재 월 통계
            current_monthly = MonthlySalesStatistics.objects.filter(
                tid=tid,
                year_month=current_month_str
            ).first()
            
            # 이전 월 통계
            previous_monthly = MonthlySalesStatistics.objects.filter(
                tid=tid,
                year_month=previous_month_str
            ).first()
            
            # 많이 팔린 상품 3가지 추출 함수 (판매 횟수 기준)
            def get_top_products(monthly_data, count=3):
                if not monthly_data or not monthly_data.product_sales_count:
                    return []
                
                # 판매 횟수 기준으로 정렬
                sorted_products = sorted(
                    monthly_data.product_sales_count.items(),
                    key=lambda x: x[1],
                    reverse=True
                )
                return sorted_products[:count]
            
            # 많이 팔린 상품 3가지 추출 함수 (판매 금액 기준)
            def get_top_products_by_amount(monthly_data, count=3):
                if not monthly_data or not monthly_data.product_sales_amount:
                    return []
                
                # 판매 금액 기준으로 정렬
                sorted_products = sorted(
                    monthly_data.product_sales_amount.items(),
                    key=lambda x: x[1],
                    reverse=True
                )
                return sorted_products[:count]
            
            # 전월과 금월의 많이 팔린 상품 3가지 (판매 횟수 기준)
            previous_top_products = get_top_products(previous_monthly)
            current_top_products = get_top_products(current_monthly)
            
            # 전월과 금월의 많이 팔린 상품 3가지 (판매 금액 기준)
            previous_top_products_by_amount = get_top_products_by_amount(previous_monthly)
            current_top_products_by_amount = get_top_products_by_amount(current_monthly)
            
            # DM 값 계산 (200리터 = 1DM)
            current_month_dm = float(current_monthly.total_quantity) / 200 if current_monthly else 0
            previous_month_dm = float(previous_monthly.total_quantity) / 200 if previous_monthly else 0
            
            monthly_stats = {
                'current_month': current_monthly,
                'previous_month': previous_monthly,
                'current_month_str': current_month_str,
                'previous_month_str': previous_month_str,
                'previous_top_products': previous_top_products,
                'current_top_products': current_top_products,
                'previous_top_products_by_amount': previous_top_products_by_amount,
                'current_top_products_by_amount': current_top_products_by_amount,
                'current_month_dm': current_month_dm,
                'previous_month_dm': previous_month_dm
            }
    except Exception as e:
        logger.error(f"월별 통계 데이터 조회 중 오류: {str(e)}")
    
    context = {
        'total_cards': total_cards,
        'active_cards': active_cards,
        'inactive_cards': inactive_cards,
        'total_customers': total_customers,
        'monthly_stats': monthly_stats,
        'current_month_visitors': current_month_visitors,
        'previous_month_visitors': previous_month_visitors,
        'current_month_amount': current_month_amount,
        'previous_month_amount': previous_month_amount,
    }
    return render(request, 'Cust_Station/station_main.html', context)


@login_required
def get_daily_sales_data(request):
    """날짜별 판매 데이터 조회 (AJAX)"""
    if not request.user.is_station:
        return JsonResponse({'error': '주유소 회원만 접근할 수 있습니다.'}, status=403)
    
    try:
        from .models import SalesStatistics, MonthlySalesStatistics, ExcelSalesData
        from datetime import datetime
        
        # TID 가져오기
        tid = getattr(getattr(request.user, 'station_profile', None), 'tid', None)
        if not tid:
            return JsonResponse({'error': 'TID가 설정되지 않았습니다.'}, status=400)
        
        # 요청 파라미터
        month_str = request.GET.get('month')  # YYYY-MM 형식
        data_type = request.GET.get('type')  # 'quantity' 또는 'amount'
        
        if not month_str or not data_type:
            return JsonResponse({'error': '필수 파라미터가 누락되었습니다.'}, status=400)
        
        # 해당 월의 날짜별 데이터 조회 (최근 날짜부터 정렬)
        daily_stats = SalesStatistics.objects.filter(
            tid=tid,
            sale_date__startswith=month_str
        ).order_by('-sale_date')
        
        # 해당 월의 월별 통계 데이터 조회 (상위 제품 정보용)
        monthly_stat = MonthlySalesStatistics.objects.filter(
            tid=tid,
            year_month=month_str
        ).first()
        
        # 데이터 형식화
        daily_data = []
        for stat in daily_stats:
            if data_type == 'quantity':
                value = stat.total_quantity
                unit = 'L'
            else:  # amount
                value = stat.total_amount
                unit = '원'
            
            daily_data.append({
                'date': stat.sale_date.strftime('%Y-%m-%d'),
                'value': float(value),
                'unit': unit
            })
        
        # 상위 2개 제품 정보 추출
        top_products = []
        if monthly_stat and monthly_stat.product_sales_count:
            if data_type == 'quantity':
                # 판매 수량 기준으로 상위 2개 제품 추출
                sorted_products = sorted(
                    monthly_stat.product_sales_quantity.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:2] if monthly_stat.product_sales_quantity else []
                
                for product, quantity in sorted_products:
                    # 해당 제품의 판매 횟수 조회
                    count = monthly_stat.product_sales_count.get(product, 0) if monthly_stat.product_sales_count else 0
                    top_products.append({
                        'product': product,
                        'count': count,
                        'quantity': float(quantity)
                    })
            else:  # amount
                # 판매 금액 기준으로 상위 2개 제품 추출
                sorted_products = sorted(
                    monthly_stat.product_sales_amount.items(),
                    key=lambda x: x[1],
                    reverse=True
                )[:2] if monthly_stat.product_sales_amount else []
                
                for product, amount in sorted_products:
                    # 해당 제품의 판매 횟수와 수량 조회
                    count = monthly_stat.product_sales_count.get(product, 0) if monthly_stat.product_sales_count else 0
                    quantity = monthly_stat.product_sales_quantity.get(product, 0) if monthly_stat.product_sales_quantity else 0
                    top_products.append({
                        'product': product,
                        'count': count,
                        'quantity': float(quantity),
                        'amount': float(amount)
                    })
        
        # 각 날짜별로 상위 2개 제품의 실제 판매 현황 계산
        daily_product_stats = []
        for stat in daily_stats:
            # 해당 날짜의 모든 ExcelSalesData 조회
            rows = ExcelSalesData.objects.filter(
                tid=stat.tid,
                sale_date=stat.sale_date
            )
            # 제품별 집계
            product_counts = {}
            product_quantities = {}
            product_amounts = {}
            for row in rows:
                product = (row.product_pack or '').strip()
                if not product:
                    continue
                product_counts[product] = product_counts.get(product, 0) + 1
                product_quantities[product] = product_quantities.get(product, 0) + float(row.quantity or 0)
                product_amounts[product] = product_amounts.get(product, 0) + float(row.total_amount or 0)
            
            # data_type에 따라 상위 2개 제품 추출
            if data_type == 'quantity':
                # 판매 수량 기준
                top2 = sorted(product_quantities.items(), key=lambda x: x[1], reverse=True)[:2]
            else:  # amount
                # 판매 금액 기준
                top2 = sorted(product_amounts.items(), key=lambda x: x[1], reverse=True)[:2]
            
            products = []
            for product_name, value in top2:
                count = product_counts.get(product_name, 0)
                quantity = product_quantities.get(product_name, 0)
                amount = product_amounts.get(product_name, 0)
                products.append({
                    'product': product_name,
                    'count': count,
                    'quantity': float(quantity),
                    'amount': float(amount)
                })
            daily_product_stats.append({
                'date': stat.sale_date.strftime('%Y-%m-%d'),
                'products': products
            })
        
        return JsonResponse({
            'success': True,
            'data': daily_data,
            'month': month_str,
            'type': data_type,
            'top_products': top_products,
            'daily_product_stats': daily_product_stats
        })
        
    except Exception as e:
        logger.error(f"날짜별 판매 데이터 조회 중 오류: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': f'데이터 조회 중 오류가 발생했습니다: {str(e)}'
        }, status=500)

@login_required
def station_management(request):
    """주유소 관리 페이지"""
    if not request.user.is_station:
        messages.error(request, '주유소 회원만 접근할 수 있습니다.')
        return redirect('home')
    
    # 현재 주유소의 카드 매핑 수 조회
    mappings = StationCardMapping.objects.filter(station=request.user, tid=request.user.station_profile.tid, is_active=True)
    total_cards = mappings.count()
    active_cards = mappings.filter(card__is_used=False).count()
    inactive_cards = mappings.filter(card__is_used=True).count()
    
    # 비율 계산
    active_percentage = (active_cards / total_cards * 100) if total_cards > 0 else 0
    inactive_percentage = (inactive_cards / total_cards * 100) if total_cards > 0 else 0
    
    context = {
        'total_cards': total_cards,
        'active_cards': active_cards,
        'inactive_cards': inactive_cards,
        'active_percentage': active_percentage,
        'inactive_percentage': inactive_percentage,
    }
    
    return render(request, 'Cust_Station/station_management.html', context)

@login_required
def station_profile(request):
    """
    주유소 프로필 페이지 (신규 TID 입력 및 TID 변경 시 데이터 연동)
    - GET: 프로필 정보 표시
    - POST: 프로필 정보 수정, TID 변경 시 기존 TID의 모든 데이터 tid를 신규 TID로 일괄 업데이트
    """
    if not request.user.is_station:
        messages.error(request, '주유소 회원만 접근할 수 있습니다.')
        return redirect('home')
    # 현재 주유소 프로필 가져오기 또는 생성
    try:
        station_profile = request.user.station_profile
    except:
        from Cust_User.models import StationProfile
        station_profile = StationProfile(user=request.user)
        station_profile.save()
    old_tid = station_profile.tid
    if request.method == 'POST':
        # POST 요청 처리
        station_profile.station_name = request.POST.get('station_name')
        station_profile.phone = request.POST.get('phone')
        station_profile.address = request.POST.get('address')
        station_profile.business_number = request.POST.get('business_number')
        station_profile.oil_company_code = request.POST.get('oil_company_code')
        station_profile.agency_code = request.POST.get('agency_code')
        new_tid = request.POST.get('tid')
        tid_changed = old_tid and new_tid and old_tid != new_tid
        station_profile.tid = new_tid
        try:
            station_profile.save()
            # TID가 변경된 경우 기존 TID의 모든 데이터 tid를 신규 TID로 일괄 업데이트
            if tid_changed:
                from django.db import transaction
                from .models import StationCardMapping, SalesData, ExcelSalesData, SalesStatistics, MonthlySalesStatistics
                from Cust_UserApp.models import CustomerVisitHistory
                with transaction.atomic():
                    StationCardMapping.objects.filter(tid=old_tid).update(tid=new_tid)
                    ExcelSalesData.objects.filter(tid=old_tid).update(tid=new_tid)
                    SalesStatistics.objects.filter(tid=old_tid).update(tid=new_tid)
                    MonthlySalesStatistics.objects.filter(tid=old_tid).update(tid=new_tid)
                    CustomerVisitHistory.objects.filter(tid=old_tid).update(tid=new_tid)
                messages.success(request, f'TID가 {old_tid} → {new_tid}로 변경되었고, 기존 데이터가 모두 연동되었습니다.')
            else:
                messages.success(request, '주유소 정보가 성공적으로 업데이트되었습니다.')
            return redirect('station:profile')
        except Exception as e:
            messages.error(request, f'정보 업데이트 중 오류가 발생했습니다: {str(e)}')
    # GET 요청 처리
    context = {
        'station_name': station_profile.station_name,
        'phone': station_profile.phone,
        'address': station_profile.address,
        'business_number': station_profile.business_number,
        'oil_company_code': station_profile.oil_company_code,
        'agency_code': station_profile.agency_code,
        'tid': station_profile.tid,
    }
    return render(request, 'Cust_Station/station_profile.html', context)

@login_required
def station_cardmanage(request):
    """주유소 카드 관리 페이지"""
    if not request.user.is_station:
        messages.error(request, '주유소 회원만 접근할 수 있습니다.')
        return redirect('home')
    
    # 현재 주유소의 카드 매핑 수 조회
    mappings = StationCardMapping.objects.filter(station=request.user, tid=request.user.station_profile.tid, is_active=True)
    total_cards = mappings.count()
    
    # 카드 상태별 통계
    active_cards = mappings.filter(card__is_used=False).count()
    used_cards = mappings.filter(card__is_used=True).count()
    
    # 비율 계산
    active_percentage = (active_cards / total_cards * 100) if total_cards > 0 else 0
    used_percentage = (used_cards / total_cards * 100) if total_cards > 0 else 0
    
    # 최근 등록된 카드 3장 가져오기
    recent_cards = StationCardMapping.objects.select_related('card').filter(
        station=request.user,
        tid=request.user.station_profile.tid,
        is_active=True
    ).order_by('-registered_at')[:3]
    
    cards_data = []
    for mapping in recent_cards:
        card = mapping.card
        cards_data.append({
            'number': card.number,
            'is_used': card.is_used,
            'created_at': mapping.registered_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    # 주유소 TID 가져오기
    station_tid = None
    if hasattr(request.user, 'station_profile'):
        station_tid = request.user.station_profile.tid
        if not station_tid:
            messages.warning(request, '주유소 단말기 번호(TID)가 설정되어 있지 않습니다. 관리자에게 문의하세요.')
    
    context = {
        'total_cards': total_cards,
        'active_cards': active_cards,
        'used_cards': used_cards,
        'active_percentage': active_percentage,
        'used_percentage': used_percentage,
        'station_name': request.user.username,
        'recent_cards': cards_data,
        'station_tid': station_tid
    }
    
    return render(request, 'Cust_Station/station_cardmanage.html', context)

@login_required
def station_usermanage(request):
    """고객 관리 페이지"""
    if not request.user.is_station:
        return redirect('home')
    
    # 페이지네이션 설정
    page = request.GET.get('page', 1)
    search_query = request.GET.get('search', '')
    
    # 회원가입 여부에 따른 고객 분류
    # 1. 회원가입한 고객 (CustomerStationRelation에서 조회)
    registered_customers = CustomerStationRelation.objects.filter(
        station=request.user
    ).select_related(
        'customer',
        'customer__customer_profile'
    ).order_by('-created_at')
    
    # 2. 미회원가입 고객 (PhoneCardMapping에서 조회)
    from .models import PhoneCardMapping
    unregistered_mappings = PhoneCardMapping.objects.filter(
        station=request.user,
        is_used=False  # 회원가입하지 않은 고객
    ).select_related('membership_card').order_by('-created_at')
    
    # 검색 필터링
    if search_query:
        # 회원가입한 고객 검색
        registered_customers = registered_customers.filter(
            Q(customer__username__icontains=search_query) |
            Q(customer__customer_profile__customer_phone__icontains=search_query) |
            Q(customer__customer_profile__membership_card__icontains=search_query)
        )
        
        # 미회원가입 고객 검색
        unregistered_mappings = unregistered_mappings.filter(
            Q(phone_number__icontains=search_query) |
            Q(membership_card__number__icontains=search_query)
        )
    
    # 페이지네이터 설정 (회원가입한 고객만 페이지네이션 적용)
    paginator = Paginator(registered_customers, 10)  # 페이지당 10개
    
    try:
        current_page = paginator.page(page)
    except PageNotAnInteger:
        current_page = paginator.page(1)
    except EmptyPage:
        current_page = paginator.page(paginator.num_pages)
    
    # 페이지 범위 계산
    page_range = range(
        max(1, current_page.number - 2),
        min(paginator.num_pages + 1, current_page.number + 3)
    )
    
    # 이번달 방문 고객 수 계산
    from datetime import datetime
    from django.utils import timezone
    current_month = timezone.now().month
    current_year = timezone.now().year
    
    from Cust_UserApp.models import CustomerVisitHistory
    this_month_visitors = CustomerVisitHistory.objects.filter(
        station=request.user,
        visit_date__year=current_year,
        visit_date__month=current_month
    ).values('customer').distinct().count()
    
    # 회원가입한 고객 데이터 가공
    registered_customers_data = []
    for relation in current_page:
        customer = relation.customer
        profile = customer.customer_profile
        
        # 고객 방문 기록 조회
        visit_history = CustomerVisitHistory.objects.filter(
            customer=customer,
            station=request.user
        ).order_by('-visit_date', '-visit_time')
        
        # 총 방문 횟수
        total_visit_count = visit_history.count()
        
        # 최근 방문 날짜
        last_visit = None
        if visit_history.exists():
            latest_visit = visit_history.first()
            last_visit = f"{latest_visit.visit_date.strftime('%Y-%m-%d')} {latest_visit.visit_time.strftime('%H:%M')}"
        
        # 총 주유 금액 계산 (방문 기록에서 실제 주유 금액 합산)
        total_fuel_amount = 0
        if visit_history.exists():
            total_fuel_amount = sum(visit.sale_amount for visit in visit_history if visit.sale_amount)
        
        registered_customers_data.append({
            'id': customer.id,
            'customer': customer,  # 고객 객체 추가
            'phone': profile.customer_phone,
            'card_number': profile.membership_card,
            'last_visit': last_visit,
            'total_visit_count': total_visit_count,
            'total_fuel_amount': total_fuel_amount,
            'created_at': relation.created_at,
            'is_registered': True
        })
    
    # 방문 횟수 기준 내림차순 정렬
    registered_customers_data.sort(key=lambda x: x['total_visit_count'], reverse=True)
    
    # 미회원가입 고객 데이터 가공
    unregistered_customers_data = []
    for mapping in unregistered_mappings:
        unregistered_customers_data.append({
            'id': f"unreg_{mapping.id}",  # 고유 ID 생성
            'phone': mapping.phone_number,
            'card_number': mapping.membership_card.full_number,
            'car_number': mapping.car_number,  # 차량 번호 추가
            'last_visit': None,
            'total_visit_count': 0,
            'total_fuel_amount': 0,
            'created_at': mapping.created_at,
            'is_registered': False
        })
    
    context = {
        'registered_customers': registered_customers_data,
        'unregistered_customers': unregistered_customers_data,
        'current_page': int(page),
        'total_pages': paginator.num_pages,
        'page_range': page_range,
        'search_query': search_query,
        'station_tid': request.user.station_profile.tid if hasattr(request.user, 'station_profile') else None,
        'this_month_visitors': this_month_visitors,
        'total_registered_count': registered_customers.count(),
        'total_unregistered_count': unregistered_mappings.count()
    }
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(context)
    
    return render(request, 'Cust_Station/station_usermanage.html', context)

@login_required
def update_customer_info(request):
    """고객 정보 업데이트"""
    if not request.user.is_station:
        return JsonResponse({'error': '권한이 없습니다.'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            customer_id = data.get('customer_id')
            phone = data.get('phone', '').strip()
            card_number = data.get('cardNumber', '').strip()
            
            customer = get_object_or_404(CustomUser, id=customer_id, user_type='CUSTOMER')
            
            # CustomerProfile 가져오기 또는 생성
            profile, created = CustomerProfile.objects.get_or_create(user=customer)
            
            # 전화번호와 카드번호 업데이트
            if phone:
                profile.customer_phone = phone
            if card_number:
                profile.membership_card = card_number
            
            profile.save()
            
            return JsonResponse({
                'success': True,
                'message': '고객 정보가 업데이트되었습니다.',
                'phone': profile.customer_phone,
                'cardNumber': profile.membership_card
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': '잘못된 요청 형식입니다.'}, status=400)
        except CustomUser.DoesNotExist:
            return JsonResponse({'error': '고객을 찾을 수 없습니다.'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': '잘못된 요청 방식입니다.'}, status=405)

@login_required
def get_cards(request):
    """등록된 카드 목록 조회"""
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 접근 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        # 현재 주유소에 등록된 카드 매핑 조회
        mappings = StationCardMapping.objects.select_related('card').filter(
            station=request.user,
            tid=request.user.station_profile.tid,
            is_active=True
        ).order_by('-registered_at')
        
        # 전체 카드 수 계산 (캐시되지 않도록 실제 쿼리 실행)
        total_count = mappings.count()
        logger.info(f"주유소 {request.user.username}의 등록 카드 수: {total_count}")
        
        # 카드 상태별 수 계산 (캐시되지 않도록 실제 쿼리 실행)
        active_count = mappings.filter(card__is_used=False).count()
        used_count = mappings.filter(card__is_used=True).count()
        
        logger.info(f"통계 정보 - 전체: {total_count}, 사용가능: {active_count}, 사용중: {used_count}")
        
        # 카드 목록 데이터 생성
        cards_data = []
        for mapping in mappings:
            card = mapping.card
            card_info = {
                'number': card.number,
                'is_used': card.is_used,
                'created_at': mapping.registered_at.strftime('%Y-%m-%d %H:%M:%S')
            }
            cards_data.append(card_info)
            logger.debug(f"카드 정보: {card_info}")
        
        return JsonResponse({
            'status': 'success',
            'cards': cards_data,
            'total_count': total_count,
            'active_count': active_count,
            'used_count': used_count
        })
    except Exception as e:
        logger.error(f"카드 목록 조회 중 오류 발생: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
@csrf_exempt
def register_cards_single(request):
    """카드 개별 등록"""
    logger.info(f"개별 카드 등록 요청 - 사용자: {request.user.username}, 메소드: {request.method}")
    
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 카드 등록 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    if request.method == 'POST':
        try:
            logger.info(f"요청 본문: {request.body.decode('utf-8')}")
            data = json.loads(request.body)
            card_number = data.get('cardNumber', '').strip()
            tid = data.get('tid', '').strip()  # TID 값 추가
            logger.info(f"추출된 카드번호: '{card_number}', TID: '{tid}'")
            
            # 입력 검증
            if not card_number or len(card_number) != 16 or not card_number.isdigit():
                logger.warning(f"잘못된 카드번호 형식: '{card_number}' (길이: {len(card_number) if card_number else 0})")
                return JsonResponse({
                    'status': 'error',
                    'message': '카드번호는 16자리 숫자여야 합니다.'
                })
            
            if not tid:
                logger.warning("TID가 제공되지 않음")
                return JsonResponse({
                    'status': 'error',
                    'message': 'TID는 필수 입력값입니다.'
                })
            
            logger.info(f"카드 생성 시도: {card_number}")
            # get_or_create를 사용하여 중복 생성 방지
            card, created = PointCard.objects.get_or_create(
                number=card_number,
                defaults={'tids': []}
            )
            logger.info(f"카드 생성 결과: created={created}, card_id={card.id}")
            
            # TID 추가
            if tid not in card.tids:
                card.add_tid(tid)
                logger.info(f"카드에 TID 추가: {tid}")
            
            # 카드와 주유소 매핑 생성
            logger.info(f"매핑 생성 시도: 주유소={request.user.username}, 카드={card_number}")
            mapping, mapping_created = StationCardMapping.objects.get_or_create(
                station=request.user,
                tid=tid,
                card=card,
                defaults={'is_active': True}
            )
            logger.info(f"매핑 생성 결과: created={mapping_created}, mapping_id={mapping.id}")
            
            # 이미 매핑이 존재하지만 비활성화된 경우 활성화
            if not mapping_created and not mapping.is_active:
                mapping.is_active = True
                mapping.save()
                logger.info(f"비활성화된 매핑을 활성화함: mapping_id={mapping.id}")
            
            message = '카드가 성공적으로 등록되었습니다.'
            if not created and mapping_created:
                message = '기존 카드가 주유소에 등록되었습니다.'
            elif not created and not mapping_created:
                message = '이미 등록된 카드입니다.'
            
            return JsonResponse({
                'status': 'success',
                'message': message,
                'created': created,
                'mapping_created': mapping_created
            })
            
        except json.JSONDecodeError:
            logger.error("JSON 디코딩 오류")
            return JsonResponse({
                'status': 'error',
                'message': '잘못된 요청 형식입니다.'
            }, status=400)
        except Exception as e:
            logger.error(f"카드 등록 중 오류 발생: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': f'카드 등록 중 오류가 발생했습니다: {str(e)}'
            }, status=500)
    
    return JsonResponse({'status': 'error', 'message': '잘못된 요청 방식입니다.'}, status=405)

@login_required
def download_template(request):
    """엑셀 템플릿 파일 다운로드"""
    logger.info(f"템플릿 다운로드 요청 - 사용자: {request.user.username}")
    
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 템플릿 다운로드 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        import os
        from django.http import FileResponse
        from django.conf import settings
        
        # 템플릿 파일 경로
        template_path = os.path.join(
            settings.BASE_DIR, 
            'Cust_StationApp', 
            'templates', 
            'Cust_Station', 
            'point_sample.xlsx'
        )
        
        # 파일 존재 확인
        if not os.path.exists(template_path):
            logger.error(f"템플릿 파일을 찾을 수 없음: {template_path}")
            return JsonResponse({
                'status': 'error',
                'message': '템플릿 파일을 찾을 수 없습니다.'
            }, status=404)
        
        # 파일 응답 생성
        response = FileResponse(
            open(template_path, 'rb'),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="멤버십카드_등록_템플릿.xlsx"'
        
        logger.info(f"템플릿 파일 다운로드 성공: {template_path}")
        return response
        
    except Exception as e:
        logger.error(f"템플릿 다운로드 중 오류 발생: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'템플릿 다운로드 중 오류가 발생했습니다: {str(e)}'
        }, status=500)

@login_required
@csrf_exempt
def register_cards_bulk(request):
    """카드 일괄 등록"""
    logger.info(f"일괄 카드 등록 요청 - 사용자: {request.user.username}, 메소드: {request.method}")
    
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 카드 등록 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    if request.method == 'POST':
        try:
            # 주유소 프로필에서 정유사 코드와 대리점 코드 가져오기
            station_profile = request.user.station_profile
            if not station_profile:
                logger.error(f"주유소 프로필을 찾을 수 없음: {request.user.username}")
                return JsonResponse({
                    'status': 'error',
                    'message': '주유소 프로필 정보가 없습니다.'
                }, status=400)

            oil_company_code = station_profile.oil_company_code
            agency_code = station_profile.agency_code

            if not oil_company_code or len(oil_company_code) != 1:
                logger.error(f"잘못된 정유사 코드: {oil_company_code}")
                return JsonResponse({
                    'status': 'error',
                    'message': '주유소 프로필의 정유사 코드가 올바르지 않습니다.'
                }, status=400)

            if not agency_code or len(agency_code) != 3:
                logger.error(f"잘못된 대리점 코드: {agency_code}")
                return JsonResponse({
                    'status': 'error',
                    'message': '주유소 프로필의 대리점 코드가 올바르지 않습니다.'
                }, status=400)

            logger.info(f"요청 본문: {request.body.decode('utf-8')}")
            data = json.loads(request.body)
            start_num = data.get('startNumber', '').strip()
            try:
                card_count = int(data.get('cardCount', 0))
            except (ValueError, TypeError):
                logger.warning(f"잘못된 카드 수 형식: {data.get('cardCount')}")
                return JsonResponse({
                    'status': 'error',
                    'message': '카드 수는 숫자여야 합니다.'
                }, status=400)
            tid = data.get('tid', '').strip()
            
            logger.info(f"시작번호: {start_num}, 카드수: {card_count}, TID: {tid}")
            
            # 입력값 검증
            if not start_num or len(start_num) != 16 or not start_num.isdigit():
                logger.warning(f"잘못된 시작번호 형식: {start_num}")
                return JsonResponse({
                    'status': 'error',
                    'message': '시작번호는 16자리 숫자여야 합니다.'
                })
            
            if not card_count or card_count <= 0:
                logger.warning(f"잘못된 카드 수: {card_count}")
                return JsonResponse({
                    'status': 'error',
                    'message': '카드 수는 1개 이상이어야 합니다.'
                })
            
            if not tid:
                logger.warning("TID가 제공되지 않음")
                return JsonResponse({
                    'status': 'error',
                    'message': 'TID는 필수 입력값입니다.'
                })
            
            try:
                start_num = int(start_num)
            except ValueError:
                logger.warning(f"시작번호를 정수로 변환할 수 없음: {start_num}")
                return JsonResponse({
                    'status': 'error',
                    'message': '시작번호는 숫자여야 합니다.'
                }, status=400)

            registered_cards = []
            
            for i in range(card_count):
                card_number = str(start_num + i).zfill(16)
                logger.debug(f"카드 생성 시도: {card_number}")
                
                try:
                    # get_or_create를 사용하여 중복 생성 방지
                    card, created = PointCard.objects.get_or_create(
                        number=card_number,
                        defaults={
                            'tids': [],
                            'oil_company_code': oil_company_code,
                            'agency_code': agency_code
                        }
                    )
                    logger.debug(f"카드 생성 결과: created={created}, card_id={card.id}")
                    
                    # TID 추가
                    if tid not in card.tids:
                        logger.debug(f"카드 {card_number}에 TID {tid} 추가 시도")
                        card.tids.append(tid)
                        card.save()
                        logger.debug(f"카드 {card_number}의 업데이트된 TID 목록: {card.tids}")
                    
                    # 카드와 주유소 매핑 생성
                    logger.debug(f"매핑 생성 시도: 카드={card_number}, TID={tid}")
                    mapping, mapping_created = StationCardMapping.objects.get_or_create(
                        station=request.user,
                        tid=tid,
                        card=card,
                        defaults={'is_active': True}
                    )
                    logger.debug(f"매핑 생성 결과: created={mapping_created}, mapping_id={mapping.id}")
                    
                    # 매핑이 이미 존재하지만 비활성화된 경우 활성화
                    if not mapping_created and not mapping.is_active:
                        mapping.is_active = True
                        mapping.save()
                        logger.info(f"비활성화된 매핑을 활성화함: mapping_id={mapping.id}")
                    
                    registered_cards.append({
                        'number': card.number,
                        'is_used': card.is_used,
                        'created_at': card.created_at.strftime('%Y-%m-%d %H:%M:%S')
                    })
                    
                except Exception as e:
                    logger.error(f"카드 {card_number} 생성 중 오류: {str(e)}", exc_info=True)
                    return JsonResponse({
                        'status': 'error',
                        'message': f'카드 {card_number} 생성 중 오류가 발생했습니다.'
                    }, status=500)
            
            return JsonResponse({
                'status': 'success',
                'message': f'{len(registered_cards)}개의 카드가 성공적으로 등록되었습니다.',
                'cards': registered_cards
            })
            
        except json.JSONDecodeError:
            logger.error("잘못된 JSON 형식")
            return JsonResponse({
                'status': 'error',
                'message': '잘못된 요청 형식입니다.'
            }, status=400)
        except Exception as e:
            logger.error(f"카드 일괄 등록 중 오류 발생: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': '카드 일괄 등록 중 오류가 발생했습니다.'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': '잘못된 요청 메소드입니다.'
    }, status=405)

@login_required
def update_card_status(request):
    """카드 사용 상태 업데이트"""
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 상태 업데이트 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            card_number = data.get('cardNumber', '').strip()
            is_used = data.get('isUsed', False)
            tid = data.get('tid', '').strip()  # TID 값 추가
            
            # 입력 검증
            if not card_number or len(card_number) != 16 or not card_number.isdigit():
                return JsonResponse({
                    'status': 'error',
                    'message': '카드번호가 올바르지 않습니다.'
                })
            
            if not tid:
                return JsonResponse({
                    'status': 'error',
                    'message': 'TID는 필수 입력값입니다.'
                })
            
            # 카드와 매핑 상태 업데이트
            try:
                # 카드 존재 여부 확인
                card = PointCard.objects.get(number=card_number)
                
                # 현재 주유소의 카드 매핑 확인
                mapping = StationCardMapping.objects.get(
                    station=request.user,
                    tid=tid,
                    card=card,
                    is_active=True
                )
                
                # 카드 상태 업데이트
                old_status = card.is_used
                card.is_used = is_used
                card.save()
                
                # 상태 변경 로깅
                logger.info(
                    f"카드 상태 변경: {card_number}, "
                    f"주유소: {request.user.username}, "
                    f"이전 상태: {'사용중' if old_status else '미사용'}, "
                    f"변경 상태: {'사용중' if is_used else '미사용'}"
                )
                
                return JsonResponse({
                    'status': 'success',
                    'message': '카드 상태가 업데이트되었습니다.',
                    'cardNumber': card.number,
                    'isUsed': card.is_used
                })
            except PointCard.DoesNotExist:
                logger.warning(f"존재하지 않는 카드 상태 업데이트 시도: {card_number}")
                return JsonResponse({
                    'status': 'error',
                    'message': '등록되지 않은 카드번호입니다.'
                })
            except StationCardMapping.DoesNotExist:
                logger.warning(f"권한 없는 카드 상태 업데이트 시도: {card_number}, 주유소: {request.user.username}")
                return JsonResponse({
                    'status': 'error',
                    'message': '해당 카드에 대한 권한이 없습니다.'
                })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': '잘못된 요청 형식입니다.'
            }, status=400)
        except Exception as e:
            logger.error(f"카드 상태 업데이트 중 오류 발생: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': f'카드 상태 업데이트 중 오류가 발생했습니다: {str(e)}'
            }, status=500)
    
    return JsonResponse({'status': 'error', 'message': '잘못된 요청 방식입니다.'}, status=405)

@login_required
def delete_card(request):
    """멤버십 카드 삭제"""
    if not request.user.is_station:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            card_number = data.get('cardNumber')
            
            if not card_number:
                return JsonResponse({
                    'status': 'error',
                    'message': '멤버십 카드 번호는 필수입니다.'
                }, status=400)
            
            # 카드 번호로 카드 찾기
            card = get_object_or_404(PointCard, number=card_number)
            
            # 사용중인 카드는 삭제할 수 없음
            if card.is_used:
                return JsonResponse({
                    'status': 'error',
                    'message': '사용중인 카드는 삭제할 수 없습니다. 먼저 미사용 상태로 변경해주세요.'
                }, status=400)
            
            # 카드 매핑 삭제
            mapping = get_object_or_404(
                StationCardMapping,
                station=request.user,
                tid=request.user.station_profile.tid,
                card=card
            )
            mapping.delete()
            
            # 카드 자체도 삭제
            card.delete()
            
            return JsonResponse({
                'status': 'success',
                'message': '멤버십 카드가 성공적으로 삭제되었습니다.'
            })
            
        except PointCard.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': '해당 카드를 찾을 수 없습니다.'
            }, status=404)
        except StationCardMapping.DoesNotExist:
            return JsonResponse({
                'status': 'error',
                'message': '해당 카드의 매핑 정보를 찾을 수 없습니다.'
            }, status=404)
        except Exception as e:
            logger.error(f"멤버십 카드 삭제 중 오류 발생: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': f'멤버십 카드 삭제 중 오류가 발생했습니다: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': '잘못된 요청 메소드입니다.'
    }, status=405)

@login_required
def station_couponmanage(request):
    """주유소 쿠폰 관리 페이지"""
    if not request.user.is_station:
        messages.error(request, '주유소 회원만 접근할 수 있습니다.')
        return redirect('home')
    
    # 기본 쿠폰 유형 생성 (없으면)
    _create_default_coupon_types(request.user)
    
    # 쿠폰 통계 계산
    from django.db.models import Q
    total_templates = CouponTemplate.objects.filter(station=request.user, is_active=True).count()
    
    # 두 템플릿 타입을 모두 고려한 쿠폰 통계
    station_filter = Q(coupon_template__station=request.user) | Q(auto_coupon_template__station=request.user)
    
    total_issued = CustomerCoupon.objects.filter(station_filter).count()
    used_coupons = CustomerCoupon.objects.filter(station_filter, status='USED').count()
    unused_coupons = CustomerCoupon.objects.filter(station_filter, status='AVAILABLE').count()
    
    # 쿠폰 유형 목록
    coupon_types = CouponType.objects.filter(station=request.user, is_active=True).order_by('is_default', 'type_name')
    
    # 쿠폰 템플릿 목록 (최근 5개)
    recent_templates = CouponTemplate.objects.filter(
        station=request.user, 
        is_active=True
    ).order_by('-created_at')[:5]
    
    # 모든 쿠폰 템플릿 (발행용)
    all_templates = CouponTemplate.objects.filter(
        station=request.user,
        is_active=True
    ).select_related('coupon_type').order_by('-created_at')
    
    # 그룹 목록
    from .models import Group
    groups = Group.objects.filter(station=request.user).order_by('name')
    
    # 발행 통계 (오늘, 이번 주)
    from datetime import datetime, timedelta
    from django.utils import timezone
    now = timezone.now()
    today = now.date()
    week_start = today - timedelta(days=today.weekday())
    
    today_issued = CustomerCoupon.objects.filter(
        station_filter,
        issued_date__date=today
    ).count()
    
    week_issued = CustomerCoupon.objects.filter(
        station_filter,
        issued_date__date__gte=week_start
    ).count()
    
    # 전체 발행 쿠폰 리스트 (최대 100개, 최신순) - 고객 프로필 정보 포함
    all_coupons = CustomerCoupon.objects.filter(
        station_filter
    ).select_related(
        'coupon_template', 
        'auto_coupon_template',
        'customer',
        'customer__customer_profile'
    ).order_by('-issued_date')[:100]

    # 사용된 쿠폰 리스트 (최대 100개) - 고객 프로필 정보 포함
    used_coupons_list = CustomerCoupon.objects.filter(
        station_filter,
        status='USED'
    ).select_related(
        'coupon_template', 
        'auto_coupon_template',
        'customer',
        'customer__customer_profile'
    ).order_by('-used_date', '-issued_date')[:100]

    # 미사용 쿠폰 리스트 (최대 100개) - 고객 프로필 정보 포함
    unused_coupons_list = CustomerCoupon.objects.filter(
        station_filter,
        status='AVAILABLE'
    ).select_related(
        'coupon_template', 
        'auto_coupon_template',
        'customer',
        'customer__customer_profile'
    ).order_by('-issued_date')[:100]
    
    context = {
        'station_name': request.user.username,
        'total_templates': total_templates,
        'total_issued': total_issued,
        'used_coupons': used_coupons,
        'unused_coupons': unused_coupons,
        'total_coupons': total_issued,  # 전체 쿠폰
        'coupon_types': coupon_types,
        'recent_templates': recent_templates,
        'coupon_templates': all_templates,  # 발행용 템플릿 목록
        'groups': groups,  # 그룹 목록
        'today_issued': today_issued,  # 오늘 발행
        'week_issued': week_issued,  # 이번 주 발행
        'all_coupons': all_coupons,  # 전체 쿠폰 리스트
        'used_coupons_list': used_coupons_list,  # 사용된 쿠폰 리스트
        'unused_coupons_list': unused_coupons_list,  # 미사용 쿠폰 리스트
    }
    
    return render(request, 'Cust_Station/station_couponmanage.html', context)


def _create_default_coupon_types(station_user):
    """기본 쿠폰 유형 생성"""
    default_types = [
        ('SIGNUP', '회원가입'),
        ('CARWASH', '세차'),
        ('PRODUCT', '상품'),
        ('FUEL', '주유'),
    ]
    
    for type_code, type_name in default_types:
        CouponType.objects.get_or_create(
            station=station_user,
            type_code=type_code,
            defaults={
                'type_name': type_name,
                'is_default': True,
                'is_active': True
            }
        )


@login_required
@require_http_methods(["POST"])
def create_coupon_type(request):
    """새로운 쿠폰 유형 생성"""
    if not request.user.is_station:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        type_name = request.POST.get('type_name', '').strip()
        if not type_name:
            return JsonResponse({'status': 'error', 'message': '유형명을 입력해주세요.'})
        
        # 유형 코드 생성 (대문자로 변환하고 공백 제거)
        type_code = type_name.upper().replace(' ', '_')
        
        # 중복 확인
        if CouponType.objects.filter(station=request.user, type_code=type_code).exists():
            return JsonResponse({'status': 'error', 'message': '이미 존재하는 유형입니다.'})
        
        # 새 유형 생성
        coupon_type = CouponType.objects.create(
            station=request.user,
            type_code=type_code,
            type_name=type_name,
            is_default=False,
            is_active=True
        )
        
        return JsonResponse({
            'status': 'success',
            'message': '쿠폰 유형이 생성되었습니다.',
            'coupon_type': {
                'id': coupon_type.id,
                'type_code': coupon_type.type_code,
                'type_name': coupon_type.type_name
            }
        })
        
    except Exception as e:
        logger.error(f"쿠폰 유형 생성 오류: {str(e)}")
        return JsonResponse({'status': 'error', 'message': '쿠폰 유형 생성 중 오류가 발생했습니다.'})


@login_required
@require_http_methods(["POST"])
def create_coupon_template(request):
    """쿠폰 템플릿 생성"""
    if not request.user.is_station:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        # 폼 데이터 수집
        coupon_type_id = request.POST.get('coupon_type_id')
        coupon_name = request.POST.get('coupon_name', '').strip()
        description = request.POST.get('description', '').strip()
        benefit_type = request.POST.get('benefit_type')
        discount_amount = request.POST.get('discount_amount', 0)
        product_name = request.POST.get('product_name', '').strip()
        is_permanent = request.POST.get('is_permanent') == 'on'
        valid_from = request.POST.get('valid_from')
        valid_until = request.POST.get('valid_until')
        
        # 유효성 검증
        if not coupon_type_id:
            return JsonResponse({'status': 'error', 'message': '쿠폰 유형을 선택해주세요.'})
        
        if not coupon_name:
            return JsonResponse({'status': 'error', 'message': '쿠폰명을 입력해주세요.'})
        
        if not benefit_type:
            return JsonResponse({'status': 'error', 'message': '혜택 유형을 선택해주세요.'})
        
        # 쿠폰 유형 확인
        try:
            coupon_type = CouponType.objects.get(id=coupon_type_id, station=request.user)
        except CouponType.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': '유효하지 않은 쿠폰 유형입니다.'})
        
        # 혜택 유형별 검증
        if benefit_type in ['DISCOUNT', 'BOTH']:
            try:
                discount_amount = Decimal(discount_amount)
                if discount_amount <= 0:
                    return JsonResponse({'status': 'error', 'message': '할인 금액은 0보다 커야 합니다.'})
            except (ValueError, TypeError):
                return JsonResponse({'status': 'error', 'message': '올바른 할인 금액을 입력해주세요.'})
        
        if benefit_type in ['PRODUCT', 'BOTH']:
            if not product_name:
                return JsonResponse({'status': 'error', 'message': '상품명을 입력해주세요.'})
        
        # 날짜 검증
        if not is_permanent:
            if not valid_from or not valid_until:
                return JsonResponse({'status': 'error', 'message': '유효기간을 설정해주세요.'})
            
            try:
                valid_from = datetime.strptime(valid_from, '%Y-%m-%d').date()
                valid_until = datetime.strptime(valid_until, '%Y-%m-%d').date()
                
                if valid_from > valid_until:
                    return JsonResponse({'status': 'error', 'message': '시작일이 종료일보다 늦을 수 없습니다.'})
            except ValueError:
                return JsonResponse({'status': 'error', 'message': '올바른 날짜 형식을 입력해주세요.'})
        else:
            valid_from = None
            valid_until = None
        
        # 기본 설명 설정 (할인 혜택이 있는 경우 세차 할인 명시)
        if not description and benefit_type in ['DISCOUNT', 'BOTH']:
            description = f"{coupon_type.type_name} 쿠폰입니다. 할인 혜택은 세차장에서 사용 가능합니다."
        elif not description:
            description = f"{coupon_type.type_name} 쿠폰입니다."
        
        # 쿠폰 템플릿 생성
        coupon_template = CouponTemplate.objects.create(
            station=request.user,
            coupon_type=coupon_type,
            coupon_name=coupon_name,
            description=description,
            benefit_type=benefit_type,
            discount_amount=discount_amount if benefit_type in ['DISCOUNT', 'BOTH'] else 0,
            product_name=product_name if benefit_type in ['PRODUCT', 'BOTH'] else None,
            is_permanent=is_permanent,
            valid_from=valid_from,
            valid_until=valid_until,
            is_active=True
        )
        
        return JsonResponse({
            'status': 'success',
            'message': '쿠폰이 생성되었습니다.',
            'coupon_template': {
                'id': coupon_template.id,
                'coupon_name': coupon_template.coupon_name,
                'benefit_description': coupon_template.get_benefit_description()
            }
        })
        
    except Exception as e:
        logger.error(f"쿠폰 템플릿 생성 오류: {str(e)}")
        return JsonResponse({'status': 'error', 'message': '쿠폰 생성 중 오류가 발생했습니다.'})


@login_required
@require_http_methods(["GET"])
def get_coupon_templates(request):
    """쿠폰 템플릿 목록 조회"""
    if not request.user.is_station:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        templates = CouponTemplate.objects.filter(
            station=request.user,
            is_active=True
        ).select_related('coupon_type').order_by('-created_at')
        
        templates_data = []
        for template in templates:
            templates_data.append({
                'id': template.id,
                'coupon_name': template.coupon_name,
                'coupon_type_name': template.coupon_type.type_name,
                'benefit_description': template.get_benefit_description(),
                'is_permanent': template.is_permanent,
                'valid_from': template.valid_from.strftime('%Y-%m-%d') if template.valid_from else None,
                'valid_until': template.valid_until.strftime('%Y-%m-%d') if template.valid_until else None,
                'created_at': template.created_at.strftime('%Y-%m-%d %H:%M'),
                'is_valid': template.is_valid_today()
            })
        
        return JsonResponse({
            'status': 'success',
            'templates': templates_data
        })
        
    except Exception as e:
        logger.error(f"쿠폰 템플릿 조회 오류: {str(e)}")
        return JsonResponse({'status': 'error', 'message': '쿠폰 목록 조회 중 오류가 발생했습니다.'})


@login_required
@require_http_methods(["POST"])
def send_coupon(request):
    """수동 쿠폰 발행 (개선된 버전)"""
    if not request.user.is_station:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        from .models import StationCouponQuota
        
        template_id = request.POST.get('coupon_template_id')
        customer_ids = request.POST.getlist('customer_ids')
        target_type = request.POST.get('target_type')  # all, group, individual
        group_id = request.POST.get('group_id')
        
        if not template_id:
            return JsonResponse({'status': 'error', 'message': '쿠폰 템플릿을 선택해주세요.'})
        
        # 템플릿 확인
        try:
            template = CouponTemplate.objects.get(id=template_id, station=request.user)
        except CouponTemplate.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': '유효하지 않은 쿠폰 템플릿입니다.'})
        
        if not template.is_valid_today():
            return JsonResponse({'status': 'error', 'message': '유효하지 않은 쿠폰입니다.'})
        
        # 회원가입 쿠폰 수동 발행 차단
        if template.coupon_type.type_code == 'SIGNUP':
            return JsonResponse({'status': 'error', 'message': '회원가입 쿠폰은 수동으로 발행할 수 없습니다.'})
        
        # 발행 대상 고객 확인
        customers = []
        
        if target_type == 'all':
            # 모든 연결된 고객
            customers = CustomUser.objects.filter(
                user_type='CUSTOMER',
                station_relations__station=request.user,
                station_relations__is_active=True
            ).distinct()
        elif target_type == 'group' and group_id:
            # 특정 그룹 고객
            try:
                group = Group.objects.get(id=group_id, station=request.user)
                customers = CustomUser.objects.filter(
                    user_type='CUSTOMER',
                    customer_profile__group=group.name,
                    station_relations__station=request.user,
                    station_relations__is_active=True
                ).distinct()
            except Group.DoesNotExist:
                return JsonResponse({'status': 'error', 'message': '유효하지 않은 그룹입니다.'})
        elif target_type == 'individual' and customer_ids:
            # 개별 고객
            customers = CustomUser.objects.filter(
                id__in=customer_ids,
                user_type='CUSTOMER',
                station_relations__station=request.user,
                station_relations__is_active=True
            )
        
        if not customers.exists():
            return JsonResponse({'status': 'error', 'message': '발행할 고객이 없습니다.'})
        
        customer_count = customers.count()
        
        # 쿠폰 수량 체크 (자동 쿠폰 제외)
        if template.coupon_type.type_code not in ['SIGNUP', 'CUMULATIVE', 'MONTHLY']:
            quota = StationCouponQuota.objects.filter(station=request.user).first()
            if not quota or not quota.can_issue_coupons(customer_count):
                available_count = quota.remaining_quota if quota else 0
                return JsonResponse({
                    'status': 'error', 
                    'message': f'쿠폰 수량이 부족합니다. (요청: {customer_count}개, 잔여: {available_count}개)'
                })
        
        # 쿠폰 발행
        issued_count = 0
        with transaction.atomic():
            for customer in customers:
                CustomerCoupon.objects.create(
                    customer=customer,
                    coupon_template=template,
                    status='AVAILABLE'
                )
                issued_count += 1
            
            # 수동 쿠폰의 경우 수량 차감
            if template.coupon_type.type_code not in ['SIGNUP', 'CUMULATIVE', 'MONTHLY']:
                quota = StationCouponQuota.objects.filter(station=request.user).first()
                if quota:
                    quota.use_quota(issued_count)
        
        return JsonResponse({
            'status': 'success',
            'message': f'{issued_count}명의 고객에게 쿠폰을 발행했습니다.',
            'issued_count': issued_count
        })
        
    except Exception as e:
        logger.error(f"쿠폰 발행 오류: {str(e)}")
        return JsonResponse({'status': 'error', 'message': '쿠폰 발행 중 오류가 발생했습니다.'})

@require_http_methods(["GET"])
@login_required
def get_unused_cards(request):
    """미사용 카드 목록 조회 (주유소+TID별)"""
    logger.info("=== 미사용 카드 목록 조회 시작 ===")
    logger.info(f"요청 사용자: {request.user.username}")
    
    # 주유소 사용자 권한 확인
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 카드 목록 조회 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        # 주유소 프로필 확인
        if not hasattr(request.user, 'station_profile') or not request.user.station_profile:
            logger.error(f"주유소 프로필을 찾을 수 없음: {request.user.username}")
            return JsonResponse({
                'status': 'error',
                'message': '주유소 프로필 정보가 없습니다. 관리자에게 문의하세요.'
            }, status=400)
        
        # TID 확인
        tid = request.user.station_profile.tid
        if not tid:
            logger.error(f"주유소 TID가 설정되지 않음: {request.user.username}")
            return JsonResponse({
                'status': 'error',
                'message': '주유소 TID가 설정되지 않았습니다. 프로필을 확인해주세요.'
            }, status=400)
        
        logger.info(f"주유소 TID: {tid}")
        
        # 현재 주유소+TID에 등록된 미사용 카드만 조회
        mappings = StationCardMapping.objects.select_related('card').filter(
            station=request.user,
            tid=tid,
            is_active=True,
            card__is_used=False
        ).order_by('-registered_at')
        
        cards_data = [{
            'number': mapping.card.number,
            'tids': mapping.card.tids,
            'created_at': mapping.registered_at.strftime('%Y-%m-%d %H:%M')
        } for mapping in mappings]
        
        logger.info(f"조회된 미사용 카드 수: {len(cards_data)}")
        logger.info("=== 미사용 카드 목록 조회 완료 ===")
        
        return JsonResponse({
            'status': 'success',
            'cards': cards_data
        })
    except Exception as e:
        logger.error(f"미사용 카드 목록 조회 중 오류: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': '카드 목록을 불러오는데 실패했습니다.'
        }, status=500)

@require_http_methods(["POST"])
@csrf_exempt
def register_card(request):
    """멤버십 카드 등록 뷰"""
    logger.info("\n=== 멤버십 카드 등록 시작 ===")
    logger.info(f"요청 사용자: {request.user.username}")
    
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 카드 등록 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        # 주유소 프로필에서 정유사 코드와 대리점 코드 가져오기
        station_profile = request.user.station_profile
        if not station_profile:
            logger.error(f"주유소 프로필을 찾을 수 없음: {request.user.username}")
            return JsonResponse({
                'status': 'error',
                'message': '주유소 프로필 정보가 없습니다.'
            }, status=400)

        oil_company_code = station_profile.oil_company_code
        agency_code = station_profile.agency_code

        if not oil_company_code or len(oil_company_code) != 1:
            logger.error(f"잘못된 정유사 코드: {oil_company_code}")
            return JsonResponse({
                'status': 'error',
                'message': '주유소 프로필의 정유사 코드가 올바르지 않습니다.'
            }, status=400)

        if not agency_code or len(agency_code) != 3:
            logger.error(f"잘못된 대리점 코드: {agency_code}")
            return JsonResponse({
                'status': 'error',
                'message': '주유소 프로필의 대리점 코드가 올바르지 않습니다.'
            }, status=400)

        # 요청 데이터 파싱
        data = json.loads(request.body)
        logger.debug(f"수신된 전체 데이터: {json.dumps(data, ensure_ascii=False)}")
        
        card_number = data.get('card_number', '').strip()
        tid = data.get('tid', '').strip()  # TID 값 추가
        logger.debug(f"입력된 카드번호: {card_number}, TID: {tid}")
        logger.debug(f"카드번호 길이: {len(card_number) if card_number else 0}")
        logger.debug(f"카드번호가 숫자인지: {card_number.isdigit() if card_number else False}")
        
        # 입력값 검증
        if not card_number or len(card_number) != 16 or not card_number.isdigit():
            logger.warning(f"잘못된 카드번호 형식: {card_number}")
            return JsonResponse({
                'status': 'error',
                'message': '올바른 카드번호를 입력해주세요 (16자리 숫자)'
            })
        
        if not tid:
            logger.warning("TID가 제공되지 않음")
            return JsonResponse({
                'status': 'error',
                'message': 'TID는 필수 입력값입니다.'
            })
        
        # 트랜잭션을 사용하여 중복 요청 방지
        with transaction.atomic():
            # 카드번호 중복 체크 (락 설정)
            existing_card = PointCard.objects.select_for_update().filter(number=card_number).first()
            if existing_card:
                logger.warning(f"중복된 카드번호: {card_number}")
                return JsonResponse({
                    'status': 'error',
                    'message': '이미 등록된 카드번호입니다'
                })
            
            # 새 카드 생성
            new_card = PointCard.objects.create(
                number=card_number,
                oil_company_code=oil_company_code,
                agency_code=agency_code,
                tids=[tid],
                created_at=timezone.now()
            )
            logger.info(f"새 카드 등록 완료: {new_card.number}, TID: {tid}")
            
            # 주유소-카드 매핑 생성
            StationCardMapping.objects.create(
                station=request.user,
                tid=tid,
                card=new_card,
                registered_at=timezone.now(),
                is_active=True
            )
            logger.info(f"카드 매핑 생성 완료: {new_card.number}, TID: {tid}")
        
        return JsonResponse({
            'status': 'success',
            'message': '카드가 성공적으로 등록되었습니다.',
            'card': {
                'number': new_card.number,
                'is_used': new_card.is_used,
                'created_at': new_card.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }
        })
        
    except json.JSONDecodeError:
        logger.error("잘못된 JSON 형식")
        return JsonResponse({
            'status': 'error',
            'message': '잘못된 요청 형식입니다.'
        }, status=400)
    except Exception as e:
        logger.error(f"카드 등록 중 오류 발생: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': '카드 등록 중 오류가 발생했습니다.'
        }, status=500)

@login_required
def register_customer(request):
    """신규 고객 등록 - 폰번호와 멤버십카드 연동"""
    logger.info("=== 고객 등록 프로세스 시작 ===")
    logger.info(f"요청 사용자: {request.user.username}")
    
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 접근 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    if request.method == 'POST':
        try:
            logger.info("POST 요청 데이터 처리 시작")
            data = json.loads(request.body)
            logger.debug(f"수신된 데이터: {json.dumps(data, ensure_ascii=False)}")
            
            phone = data.get('phone', '').strip()
            card_number = data.get('card_number', '').strip()
            car_number = data.get('car_number', '').strip()
            
            logger.info(f"입력값 확인 - 전화번호: {phone}, 카드번호: {card_number}, 차량번호: {car_number}")
            
            # 입력값 검증
            if not phone or not card_number:
                logger.warning(f"필수 필드 누락 - 전화번호: {bool(phone)}, 카드번호: {bool(card_number)}")
                return JsonResponse({
                    'status': 'error',
                    'message': '전화번호와 카드번호를 모두 입력해주세요.'
                }, status=400)
            
            # 전화번호 형식 확인
            phone = re.sub(r'[^0-9]', '', phone)
            if not re.match(r'^\d{10,11}$', phone):
                logger.warning(f"잘못된 전화번호 형식: {phone} (길이: {len(phone)})")
                return JsonResponse({
                    'status': 'error',
                    'message': '올바른 전화번호 형식이 아닙니다.'
                }, status=400)
            
            # 카드번호 형식 확인
            card_number = re.sub(r'[^0-9]', '', card_number)
            if not re.match(r'^\d{16}$', card_number):
                logger.warning(f"잘못된 카드번호 형식: {card_number} (길이: {len(card_number)})")
                return JsonResponse({
                    'status': 'error',
                    'message': '올바른 카드번호 형식이 아닙니다.'
                }, status=400)
            
            try:
                with transaction.atomic():
                    # 1. 카드 확인 (기존 등록된 카드만 사용)
                    try:
                        # 중복 데이터가 있을 수 있으므로 first() 사용
                        card_mapping = StationCardMapping.objects.select_for_update().select_related('card').filter(
                            card__number=card_number,
                            is_active=True
                        ).first()
                        
                        if not card_mapping:
                            logger.warning(f"미등록 카드 - 카드번호: {card_number}")
                            return JsonResponse({
                                'status': 'error',
                                'message': '등록되지 않은 카드번호입니다.'
                            }, status=400)
                        
                        card = card_mapping.card
                        logger.info(f"기존 카드 발견: {card_number} (매핑 ID: {card_mapping.id})")
                        
                        # 중복 데이터가 있는지 확인
                        duplicate_count = StationCardMapping.objects.filter(
                            card__number=card_number,
                            is_active=True
                        ).count()
                        
                        if duplicate_count > 1:
                            logger.warning(f"중복 카드 매핑 발견 - 카드번호: {card_number}, 개수: {duplicate_count}")
                            
                    except Exception as e:
                        logger.error(f"카드 조회 중 오류: {str(e)}", exc_info=True)
                        return JsonResponse({
                            'status': 'error',
                            'message': '카드 조회 중 오류가 발생했습니다.'
                        }, status=500)
                    
                    if card.is_used:
                        logger.warning(f"이미 사용 중인 카드 사용 시도: {card_number}")
                        return JsonResponse({
                            'status': 'error',
                            'message': '이미 사용 중인 카드입니다.'
                        }, status=400)

                    # 2. 기존 폰번호-카드 연동 확인 (같은 폰번호와 카드 조합만 중복 방지)
                    existing_mapping = PhoneCardMapping.objects.filter(
                        phone_number=phone,
                        membership_card=card,
                        station=request.user
                    ).first()
                    
                    if existing_mapping:
                        logger.warning(f"이미 등록된 폰번호-카드 조합: {phone} - {card_number}")
                        return JsonResponse({
                            'status': 'error',
                            'message': '이 전화번호와 카드 조합은 이미 등록되어 있습니다.'
                        }, status=400)

                    # 일반 고객 DB에서 동일한 전화번호를 가진 고객 확인
                    existing_customer = None
                    try:
                        from Cust_User.models import CustomerProfile
                        existing_customer = CustomerProfile.objects.filter(
                            customer_phone=phone
                        ).select_related('user').first()
                        
                        if existing_customer:
                            logger.info(f"기존 고객 발견: {existing_customer.user.username} (전화번호: {phone})")
                    except Exception as e:
                        logger.warning(f"기존 고객 조회 중 오류: {str(e)}")

                    # 3. 폰번호-카드 연동 생성
                    if not existing_customer:
                        logger.info("신규 고객 등록 - 미회원 매핑 생성 시작")
                        # 회원가입 고객이 없을 때만 미회원 매핑 생성
                        # 차량 번호가 빈 문자열이면 None으로 설정
                        car_number_clean = car_number.strip() if car_number else None
                        if car_number_clean == '':
                            car_number_clean = None
                        logger.info(f"차량 번호 처리 - 원본: '{car_number}', 정리됨: '{car_number_clean}'")
                            
                        try:
                            phone_card_mapping = PhoneCardMapping.objects.create(
                                phone_number=phone,
                                membership_card=card,
                                station=request.user,
                                car_number=car_number_clean,
                                is_used=False
                            )
                            logger.info(f"폰번호-카드 연동 생성 완료: {phone} - {card_number} (차량번호: {car_number_clean or '없음'})")
                            logger.info(f"생성된 매핑 ID: {phone_card_mapping.id}")
                        except Exception as e:
                            logger.error(f"PhoneCardMapping 생성 중 오류: {str(e)}", exc_info=True)
                            raise
                    else:
                        # 이미 회원가입 고객이 있으면 미회원 매핑을 생성하지 않음
                        logger.info("이미 회원가입된 고객이므로 미회원 매핑을 생성하지 않음")

                    # 4. 기존 고객이 있다면 해당 고객의 프로필에 카드번호 등록
                    if existing_customer:
                        logger.info("기존 고객 프로필 업데이트 시작")
                        try:
                            logger.info(f"기존 고객 정보 - 사용자: {existing_customer.user.username}, 기존 차량번호: {existing_customer.car_number or '없음'}")
                            existing_customer.membership_card = card_number
                            # 차량 번호가 있으면 고객 프로필에 업데이트 (기존 차량번호가 없을 때만)
                            car_number_clean = car_number.strip() if car_number else None
                            logger.info(f"차량 번호 처리 - 원본: '{car_number}', 정리됨: '{car_number_clean}'")
                            if car_number_clean and car_number_clean != '' and not existing_customer.car_number:
                                existing_customer.car_number = car_number_clean
                                logger.info(f"기존 고객 프로필에 차량번호 추가: {existing_customer.user.username} - {car_number_clean}")
                            else:
                                logger.info(f"차량 번호 업데이트 건너뜀 - 조건 불충족")
                            existing_customer.save()
                            logger.info(f"기존 고객 프로필에 카드번호 등록 완료: {existing_customer.user.username} - {card_number}")
                            
                            # 고객-주유소 관계 생성 (이미 존재하지 않는 경우에만)
                            from Cust_User.models import CustomerStationRelation
                            relation, created = CustomerStationRelation.objects.get_or_create(
                                customer=existing_customer.user,
                                station=request.user,
                                defaults={'is_active': True}
                            )
                            
                            if created:
                                logger.info(f"고객-주유소 관계 생성 완료: {existing_customer.user.username} - {request.user.username}")
                                
                                # 회원가입 쿠폰 자동 발행
                                from .models import auto_issue_signup_coupons
                                issued_count = auto_issue_signup_coupons(existing_customer.user, request.user)
                                if issued_count > 0:
                                    logger.info(f"회원가입 쿠폰 {issued_count}개 자동 발행됨")
                            else:
                                logger.info(f"고객-주유소 관계 이미 존재: {existing_customer.user.username} - {request.user.username}")
                                
                        except Exception as e:
                            logger.error(f"기존 고객 프로필 업데이트 중 오류: {str(e)}", exc_info=True)
                    
                    # 5. 카드 상태 업데이트 (사용 중으로 변경)
                    card.is_used = True
                    card.save()
                    logger.info(f"카드 상태 업데이트 완료 - 카드번호: {card_number}")
                    
                    # 응답 메시지 결정
                    if existing_customer:
                        message = f'폰번호와 멤버십카드가 성공적으로 연동되었습니다. 기존 고객 "{existing_customer.user.username}"님의 프로필에 카드가 등록되었습니다.'
                        logger.info(f"기존 고객 연동 완료 - 사용자: {existing_customer.user.username}")
                    else:
                        message = '폰번호와 멤버십카드가 성공적으로 연동되었습니다. 고객이 회원가입 시 자동으로 연동됩니다.'
                        logger.info("신규 고객 등록 완료 - 미회원 매핑 생성됨")
                    
                    logger.info("=== 고객 등록 프로세스 완료 ===")
                    logger.info(f"최종 응답 메시지: {message}")
                    return JsonResponse({
                        'status': 'success',
                        'message': message
                    })
                    
            except IntegrityError as e:
                logger.error("=== 데이터베이스 무결성 오류 발생 ===")
                logger.error(f"오류 내용: {str(e)}")
                logger.error(f"입력 데이터 - 전화번호: {phone}, 카드번호: {card_number}, 차량번호: {car_number}")
                logger.error("스택 트레이스:", exc_info=True)
                return JsonResponse({
                    'status': 'error',
                    'message': '고객 등록 중 무결성 오류가 발생했습니다. 이미 등록된 정보일 수 있습니다.'
                }, status=400)
            except Exception as e:
                logger.error("=== 데이터베이스 처리 중 예상치 못한 오류 발생 ===")
                logger.error(f"오류 내용: {str(e)}")
                logger.error(f"입력 데이터 - 전화번호: {phone}, 카드번호: {card_number}, 차량번호: {car_number}")
                logger.error("스택 트레이스:", exc_info=True)
                return JsonResponse({
                    'status': 'error',
                    'message': '고객 등록 중 오류가 발생했습니다.'
                }, status=500)
                
        except json.JSONDecodeError as e:
            logger.error("=== JSON 파싱 오류 발생 ===")
            logger.error(f"오류 내용: {str(e)}")
            logger.error(f"요청 본문: {request.body}")
            logger.error("스택 트레이스:", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': '잘못된 요청 형식입니다.'
            }, status=400)
        except Exception as e:
            logger.error("=== 예상치 못한 오류 발생 ===")
            logger.error(f"오류 내용: {str(e)}")
            logger.error(f"요청 메서드: {request.method}")
            logger.error(f"요청 사용자: {request.user.username}")
            logger.error("스택 트레이스:", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': '서버 오류가 발생했습니다.'
            }, status=500)
    
    logger.warning(f"잘못된 요청 방식: {request.method}")
    return JsonResponse({
        'status': 'error',
        'message': '잘못된 요청 방식입니다.'
    }, status=405)

@login_required
def delete_customer(request):
    """고객 삭제"""
    if not request.user.is_station:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            customer_id = data.get('customer_id')
            
            if not customer_id:
                return JsonResponse({
                    'status': 'error',
                    'message': '고객 ID는 필수입니다.'
                }, status=400)
            
            # 고객-주유소 관계 삭제
            relation = get_object_or_404(
                CustomerStationRelation,
                customer_id=customer_id,
                station=request.user
            )
            relation.delete()
            
            return JsonResponse({
                'status': 'success',
                'message': '고객이 성공적으로 삭제되었습니다.'
            })
            
        except Exception as e:
            logger.error(f"고객 삭제 중 오류 발생: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': f'고객 삭제 중 오류가 발생했습니다: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': '잘못된 요청 메소드입니다.'
    }, status=405)

@login_required
def check_customer_exists(request):
    """전화번호로 사용자 존재 여부와 상태를 확인하는 뷰"""
    if not request.user.is_station:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            phone = data.get('phone', '').strip()
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': '잘못된 요청 형식입니다.'
            }, status=400)
    elif request.method == 'GET':
        phone = request.GET.get('phone', '').strip()
    else:
        return JsonResponse({
            'status': 'error',
            'message': '지원하지 않는 요청 방식입니다.'
        }, status=405)

    if not phone:
        return JsonResponse({
            'status': 'error',
            'message': '전화번호를 입력해주세요.'
        }, status=400)

    # 전화번호 형식 확인 (숫자만 허용)
    phone = re.sub(r'[^0-9]', '', phone)
    if not re.match(r'^\d{10,11}$', phone):
        return JsonResponse({
            'status': 'error',
            'message': '올바른 전화번호 형식이 아닙니다.'
        }, status=400)

    try:
        # 전화번호로 기존 고객 프로필 검색
        from Cust_User.models import CustomerProfile
        profile = CustomerProfile.objects.filter(customer_phone=phone).select_related('user').first()
        
        if not profile:
            return JsonResponse({
                'status': 'success',
                'exists': False,
                'message': '사용 가능한 전화번호입니다.',
                'data': {
                    'can_register': True
                }
            })

        user = profile.user
        
        # 현재 주유소와의 관계 확인
        relation = CustomerStationRelation.objects.filter(
            customer=user,
            station=request.user
        ).exists()

        if relation:
            message = '이미 이 주유소에 등록된 고객입니다.'
            can_register = False
        else:
            message = f'기존 고객 "{user.username}"님의 전화번호입니다. 카드 등록 시 자동으로 연동됩니다.'
            can_register = True

        return JsonResponse({
            'status': 'success',
            'exists': True,
            'message': message,
            'data': {
                'phone': profile.customer_phone,
                'membership_card': profile.membership_card,
                'username': user.username,
                'is_registered_here': relation,
                'can_register': can_register
            }
        })

    except Exception as e:
        print(f"[DEBUG] 사용자 확인 중 오류 발생: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': '사용자 확인 중 오류가 발생했습니다.'
        }, status=500)

@login_required
def station_sales(request):
    """주유소 매출 관리 페이지"""
    if not request.user.is_station:
        messages.error(request, '주유소 회원만 접근할 수 있습니다.')
        return redirect('home')
    
    # TID 가져오기
    tid = getattr(getattr(request.user, 'station_profile', None), 'tid', None)
    
    # 업로드된 엑셀 파일 목록 가져오기
    uploaded_files = []
    if tid:
        import os
        upload_root = os.path.join(settings.BASE_DIR, 'upload', tid)
        if os.path.exists(upload_root):
            for filename in os.listdir(upload_root):
                if filename.endswith('.xlsx'):
                    file_path = os.path.join(upload_root, filename)
                    file_stat = os.stat(file_path)
                    # 파일 크기를 읽기 쉽게 변환
                    size = file_stat.st_size
                    if size < 1024:
                        size_str = f"{size} B"
                    elif size < 1024 * 1024:
                        size_str = f"{size / 1024:.1f} KB"
                    else:
                        size_str = f"{size / (1024 * 1024):.1f} MB"
                    
                    uploaded_files.append({
                        'filename': filename,
                        'size': size_str,
                        'size_bytes': file_stat.st_size,
                        'modified': file_stat.st_mtime,
                        'path': file_path
                    })
    
    # 파일명으로 정렬 (최신순)
    uploaded_files.sort(key=lambda x: x['filename'], reverse=True)
    
    # 기존 주유소app SalesData
    sales_data = SalesData.objects.filter(station=request.user).order_by('-sales_date')
    # 엑셀에서 불러온 SalesData
    excel_sales_data = ExcelSalesData.objects.all().order_by('-sale_date', '-sale_time')
    
    # 통계 데이터 가져오기
    sales_statistics = SalesStatistics.objects.filter(
        tid=tid
    ).order_by('-sale_date', '-created_at')
    
    context = {
        'uploaded_files': uploaded_files,
        'sales_data': sales_data,
        'excel_sales_data': excel_sales_data,
        'sales_statistics': sales_statistics,
    }
    
    return render(request, 'Cust_Station/station_sales.html', context)

from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

@login_required
@require_http_methods(["POST"])
def upload_sales_data(request):
    """매출 데이터 엑셀 파일 업로드 (TID별 폴더, TID_원본파일명으로 저장)"""
    if not request.user.is_station:
        return JsonResponse({'error': '권한이 없습니다.'}, status=403)
    
    # 중복 요청 방지를 위한 로깅
    import logging
    logger = logging.getLogger(__name__)
    
    # 중복 요청 방지를 위한 캐시 키 생성
    cache_key = f'upload_sales_{request.user.id}_{request.FILES.get("sales_file", {}).name if request.FILES else "no_file"}'
    
    # 이미 처리 중인 요청인지 확인
    if cache.get(cache_key):
        logger.warning(f'중복 업로드 요청 감지: {cache_key}')
        return JsonResponse({'error': '이미 처리 중인 요청입니다. 잠시 후 다시 시도해주세요.'}, status=429)
    
    # 캐시에 처리 중임을 표시 (5초 동안)
    cache.set(cache_key, True, 5)
    
    try:
        logger.info(f'파일 업로드 요청 시작 - 사용자: {request.user.username}')
        
        if 'sales_file' not in request.FILES:
            cache.delete(cache_key)
            return JsonResponse({'error': '파일이 선택되지 않았습니다.'}, status=400)
        
        sales_file = request.FILES['sales_file']
        if not sales_file.name.endswith('.xlsx'):
            cache.delete(cache_key)
            return JsonResponse({'error': '엑셀 파일(.xlsx)만 업로드 가능합니다.'}, status=400)
        
        # TID 가져오기
        tid = getattr(getattr(request.user, 'station_profile', None), 'tid', None)
        if not tid:
            cache.delete(cache_key)
            return JsonResponse({'error': '주유소 TID가 등록되어 있지 않습니다.'}, status=400)
        
        # 원본 파일명에서 디렉토리 제거
        import os
        from datetime import datetime
        
        original_name = os.path.basename(sales_file.name)
        # 파일명에서 확장자 분리
        name_without_ext, file_extension = os.path.splitext(original_name)
        # 파일명: 원본파일명_Tid.xlsx
        file_name = f'{name_without_ext}_{tid}{file_extension}'
        # 저장 경로: Cust_Note/upload/<TID>/
        upload_root = os.path.join(settings.BASE_DIR, 'upload', tid)
        os.makedirs(upload_root, exist_ok=True)
        file_path = os.path.join(upload_root, file_name)
        
        # 파일이 이미 존재하는지 확인
        if os.path.exists(file_path):
            logger.warning(f'파일이 이미 존재합니다: {file_path}')
            cache.delete(cache_key)
            return JsonResponse({'error': '동일한 파일이 이미 업로드되어 있습니다.'}, status=400)
        
        logger.info(f'파일 저장 시작: {file_path}')
        # 파일 저장
        with open(file_path, 'wb+') as destination:
            for chunk in sales_file.chunks():
                destination.write(chunk)
        
        logger.info(f'파일 업로드 완료: {file_name}')
        cache.delete(cache_key)  # 성공 시 캐시 삭제
        return JsonResponse({'message': f'파일이 성공적으로 업로드되었습니다: {file_name}'})
        
    except Exception as e:
        logger.error(f'엑셀 파일 업로드 중 오류 발생: {str(e)}')
        cache.delete(cache_key)  # 오류 시에도 캐시 삭제
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def analyze_sales_file(request):
    """업로드된 엑셀 파일 분석"""
    if not request.user.is_station:
        return JsonResponse({'error': '권한이 없습니다.'}, status=403)
    
    try:
        filename = request.POST.get('filename')
        if not filename:
            return JsonResponse({'error': '파일명이 제공되지 않았습니다.'}, status=400)
        
        # TID 가져오기
        tid = getattr(getattr(request.user, 'station_profile', None), 'tid', None)
        if not tid:
            return JsonResponse({'error': '주유소 TID가 등록되어 있지 않습니다.'}, status=400)
        
        # 파일 경로 확인
        import os
        file_path = os.path.join(settings.BASE_DIR, 'upload', tid, filename)
        if not os.path.exists(file_path):
            return JsonResponse({'error': '파일을 찾을 수 없습니다.'}, status=404)
        
        # 엑셀 파일 분석 및 데이터베이스 저장
        import pandas as pd
        from datetime import datetime
        
        logger.info(f"파일 분석 시작: {filename}")
        logger.info(f"파일 경로: {file_path}")
        
        # 엑셀 파일 읽기 (첫 번째 행부터 시작)
        logger.info("엑셀 파일 읽기 시작...")
        df = pd.read_excel(
            file_path,
            skiprows=0,  # 첫 번째 행부터 시작
            names=['판매일자', '주유시간', '고객번호', '고객명', '발행번호', '주류상품종류', 
                  '판매구분', '결제구분', '판매구분2', '노즐', '제품코드', '제품/PACK',
                  '판매수량', '판매단가', '판매금액', '적립포인트', '포인트', '보너스',
                  'POS_ID', 'POS코드', '판매점', '영수증', '승인번호', '승인일시',
                  '보너스카드', '고객카드번호', '데이터생성일시']
        )
        logger.info(f"엑셀 파일 읽기 완료. 총 {len(df)} 행 발견")
        
        # 빈 행 제거
        df_cleaned = df.dropna(how='all')
        logger.info(f"빈 행 제거 후: {len(df_cleaned)} 행")
        
        # 헤더 행과 합계 행 제거 (더 안전한 처리)
        if len(df_cleaned) > 0:
            # 첫 번째 행이 헤더인 경우 제거
            first_row_sale_date = str(df_cleaned.iloc[0]['판매일자']).strip()
            if first_row_sale_date == '판매일자' or first_row_sale_date == 'nan' or first_row_sale_date == '':
                logger.info("헤더 행 제거")
                df_cleaned = df_cleaned.iloc[1:]
                logger.info(f"헤더 제거 후: {len(df_cleaned)} 행")
            
            # 마지막 행이 합계인 경우 제거
            if len(df_cleaned) > 0:
                last_row_sale_date = str(df_cleaned.iloc[-1]['판매일자']).strip()
                if last_row_sale_date == '합계' or last_row_sale_date == 'nan' or last_row_sale_date == '':
                    logger.info("합계 행 제거")
                    df_cleaned = df_cleaned.iloc[:-1]
                    logger.info(f"합계 제거 후: {len(df_cleaned)} 행")
        
        # 기존 데이터 삭제 (같은 파일에서 온 데이터)
        logger.info(f"기존 데이터 삭제: {filename}")
        deleted_count = ExcelSalesData.objects.filter(source_file=filename).delete()[0]
        logger.info(f"삭제된 기존 데이터: {deleted_count}개")
        
        # 데이터 분석 결과 출력
        logger.info("=== 📊 엑셀 파일 분석 결과 ===")
        logger.info(f"📈 기본 정보")
        logger.info(f"파일명: {filename}")
        logger.info(f"총 데이터 행 개수: {len(df)}행")
        logger.info(f"실제 데이터 행 개수: {len(df_cleaned)}행")
        
        # 날짜별 데이터 분석 및 통계 저장
        if len(df_cleaned) > 0:
            try:
                sale_dates = df_cleaned['판매일자'].dropna()
                if len(sale_dates) > 0:
                    min_date = sale_dates.min()
                    max_date = sale_dates.max()
                    logger.info(f"📅 날짜 범위")
                    logger.info(f"최초 판매일: {min_date}")
                    logger.info(f"최종 판매일: {max_date}")
                    
                    # 날짜별 데이터 개수 및 통계 계산
                    # 날짜별 데이터 개수 및 통계 계산
                    date_counts = sale_dates.value_counts().sort_index()
                    logger.info(f"날짜별 데이터 개수:")
                    
                    # 기존 통계 데이터 확인 (같은 파일에서 온 데이터)
                    from .models import SalesStatistics
                    existing_stats = SalesStatistics.objects.filter(tid__startswith=tid, source_file=filename)
                    if existing_stats.exists():
                        logger.info(f"기존 통계 데이터 발견: {existing_stats.count()}개 - 중복 방지 모드로 진행")
                    else:
                        logger.info(f"새로운 파일 분석: {filename}")
                    
                    # 날짜별 통계 데이터 생성 및 저장
                    for date, count in date_counts.items():
                        logger.info(f"  {date}: {count}행")
                        
                        # 해당 날짜의 데이터만 필터링
                        daily_data = df_cleaned[df_cleaned['판매일자'] == date]
                        
                        # 일별 통계 계산
                        daily_quantity = daily_data['판매수량'].sum()
                        daily_amount = daily_data['판매금액'].sum()
                        daily_avg_price = daily_amount / daily_quantity if daily_quantity > 0 else 0
                        
                        # 제품별 판매 현황 (가장 많이 팔린 제품)
                        product_counts = daily_data['제품/PACK'].value_counts()
                        top_product = product_counts.index[0] if len(product_counts) > 0 else ''
                        top_product_count = product_counts.iloc[0] if len(product_counts) > 0 else 0
                        
                        # SalesStatistics 모델에 통계 데이터 저장
                        try:
                            # 날짜 파싱
                            if '/' in str(date):
                                parsed_date = datetime.strptime(str(date), '%Y/%m/%d').date()
                            else:
                                parsed_date = date
                            
                            # 중복 확인 (tid, sale_date 조합)
                            existing_stat = SalesStatistics.objects.filter(
                                tid=tid,
                                sale_date=parsed_date
                            ).first()
                            
                            if existing_stat:
                                logger.info(f"중복 데이터 발견 - 건너뛰기: {date} ({existing_stat.total_transactions}건, {existing_stat.total_amount:,.0f}원)")
                                continue
                            
                            # 새로운 통계 데이터 저장
                            sales_stat = SalesStatistics(
                                tid=tid,  # 주유소 TID만 저장
                                sale_date=parsed_date,
                                total_transactions=count,
                                total_quantity=daily_quantity,
                                total_amount=daily_amount,
                                avg_unit_price=daily_avg_price,
                                top_product=top_product,
                                top_product_count=top_product_count,
                                source_file=filename
                            )
                            sales_stat.save()
                            logger.info(f"날짜별 통계 저장 완료: {date} - {count}건, {daily_amount:,.0f}원")
                            
                        except Exception as e:
                            logger.error(f"날짜별 통계 저장 중 오류 ({date}): {str(e)}")
                            continue
                            
            except Exception as e:
                logger.warning(f"날짜 분석 중 오류: {e}")
        
        # 제품별 데이터 분석
        if len(df_cleaned) > 0:
            try:
                product_counts = df_cleaned['제품/PACK'].value_counts()
                logger.info(f"⛽ 제품별 판매 현황")
                total_products = len(product_counts)
                for i, (product, count) in enumerate(product_counts.items(), 1):
                    percentage = (count / len(df_cleaned) * 100) if len(df_cleaned) > 0 else 0
                    logger.info(f"  {product}: {count}행 ({percentage:.1f}%)")
            except Exception as e:
                logger.warning(f"제품별 분석 중 오류: {e}")
        
        # 매출 정보 분석
        if len(df_cleaned) > 0:
            try:
                total_quantity = df_cleaned['판매수량'].sum()
                total_amount = df_cleaned['판매금액'].sum()
                avg_unit_price = total_amount / total_quantity if total_quantity > 0 else 0
                
                logger.info(f"💰 매출 정보")
                logger.info(f"총 판매수량: {total_quantity:,.2f}L")
                logger.info(f"총 판매금액: {total_amount:,.0f}원")
                logger.info(f"평균 단가: {avg_unit_price:,.0f}원/L")
            except Exception as e:
                logger.warning(f"매출 분석 중 오류: {e}")
        
        logger.info("=== 데이터베이스 저장 시작 ===")
        
        # 데이터베이스에 저장
        saved_count = 0
        daily_records = {}  # 날짜별로 데이터 그룹화
        
        # 먼저 날짜별로 데이터 그룹화
        for index, row in df_cleaned.iterrows():
            try:
                # 날짜 파싱 (안전한 처리)
                sale_date_str = str(row['판매일자']).strip()
                if pd.isna(row['판매일자']) or sale_date_str == '' or sale_date_str == 'nan':
                    logger.warning(f"행 {index}: 유효하지 않은 날짜 데이터 - 건너뛰기")
                    continue
                
                sale_date = None
                if '/' in sale_date_str:
                    try:
                        sale_date = datetime.strptime(sale_date_str, '%Y/%m/%d').date()
                    except ValueError:
                        logger.warning(f"행 {index}: 날짜 형식 오류 '{sale_date_str}' - 건너뛰기")
                        continue
                else:
                    logger.warning(f"행 {index}: 날짜 형식이 맞지 않음 '{sale_date_str}' - 건너뛰기")
                    continue
                
                # 날짜별로 데이터 그룹화
                if sale_date not in daily_records:
                    daily_records[sale_date] = []
                daily_records[sale_date].append(row)
                
            except Exception as e:
                logger.error(f"행 {index} 날짜 파싱 중 오류: {str(e)}")
                continue
        
        # 날짜별로 개별 저장
        for sale_date, rows in daily_records.items():
            logger.info(f"날짜별 저장 시작: {sale_date} - {len(rows)}행")
            
            # 해당 날짜의 기존 데이터 삭제 (tid, sale_date 기준으로 완전 삭제)
            deleted_excel = ExcelSalesData.objects.filter(
                tid=tid,
                sale_date=sale_date
            ).delete()
            deleted_stats = SalesStatistics.objects.filter(
                tid=tid,
                sale_date=sale_date
            ).delete()
            logger.info(f"[삭제] {sale_date} - ExcelSalesData: {deleted_excel[0]}개, SalesStatistics: {deleted_stats[0]}개")
            
            # 해당 날짜의 통계 데이터도 삭제
            deleted_stats = SalesStatistics.objects.filter(
                tid=tid,
                sale_date=sale_date
            ).delete()[0]
            if deleted_stats > 0:
                logger.info(f"기존 통계 데이터 삭제: {sale_date} - {deleted_stats}개")
            
            # 해당 날짜의 모든 행 저장
            daily_saved_count = 0
            daily_quantity = 0
            daily_amount = 0
            product_counts = {}
            product_amounts = {}  # 실제 제품별 판매금액
            
            for row in rows:
                try:
                    # 시간 파싱 (안전한 처리)
                    sale_time_str = str(row['주유시간']).strip()
                    if pd.isna(row['주유시간']) or sale_time_str == '' or sale_time_str == 'nan':
                        sale_time = datetime.now().time()
                    else:
                        try:
                            if ' ' in sale_time_str:
                                time_part = sale_time_str.split(' ')[1]
                                sale_time = datetime.strptime(time_part, '%H:%M').time()
                            else:
                                sale_time = datetime.now().time()
                        except ValueError:
                            logger.warning(f"시간 형식 오류 '{sale_time_str}' - 현재 시간 사용")
                            sale_time = datetime.now().time()
                    
                    # 숫자 데이터 처리 (안전한 변환)
                    def safe_float(value, default=0, handle_negative='zero'):
                        """
                        안전한 float 변환 함수
                        handle_negative: 'zero' (음수를 0으로), 'abs' (절댓값), 'keep' (그대로 유지)
                        """
                        if pd.isna(value):
                            return default
                        try:
                            result = float(value)
                            if handle_negative == 'zero' and result < 0:
                                logger.warning(f"음수 값 발견: {value} -> 0으로 처리")
                                return 0
                            elif handle_negative == 'abs' and result < 0:
                                logger.warning(f"음수 값 발견: {value} -> 절댓값으로 처리")
                                return abs(result)
                            elif handle_negative == 'keep' and result < 0:
                                logger.info(f"음수 값 발견: {value} -> 그대로 유지 (환불/취소 거래)")
                                return result
                            return result
                        except (ValueError, TypeError):
                            return default
                    
                    def safe_int(value, default=0, handle_negative='zero'):
                        """
                        안전한 int 변환 함수
                        handle_negative: 'zero' (음수를 0으로), 'abs' (절댓값), 'keep' (그대로 유지)
                        """
                        if pd.isna(value):
                            return default
                        try:
                            result = int(float(value))  # float로 먼저 변환 후 int로 변환
                            if handle_negative == 'zero' and result < 0:
                                logger.warning(f"음수 값 발견: {value} -> 0으로 처리")
                                return 0
                            elif handle_negative == 'abs' and result < 0:
                                logger.warning(f"음수 값 발견: {value} -> 절댓값으로 처리")
                                return abs(result)
                            elif handle_negative == 'keep' and result < 0:
                                logger.info(f"음수 값 발견: {value} -> 그대로 유지 (환불/취소 거래)")
                                return result
                            return result
                        except (ValueError, TypeError):
                            return default
                    
                    # 판매수량, 판매금액은 음수도 그대로 유지 (환불/취소 거래 포함)
                    quantity = safe_float(row['판매수량'], handle_negative='keep')
                    unit_price = safe_float(row['판매단가'], handle_negative='keep')
                    total_amount = safe_float(row['판매금액'], handle_negative='keep')
                    
                    # 포인트 관련은 절댓값으로 처리 (음수 포인트 사용도 유효한 데이터)
                    earned_points = safe_int(row.get('적립포인트', 0), handle_negative='abs')
                    points = safe_int(row.get('포인트', 0), handle_negative='abs')
                    bonus = safe_int(row.get('보너스', 0), handle_negative='abs')
                    
                    # 통계 계산을 위한 누적
                    daily_quantity += quantity
                    daily_amount += total_amount
                    
                    # 제품별 카운트 및 판매금액 누적
                    product_pack = str(row.get('제품/PACK', ''))
                    if product_pack and product_pack != 'nan':
                        product_counts[product_pack] = product_counts.get(product_pack, 0) + 1
                        product_amounts[product_pack] = product_amounts.get(product_pack, 0) + total_amount
                    
                    # ExcelSalesData 객체 생성 및 저장
                    excel_data = ExcelSalesData(
                        tid=tid,
                        sale_date=sale_date,
                        sale_time=sale_time,
                        customer_number=str(row.get('고객번호', '')),
                        customer_name=str(row.get('고객명', '')),
                        issue_number=str(row.get('발행번호', '')),
                        product_type=str(row.get('주류상품종류', '')),
                        sale_type=str(row.get('판매구분', '')),
                        payment_type=str(row.get('결제구분', '')),
                        sale_type2=str(row.get('판매구분2', '')),
                        nozzle=str(row.get('노즐', '')),
                        product_code=str(row.get('제품코드', '')),
                        product_pack=product_pack,
                        quantity=quantity,
                        unit_price=unit_price,
                        total_amount=total_amount,
                        earned_points=earned_points,
                        points=points,
                        bonus=bonus,
                        pos_id=str(row.get('POS_ID', '')),
                        pos_code=str(row.get('POS코드', '')),
                        store=str(row.get('판매점', '')),
                        receipt=str(row.get('영수증', '')),
                        approval_number=str(row.get('승인번호', '')),
                        approval_datetime=datetime.now(),
                        bonus_card=str(row.get('보너스카드', '')),
                        customer_card_number=str(row.get('고객카드번호', '')),
                        data_created_at=datetime.now(),
                        source_file=filename
                    )
                    excel_data.save()
                    daily_saved_count += 1
                    saved_count += 1
                    
                    # 보너스 카드와 일치하는 고객 찾아 방문 내역 저장
                    bonus_card = str(row.get('보너스카드', '')).strip()
                    if bonus_card and bonus_card != 'nan' and bonus_card != '':
                        try:
                            # Cust_UserApp의 CustomerVisitHistory 모델 import
                            from Cust_UserApp.models import CustomerVisitHistory
                            from Cust_User.models import CustomUser, CustomerProfile
                            
                            # 보너스 카드와 일치하는 고객 찾기
                            customer_profile = CustomerProfile.objects.filter(
                                membership_card__icontains=bonus_card
                            ).first()
                            
                            if customer_profile:
                                customer = customer_profile.user
                                logger.info(f"고객 발견: {customer.username} (보너스카드: {bonus_card})")
                                
                                # 주유량 정보 가져오기 (quantity 값) - 마이너스 값도 그대로 유지
                                fuel_quantity = safe_float(row.get('판매수량', 0), handle_negative='keep')
                                logger.info(f"주유량 추출: {fuel_quantity:.2f}L (원본값: {row.get('판매수량', 0)})")
                                
                                # 중복 방문 내역 체크 및 처리
                                approval_number = str(row.get('승인번호', ''))
                                existing_visit = CustomerVisitHistory.objects.filter(
                                    customer=customer,
                                    station=request.user,
                                    visit_date=sale_date,
                                    visit_time=sale_time,
                                    approval_number=approval_number
                                ).first()
                                
                                if existing_visit:
                                    logger.info(f"중복 방문 내역 발견 - 기존 데이터 삭제 후 재저장: {customer.username} - {sale_date} {sale_time} (승인번호: {approval_number})")
                                    existing_visit.delete()
                                
                                # 방문 내역 저장
                                visit_history = CustomerVisitHistory(
                                    customer=customer,
                                    station=request.user,
                                    tid=tid,
                                    visit_date=sale_date,
                                    visit_time=sale_time,
                                    payment_type=str(row.get('결제구분', '')),
                                    product_pack=str(row.get('제품/PACK', '')),
                                    sale_amount=total_amount,
                                    fuel_quantity=fuel_quantity,
                                    approval_number=approval_number,
                                    membership_card=bonus_card
                                )
                                visit_history.save()
                                logger.info(f"방문 내역 저장 완료: {customer.username} - {sale_date} {sale_time} (주유량: {fuel_quantity:.2f}L)")
                                
                                # 고객 프로필의 주유량 및 주유금액 정보 업데이트
                                from Cust_User.models import CustomerProfile
                                
                                # 기존 주유량 정보
                                old_total = customer_profile.total_fuel_amount
                                old_monthly = customer_profile.monthly_fuel_amount
                                old_last = customer_profile.last_fuel_amount
                                
                                # 새로운 주유량 정보 계산 (마이너스 값도 그대로 반영)
                                customer_profile.total_fuel_amount += fuel_quantity
                                customer_profile.monthly_fuel_amount += fuel_quantity
                                customer_profile.last_fuel_amount = fuel_quantity
                                customer_profile.last_fuel_date = sale_date
                                
                                # 새로운 주유금액 정보 계산
                                customer_profile.total_fuel_cost += total_amount
                                customer_profile.monthly_fuel_cost += total_amount
                                customer_profile.last_fuel_cost = total_amount
                                
                                customer_profile.save()
                                
                                # 업데이트된 주유량 및 주유금액 정보 로그
                                logger.info(f"업데이트된 주유량 정보 - 총: {customer_profile.total_fuel_amount:.2f}L, 월: {customer_profile.monthly_fuel_amount:.2f}L, 최근: {customer_profile.last_fuel_amount:.2f}L")
                                logger.info(f"업데이트된 주유금액 정보 - 총: {customer_profile.total_fuel_cost:,.0f}원, 월: {customer_profile.monthly_fuel_cost:,.0f}원, 최근: {customer_profile.last_fuel_cost:,.0f}원")
                                logger.info(f"방문 내역 및 주유 정보 저장 완료: {customer.username} - {sale_date} {sale_time} (주유량: {fuel_quantity:.2f}L, 주유금액: {total_amount:,.0f}원)")
                            else:
                                logger.info(f"보너스카드 {bonus_card}와 일치하는 고객을 찾을 수 없음")
                                
                        except Exception as e:
                            logger.error(f"방문 내역 저장 중 오류: {str(e)}")
                    
                except Exception as e:
                    logger.error(f"행 처리 중 오류: {str(e)}")
                    continue
            
            # 해당 날짜의 통계 데이터 저장
            try:
                # 날짜별 통계 중복 체크: 이미 해당 날짜의 통계가 있는지 확인
                existing_daily_stat = SalesStatistics.objects.filter(
                    tid=tid,
                    sale_date=sale_date
                ).first()
                
                if existing_daily_stat:
                    logger.info(f"=== 날짜별 통계 중복 발견 - 통계 저장 건너뛰기 ===")
                    logger.info(f"날짜: {sale_date}, 기존 파일: {existing_daily_stat.source_file}")
                    logger.info(f"현재 파일: {filename}")
                    logger.info(f"중복 방지를 위해 날짜별 통계 저장을 건너뜁니다.")
                    
                    # 날짜별 통계는 건너뛰지만 월별 누적은 진행
                    logger.info(f"월별 누적은 계속 진행합니다.")
                    
                    # 월별 누적 데이터 업데이트 (날짜별 통계 없이)
                    try:
                        logger.info(f"=== 월별 누적 업데이트 호출 (날짜별 통계 없이) ===")
                        logger.info(f"파일: {filename}, 날짜: {sale_date}")
                        logger.info(f"전달할 데이터 - 거래건수: {daily_saved_count}, 수량: {daily_quantity}, 금액: {daily_amount:,.0f}")
                        logger.info(f"제품별 카운트: {product_counts}")
                        logger.info(f"제품별 판매금액: {product_amounts}")
                        
                        update_monthly_statistics(tid, sale_date, daily_saved_count, daily_quantity, daily_amount, daily_avg_price, top_product, top_product_count, product_counts, product_amounts)
                        
                        logger.info(f"월별 누적 업데이트 완료: {sale_date}")
                    except Exception as e:
                        logger.error(f"월별 누적 데이터 업데이트 중 오류 ({sale_date}): {str(e)}")
                    
                    continue
                
                daily_avg_price = daily_amount / daily_quantity if daily_quantity > 0 else 0
                
                # 가장 많이 팔린 제품
                top_product = max(product_counts.items(), key=lambda x: x[1])[0] if product_counts else ''
                top_product_count = max(product_counts.values()) if product_counts else 0
                
                # SalesStatistics 모델에 통계 데이터 저장
                sales_stat = SalesStatistics(
                    tid=tid,
                    sale_date=sale_date,
                    total_transactions=daily_saved_count,
                    total_quantity=daily_quantity,
                    total_amount=daily_amount,
                    avg_unit_price=daily_avg_price,
                    top_product=top_product,
                    top_product_count=top_product_count,
                    source_file=filename
                )
                sales_stat.save()
                logger.info(f"날짜별 통계 저장 완료: {sale_date} - {daily_saved_count}건, {daily_amount:,.0f}원")
                
                # 월별 누적 데이터 업데이트
                try:
                    logger.info(f"=== 월별 누적 업데이트 호출 ===")
                    logger.info(f"파일: {filename}, 날짜: {sale_date}")
                    logger.info(f"전달할 데이터 - 거래건수: {daily_saved_count}, 수량: {daily_quantity}, 금액: {daily_amount:,.0f}")
                    logger.info(f"제품별 카운트: {product_counts}")
                    logger.info(f"제품별 판매금액: {product_amounts}")
                    
                    update_monthly_statistics(tid, sale_date, daily_saved_count, daily_quantity, daily_amount, daily_avg_price, top_product, top_product_count, product_counts, product_amounts)
                    
                    logger.info(f"월별 누적 업데이트 완료: {sale_date}")
                except Exception as e:
                    logger.error(f"월별 누적 데이터 업데이트 중 오류 ({sale_date}): {str(e)}")
                
            except Exception as e:
                logger.error(f"날짜별 통계 저장 중 오류 ({sale_date}): {str(e)}")
            
            # 진행상황 로그
            logger.info(f"날짜별 저장 완료: {sale_date} - {daily_saved_count}개 데이터 저장")
        
        logger.info(f"=== 분석 완료 ===")
        logger.info(f"총 {saved_count}개 데이터 저장 완료")
        
        return JsonResponse({
            'message': f'파일 분석이 완료되었습니다: {filename} (총 {saved_count}개 데이터 저장)',
            'result': {
                'filename': filename,
                'total_rows': len(df_cleaned),
                'saved_count': saved_count,
                'tid': tid
            }
        })
        
    except Exception as e:
        logger.error(f'파일 분석 중 오류 발생: {str(e)}')
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["POST"])
def delete_sales_file(request):
    """업로드된 엑셀 파일 삭제"""
    if not request.user.is_station:
        return JsonResponse({'error': '권한이 없습니다.'}, status=403)
    
    try:
        filename = request.POST.get('filename')
        if not filename:
            return JsonResponse({'error': '파일명이 제공되지 않았습니다.'}, status=400)
        
        # TID 가져오기
        tid = getattr(getattr(request.user, 'station_profile', None), 'tid', None)
        if not tid:
            return JsonResponse({'error': '주유소 TID가 등록되어 있지 않습니다.'}, status=400)
        
        # 파일 경로 확인 및 삭제
        import os
        file_path = os.path.join(settings.BASE_DIR, 'upload', tid, filename)
        if not os.path.exists(file_path):
            return JsonResponse({'error': '파일을 찾을 수 없습니다.'}, status=404)
        
        os.remove(file_path)
        return JsonResponse({'message': f'파일이 성공적으로 삭제되었습니다: {filename}'})
    
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'파일 삭제 중 오류 발생: {str(e)}')
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def download_uploaded_file(request):
    """업로드된 엑셀 파일 다운로드"""
    if not request.user.is_station:
        return JsonResponse({'error': '권한이 없습니다.'}, status=403)
    
    try:
        filename = request.GET.get('filename')
        if not filename:
            return JsonResponse({'error': '파일명이 제공되지 않았습니다.'}, status=400)
        
        # TID 가져오기
        tid = getattr(getattr(request.user, 'station_profile', None), 'tid', None)
        if not tid:
            return JsonResponse({'error': '주유소 TID가 등록되어 있지 않습니다.'}, status=400)
        
        # 파일 경로 확인
        file_path = os.path.join(settings.BASE_DIR, 'upload', tid, filename)
        if not os.path.exists(file_path):
            return JsonResponse({'error': '파일을 찾을 수 없습니다.'}, status=404)
        
        # 파일 다운로드 - 서버에 저장된 이름으로 다운로드
        filename = os.path.basename(file_path)
        logger.info(f"다운로드 파일명: {filename}")
        logger.info(f"전체 파일 경로: {file_path}")
        
        # 한글 파일명 처리를 위한 URL 인코딩
        import urllib.parse
        encoded_filename = urllib.parse.quote(filename)
        
        response = FileResponse(open(file_path, 'rb'))
        response['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response['Content-Disposition'] = f'attachment; filename="{encoded_filename}"; filename*=UTF-8\'\'{encoded_filename}'
        return response
        
    except Exception as e:
        logger.error(f'업로드된 파일 다운로드 중 오류 발생: {str(e)}')
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_sales_details(request):
    """특정 날짜의 매출 상세 정보를 반환하는 API"""
    if not request.user.is_station:
        return JsonResponse({'error': '권한이 없습니다.'}, status=403)
    
    try:
        date = request.GET.get('date')
        stat_id = request.GET.get('stat_id')
        
        if not date or not stat_id:
            return JsonResponse({'error': '날짜와 통계 ID가 필요합니다.'}, status=400)
        
        # TID 가져오기
        tid = getattr(getattr(request.user, 'station_profile', None), 'tid', None)
        if not tid:
            return JsonResponse({'error': '주유소 TID가 등록되어 있지 않습니다.'}, status=400)
        
        # 통계 데이터 가져오기 (해당 통계 ID로 조회)
        from .models import SalesStatistics
        try:
            stat = SalesStatistics.objects.filter(id=stat_id).first()
            if not stat:
                return JsonResponse({'error': '통계 데이터를 찾을 수 없습니다.'}, status=404)
        except Exception as e:
            logger.error(f'통계 데이터 조회 중 오류: {str(e)}')
            return JsonResponse({'error': '통계 데이터를 찾을 수 없습니다.'}, status=404)
        
        # 해당 날짜의 상세 데이터 가져오기
        from .models import ExcelSalesData
        daily_sales = ExcelSalesData.objects.filter(
            tid=tid,
            sale_date=date
        ).order_by('sale_time')
        
        # 제품별 판매 현황 계산
        product_breakdown = []
        if daily_sales.exists():
            from django.db.models import Sum, Count
            product_stats = daily_sales.values('product_pack').annotate(
                count=Count('id'),
                quantity=Sum('quantity'),
                amount=Sum('total_amount')
            ).order_by('-amount')
            
            for product in product_stats:
                product_breakdown.append({
                    'product_name': product['product_pack'],
                    'count': product['count'],
                    'quantity': f"{product['quantity']:.2f}",
                    'amount': f"{product['amount']:,.0f}"
                })
        
        # 응답 데이터 구성
        response_data = {
            'total_transactions': stat.total_transactions,
            'total_quantity': f"{stat.total_quantity:.2f}",
            'total_amount': f"{stat.total_amount:,.0f}",
            'avg_unit_price': f"{stat.avg_unit_price:,.0f}",
            'top_product': stat.top_product,
            'top_product_count': stat.top_product_count,
            'source_file': stat.source_file,
            'created_at': stat.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'product_breakdown': product_breakdown
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f'상세 정보 조회 중 오류 발생: {str(e)}')
        return JsonResponse({'error': '상세 정보를 불러오는 중 오류가 발생했습니다.'}, status=500)

@login_required
def search_customer(request):
    """전화번호로 사용자를 검색하는 뷰"""
    if request.method == 'GET':
        phone = request.GET.get('phone')
        if not phone:
            return JsonResponse({
                'status': 'error',
                'message': '전화번호를 입력해주세요.'
            }, status=400)

        try:
            # 사용자 검색
            user = CustomUser.objects.filter(username=phone).first()
            
            if not user:
                return JsonResponse({
                    'status': 'success',
                    'exists': False,
                    'message': '등록되지 않은 사용자입니다.'
                })

            # 프로필 정보 가져오기
            profile = CustomerProfile.objects.filter(user=user).first()
            
            # 현재 주유소와의 관계 확인
            relation = CustomerStationRelation.objects.filter(
                customer=user,
                station=request.user
            ).exists()

            return JsonResponse({
                'status': 'success',
                'exists': True,
                'data': {
                    'phone': profile.customer_phone if profile else None,
                    'membership_card': profile.membership_card if profile else None,
                    'is_registered_here': relation
                },
                'message': '사용자를 찾았습니다.'
            })

        except Exception as e:
            print(f"[DEBUG] 사용자 검색 중 오류 발생: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': '사용자 검색 중 오류가 발생했습니다.'
            }, status=500)

@login_required
def get_sales_statistics_list(request):
    """전체 매출 통계 리스트 반환"""
    if not request.user.is_station:
        return JsonResponse({'error': '권한이 없습니다.'}, status=403)
    
    try:
        # TID 가져오기
        tid = getattr(getattr(request.user, 'station_profile', None), 'tid', None)
        if not tid:
            return JsonResponse({'error': '주유소 TID가 등록되어 있지 않습니다.'}, status=400)
        
        # 전체 통계 데이터 조회
        from .models import SalesStatistics
        statistics = SalesStatistics.objects.filter(
            tid__startswith=tid
        ).order_by('-sale_date', '-created_at')
        
        # JSON 응답용 데이터 변환
        statistics_list = []
        for stat in statistics:
            statistics_list.append({
                'sale_date': stat.sale_date.strftime('%Y-%m-%d') if stat.sale_date else '',
                'tid': stat.tid,
                'total_transactions': stat.total_transactions,
                'total_quantity': f"{stat.total_quantity:.2f}",
                'total_amount': f"{stat.total_amount:,.0f}",
                'avg_unit_price': f"{stat.avg_unit_price:,.0f}",
                'top_product': stat.top_product or '없음',
                'top_product_count': stat.top_product_count,
                'source_file': stat.source_file or '',
                'created_at': stat.created_at.strftime('%Y-%m-%d %H:%M:%S') if stat.created_at else ''
            })
        
        response_data = {
            'statistics': statistics_list,
            'total_count': len(statistics_list)
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f'매출 통계 리스트 조회 중 오류: {str(e)}')
        return JsonResponse({'error': '통계 리스트를 불러오는 중 오류가 발생했습니다.'}, status=500)

@login_required
def get_sales_list(request):
    """특정 날짜의 매출 리스트 반환"""
    if not request.user.is_station:
        return JsonResponse({'error': '권한이 없습니다.'}, status=403)
    
    try:
        sale_date = request.GET.get('date')
        stat_id = request.GET.get('stat_id')
        
        if not sale_date or not stat_id:
            return JsonResponse({'error': '날짜와 통계 ID가 필요합니다.'}, status=400)
        
        # TID 가져오기
        tid = getattr(getattr(request.user, 'station_profile', None), 'tid', None)
        if not tid:
            return JsonResponse({'error': '주유소 TID가 등록되어 있지 않습니다.'}, status=400)
        
        # 해당 날짜의 매출 데이터 조회
        from .models import ExcelSalesData
        sales_list = ExcelSalesData.objects.filter(
            sale_date=sale_date,
            tid=tid
        ).order_by('sale_time')
        
        # JSON 응답용 데이터 변환
        sales_data = []
        for sale in sales_list:
            sales_data.append({
                'sale_time': sale.sale_time.strftime('%H:%M:%S') if sale.sale_time else '',
                'customer_number': sale.customer_number or '',
                'customer_name': sale.customer_name or '',
                'product_pack': sale.product_pack or '',
                'sale_quantity': f"{sale.quantity:.2f}" if sale.quantity else '0.00',
                'sale_unit_price': f"{sale.unit_price:,.0f}" if sale.unit_price else '0',
                'sale_amount': f"{sale.total_amount:,.0f}" if sale.total_amount else '0',
                'payment_method': sale.payment_type or '',
                'receipt_number': sale.receipt or '',
                'approval_number': sale.approval_number or '',
                'customer_card_number': sale.customer_card_number or '',
                'data_created_at': sale.data_created_at.strftime('%Y-%m-%d %H:%M:%S') if sale.data_created_at else ''
            })
        
        response_data = {
            'sale_date': sale_date,
            'total_count': len(sales_data),
            'sales_list': sales_data
        }
        
        return JsonResponse(response_data)
        
    except Exception as e:
        logger.error(f'매출 리스트 조회 중 오류: {str(e)}')
        return JsonResponse({'error': '매출 리스트를 불러오는 중 오류가 발생했습니다.'}, status=500)

# 그룹 관리 관련 함수들
@login_required
def group_management(request):
    """그룹 관리 페이지"""
    logger.info("=== 그룹 관리 페이지 접근 ===")
    logger.info(f"요청 사용자: {request.user.username}")
    
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 그룹 관리 접근 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    # 현재 주유소의 그룹 목록 조회
    from .models import Group
    groups = Group.objects.filter(station=request.user).order_by('-created_at')
    
    context = {
        'groups': groups,
        'total_groups': groups.count()
    }
    
    return render(request, 'Cust_Station/station_groupmanage.html', context)

@login_required
def create_group(request):
    """그룹 생성"""
    logger.info("=== 그룹 생성 요청 ===")
    logger.info(f"요청 사용자: {request.user.username}")
    
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 그룹 생성 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            group_name = data.get('name', '').strip()
            
            logger.info(f"그룹 생성 시도: {group_name}")
            
            # 입력값 검증
            if not group_name:
                logger.warning("그룹명이 입력되지 않음")
                return JsonResponse({
                    'status': 'error',
                    'message': '그룹명을 입력해주세요.'
                }, status=400)
            
            if len(group_name) > 100:
                logger.warning(f"그룹명이 너무 김: {len(group_name)}자")
                return JsonResponse({
                    'status': 'error',
                    'message': '그룹명은 100자 이하여야 합니다.'
                }, status=400)
            
            # 중복 체크
            from .models import Group
            if Group.objects.filter(station=request.user, name=group_name).exists():
                logger.warning(f"중복된 그룹명: {group_name}")
                return JsonResponse({
                    'status': 'error',
                    'message': '이미 존재하는 그룹명입니다.'
                }, status=400)
            
            # 그룹 생성
            new_group = Group.objects.create(
                name=group_name,
                station=request.user
            )
            logger.info(f"그룹 생성 완료: {new_group.name}")
            
            return JsonResponse({
                'status': 'success',
                'message': '그룹이 성공적으로 생성되었습니다.',
                'group': {
                    'id': new_group.id,
                    'name': new_group.name,
                    'created_at': new_group.created_at.strftime('%Y-%m-%d %H:%M:%S')
                }
            })
            
        except json.JSONDecodeError:
            logger.error("잘못된 JSON 형식")
            return JsonResponse({
                'status': 'error',
                'message': '잘못된 요청 형식입니다.'
            }, status=400)
        except Exception as e:
            logger.error(f"그룹 생성 중 오류 발생: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': '그룹 생성 중 오류가 발생했습니다.'
            }, status=500)
    
    return JsonResponse({'status': 'error', 'message': '잘못된 요청 방식입니다.'}, status=405)

@login_required
def update_group(request, group_id):
    """그룹 수정"""
    logger.info(f"=== 그룹 수정 요청 (그룹 ID: {group_id}) ===")
    logger.info(f"요청 사용자: {request.user.username}")
    
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 그룹 수정 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    from .models import Group
    try:
        group = Group.objects.get(id=group_id, station=request.user)
    except Group.DoesNotExist:
        logger.warning(f"존재하지 않는 그룹: {group_id}")
        return JsonResponse({
            'status': 'error',
            'message': '존재하지 않는 그룹입니다.'
        }, status=404)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_name = data.get('name', '').strip()
            
            logger.info(f"그룹 수정 시도: {group.name} -> {new_name}")
            
            # 입력값 검증
            if not new_name:
                logger.warning("새 그룹명이 입력되지 않음")
                return JsonResponse({
                    'status': 'error',
                    'message': '그룹명을 입력해주세요.'
                }, status=400)
            
            if len(new_name) > 100:
                logger.warning(f"그룹명이 너무 김: {len(new_name)}자")
                return JsonResponse({
                    'status': 'error',
                    'message': '그룹명은 100자 이하여야 합니다.'
                }, status=400)
            
            # 중복 체크 (자신 제외)
            if Group.objects.filter(station=request.user, name=new_name).exclude(id=group_id).exists():
                logger.warning(f"중복된 그룹명: {new_name}")
                return JsonResponse({
                    'status': 'error',
                    'message': '이미 존재하는 그룹명입니다.'
                }, status=400)
            
            # 그룹명 업데이트
            old_name = group.name
            group.name = new_name
            group.save()
            
            # 해당 그룹의 고객들의 그룹명도 업데이트
            from Cust_User.models import CustomerProfile
            CustomerProfile.objects.filter(group=old_name).update(group=new_name)
            
            logger.info(f"그룹 수정 완료: {old_name} -> {new_name}")
            
            return JsonResponse({
                'status': 'success',
                'message': '그룹이 성공적으로 수정되었습니다.',
                'group': {
                    'id': group.id,
                    'name': group.name,
                    'created_at': group.created_at.strftime('%Y-%m-%d %H:%M:%S')
                }
            })
            
        except json.JSONDecodeError:
            logger.error("잘못된 JSON 형식")
            return JsonResponse({
                'status': 'error',
                'message': '잘못된 요청 형식입니다.'
            }, status=400)
        except Exception as e:
            logger.error(f"그룹 수정 중 오류 발생: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': '그룹 수정 중 오류가 발생했습니다.'
            }, status=500)
    
    return JsonResponse({'status': 'error', 'message': '잘못된 요청 방식입니다.'}, status=405)

@login_required
def delete_group(request, group_id):
    """그룹 삭제"""
    logger.info(f"=== 그룹 삭제 요청 (그룹 ID: {group_id}) ===")
    logger.info(f"요청 사용자: {request.user.username}")
    
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 그룹 삭제 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    from .models import Group
    try:
        group = Group.objects.get(id=group_id, station=request.user)
    except Group.DoesNotExist:
        logger.warning(f"존재하지 않는 그룹: {group_id}")
        return JsonResponse({
            'status': 'error',
            'message': '존재하지 않는 그룹입니다.'
        }, status=404)
    
    if request.method == 'POST':
        try:
            group_name = group.name
            logger.info(f"그룹 삭제 시도: {group_name}")
            
            # 해당 그룹의 고객들의 그룹명을 None으로 설정
            from Cust_User.models import CustomerProfile
            CustomerProfile.objects.filter(group=group_name).update(group=None)
            
            # 그룹 삭제
            group.delete()
            
            logger.info(f"그룹 삭제 완료: {group_name}")
            
            return JsonResponse({
                'status': 'success',
                'message': '그룹이 성공적으로 삭제되었습니다.'
            })
            
        except Exception as e:
            logger.error(f"그룹 삭제 중 오류 발생: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': '그룹 삭제 중 오류가 발생했습니다.'
            }, status=500)
    
    return JsonResponse({'status': 'error', 'message': '잘못된 요청 방식입니다.'}, status=405)

@login_required
def get_groups(request):
    """그룹 목록 조회 (AJAX)"""
    logger.info("=== 그룹 목록 조회 요청 ===")
    logger.info(f"요청 사용자: {request.user.username}")
    
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 그룹 목록 조회 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        from .models import Group
        groups = Group.objects.filter(station=request.user).order_by('-created_at')
        
        groups_list = []
        for group in groups:
            groups_list.append({
                'id': group.id,
                'name': group.name,
                'customer_count': group.get_customer_count(),
                'created_at': group.created_at.strftime('%Y-%m-%d %H:%M:%S')
            })
        
        logger.info(f"그룹 목록 조회 완료: {len(groups_list)}개")
        
        return JsonResponse({
            'status': 'success',
            'groups': groups_list
        })
        
    except Exception as e:
        logger.error(f"그룹 목록 조회 중 오류 발생: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': '그룹 목록을 불러오는 중 오류가 발생했습니다.'
        }, status=500)

@login_required
def get_current_month_visitors(request):
    """금월 방문 고객 정보 조회 API"""
    try:
        from Cust_UserApp.models import CustomerVisitHistory
        from datetime import datetime
        from django.utils import timezone
        
        current_month = timezone.now().month
        current_year = timezone.now().year
        
        # 금월 방문 고객 정보 조회
        current_month_visits = CustomerVisitHistory.objects.filter(
            station=request.user,
            visit_date__year=current_year,
            visit_date__month=current_month
        ).select_related('customer', 'customer__customer_profile')
        
        # 고객별 방문 횟수와 주유 금액 집계
        visitor_stats = {}
        for visit in current_month_visits:
            customer_id = visit.customer.id
            if customer_id not in visitor_stats:
                visitor_stats[customer_id] = {
                    'customer': visit.customer,
                    'visit_count': 0,
                    'total_amount': 0
                }
            visitor_stats[customer_id]['visit_count'] += 1
            visitor_stats[customer_id]['total_amount'] += float(visit.sale_amount or 0)
        
        # 방문 횟수 기준으로 정렬 (내림차순)
        sorted_visitors = sorted(
            visitor_stats.values(),
            key=lambda x: x['visit_count'],
            reverse=True
        )
        
        # 총 방문 고객 수와 총 주유 금액 계산
        total_visitors = len(sorted_visitors)
        total_amount = sum(visitor['total_amount'] for visitor in sorted_visitors)
        
        # 응답 데이터 구성
        visitors_data = []
        for visitor in sorted_visitors:
            customer = visitor['customer']
            # 전화번호는 CustomerProfile에서 가져오기
            phone = ''
            if hasattr(customer, 'customer_profile') and customer.customer_profile:
                phone = customer.customer_profile.customer_phone or ''
            visitors_data.append({
                'customer_id': customer.id,  # 반드시 포함!
                'customer_name': customer.username if customer.username else '고객',
                'phone': phone,
                'visit_count': visitor['visit_count'],
                'total_amount': visitor['total_amount']
            })
        
        return JsonResponse({
            'success': True,
            'total_visitors': total_visitors,
            'total_amount': total_amount,
            'visitors': visitors_data
        })
        
    except Exception as e:
        logger.error(f"금월 방문 고객 정보 조회 중 오류: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': '데이터를 불러오는 중 오류가 발생했습니다.'
        })

@login_required
def get_previous_month_visitors(request):
    """전월 방문 고객 정보 조회 API"""
    try:
        from Cust_UserApp.models import CustomerVisitHistory
        from datetime import datetime
        from django.utils import timezone
        
        current_month = timezone.now().month
        current_year = timezone.now().year
        
        # 이전 월 계산
        if current_month == 1:
            previous_month = 12
            previous_year = current_year - 1
        else:
            previous_month = current_month - 1
            previous_year = current_year
        
        # 전월 방문 고객 정보 조회
        previous_month_visits = CustomerVisitHistory.objects.filter(
            station=request.user,
            visit_date__year=previous_year,
            visit_date__month=previous_month
        ).select_related('customer', 'customer__customer_profile')
        
        # 고객별 방문 횟수와 주유 금액 집계
        visitor_stats = {}
        for visit in previous_month_visits:
            customer_id = visit.customer.id
            if customer_id not in visitor_stats:
                visitor_stats[customer_id] = {
                    'customer': visit.customer,
                    'visit_count': 0,
                    'total_amount': 0
                }
            visitor_stats[customer_id]['visit_count'] += 1
            visitor_stats[customer_id]['total_amount'] += float(visit.sale_amount or 0)
        
        # 방문 횟수 기준으로 정렬 (내림차순)
        sorted_visitors = sorted(
            visitor_stats.values(),
            key=lambda x: x['visit_count'],
            reverse=True
        )
        
        # 총 방문 고객 수와 총 주유 금액 계산
        total_visitors = len(sorted_visitors)
        total_amount = sum(visitor['total_amount'] for visitor in sorted_visitors)
        
        # 응답 데이터 구성
        visitors_data = []
        for visitor in sorted_visitors:
            customer = visitor['customer']
            # 전화번호는 CustomerProfile에서 가져오기
            phone = ''
            if hasattr(customer, 'customer_profile') and customer.customer_profile:
                phone = customer.customer_profile.customer_phone or ''
            visitors_data.append({
                'customer_id': customer.id,  # 반드시 포함!
                'customer_name': customer.username if customer.username else '고객',
                'phone': phone,
                'visit_count': visitor['visit_count'],
                'total_amount': visitor['total_amount']
            })
        
        return JsonResponse({
            'success': True,
            'total_visitors': total_visitors,
            'total_amount': total_amount,
            'visitors': visitors_data
        })
        
    except Exception as e:
        logger.error(f"전월 방문 고객 정보 조회 중 오류: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': '데이터를 불러오는 중 오류가 발생했습니다.'
        })

@login_required
def check_phone_mapping(request):
    """폰번호로 연동 정보 조회"""
    logger.info("=== 폰번호 연동 정보 조회 시작 ===")
    
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 접근 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    if request.method == 'GET':
        phone = request.GET.get('phone', '').strip()
        
        if not phone:
            return JsonResponse({
                'status': 'error',
                'message': '전화번호를 입력해주세요.'
            }, status=400)
        
        # 전화번호 형식 정리
        phone = re.sub(r'[^0-9]', '', phone)
        
        try:
            # 폰번호로 연동 정보 찾기
            phone_mapping = PhoneCardMapping.find_by_phone(phone, station=request.user)
            
            if phone_mapping:
                return JsonResponse({
                    'status': 'success',
                    'exists': True,
                    'data': {
                        'phone_number': phone_mapping.phone_number,
                        'card_number': phone_mapping.membership_card.full_number,
                        'is_used': phone_mapping.is_used,
                        'linked_user': phone_mapping.linked_user.username if phone_mapping.linked_user else None,
                        'created_at': phone_mapping.created_at.strftime('%Y-%m-%d %H:%M:%S')
                    }
                })
            else:
                return JsonResponse({
                    'status': 'success',
                    'exists': False,
                    'message': '해당 전화번호로 등록된 연동 정보가 없습니다.'
                })
                
        except Exception as e:
            logger.error(f"폰번호 연동 정보 조회 중 오류: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': '연동 정보 조회 중 오류가 발생했습니다.'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': '잘못된 요청 방식입니다.'
    }, status=405)

@login_required
def search_card_by_number(request):
    """카드번호로 카드 정보 조회"""
    logger.info("=== 카드번호 조회 시작 ===")
    
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 접근 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    if request.method == 'GET':
        card_number = request.GET.get('card_number', '').strip()
        
        if not card_number:
            return JsonResponse({
                'status': 'error',
                'message': '카드번호를 입력해주세요.'
            }, status=400)
        
        # 카드번호 형식 정리 (숫자만 추출)
        card_number = re.sub(r'[^0-9]', '', card_number)
        
        if len(card_number) < 4:
            return JsonResponse({
                'status': 'error',
                'message': '카드번호는 최소 4자리 이상 입력해주세요.'
            }, status=400)
        
        try:
            # 카드번호로 카드 찾기 (부분 매칭)
            from .models import PointCard
            cards = PointCard.objects.filter(number__icontains=card_number).order_by('number')[:10]  # 최대 10개까지만 반환
            
            if cards.exists():
                # 실시간 검색과 동일한 형식으로 카드 데이터 변환
                cards_data = []
                for card in cards:
                    cards_data.append({
                        'id': card.id,
                        'card_number': card.full_number,
                        'card_number_short': card.number,
                        'is_used': card.is_used,
                        'tids': ", ".join(card.tids) if card.tids else None,
                        'created_at': card.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                        'updated_at': card.updated_at.strftime('%Y-%m-%d %H:%M:%S')
                    })
                
                return JsonResponse({
                    'status': 'success',
                    'exists': True,
                    'cards': cards_data,
                    'total_count': cards.count()
                })
            else:
                return JsonResponse({
                    'status': 'success',
                    'exists': False,
                    'message': '해당 카드번호로 등록된 카드가 없습니다.'
                })
                
        except Exception as e:
            logger.error(f"카드번호 조회 중 오류: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': '카드 정보 조회 중 오류가 발생했습니다.'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': '잘못된 요청 방식입니다.'
    }, status=405)

@login_required
def search_cards_by_number_partial(request):
    """카드번호 부분 입력으로 카드 검색 (실시간 검색용)"""
    logger.info("=== 실시간 카드번호 검색 시작 ===")
    
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 접근 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    if request.method == 'GET':
        card_number = request.GET.get('card_number', '').strip()
        
        if not card_number:
            return JsonResponse({
                'status': 'success',
                'cards': []
            })
        
        # 카드번호 형식 정리 (숫자만 추출)
        card_number = re.sub(r'[^0-9]', '', card_number)
        
        # 최소 4자리 이상 입력된 경우에만 검색
        if len(card_number) < 4:
            return JsonResponse({
                'status': 'success',
                'cards': []
            })
        
        try:
            # 카드번호로 카드 검색 (부분 매칭)
            from .models import PointCard
            logger.info(f"검색할 카드번호: {card_number}")
            
            # 16자리 카드번호에서 어느 위치든 입력된 숫자가 포함되는 카드 검색
            cards = PointCard.objects.filter(
                number__icontains=card_number
            ).order_by('number')[:10]  # 최대 10개까지만 반환
            
            logger.info(f"검색된 카드 수: {cards.count()}")
            
            cards_data = []
            for card in cards:
                # 카드 상태 정보
                status = "사용 중" if card.is_used else "미사용"
                status_class = "text-danger" if card.is_used else "text-success"
                
                # TID 정보
                tid_info = ""
                if card.tids:
                    tid_info = ", ".join(card.tids)
                
                cards_data.append({
                    'card_number': card.full_number,
                    'card_number_short': card.number,
                    'is_used': card.is_used,
                    'status': status,
                    'status_class': status_class,
                    'tids': tid_info,
                    'created_at': card.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    'updated_at': card.updated_at.strftime('%Y-%m-%d %H:%M:%S')
                })
            
            logger.info(f"반환할 카드 데이터: {cards_data}")
            response_data = {
                'status': 'success',
                'cards': cards_data,
                'count': len(cards_data)
            }
            logger.info(f"최종 응답: {response_data}")
            return JsonResponse(response_data)
                
        except Exception as e:
            logger.error(f"실시간 카드번호 검색 중 오류: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': '카드 검색 중 오류가 발생했습니다.'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': '잘못된 요청 방식입니다.'
    }, status=405)

@require_GET
@login_required
def api_visit_history(request):
    """
    [고객 방문 이력 조회 API]
    - GET 파라미터: customer_id
    - 해당 고객의 방문 이력(날짜, 시간, 금액, 유종 등) 리스트 반환
    - 오류 시 JSON 에러 반환
    """
    from Cust_UserApp.models import CustomerVisitHistory  # import 누락 방지
    import logging
    logger = logging.getLogger(__name__)
    customer_id = request.GET.get('customer_id')
    logger.info(f"[api_visit_history] customer_id: {customer_id}")
    # 주유소 회원만 접근 가능
    if not request.user.is_station:
        logger.warning("[api_visit_history] 비회원 주유소 접근")
        return JsonResponse({'error': '주유소 회원만 접근할 수 있습니다.'}, status=403)
    # 필수 파라미터 체크
    if not customer_id:
        logger.warning("[api_visit_history] 고객 ID 없음")
        return JsonResponse({'error': '고객 ID가 필요합니다.'}, status=400)
    try:
        from Cust_User.models import CustomUser
        customer = CustomUser.objects.get(id=customer_id)
        logger.info(f"[api_visit_history] customer: {customer} ({customer.username})")
    except CustomUser.DoesNotExist:
        logger.warning(f"[api_visit_history] 고객({customer_id}) 없음")
        return JsonResponse({'error': '고객을 찾을 수 없습니다.'}, status=404)
    # 방문 이력 쿼리 (해당 주유소 기준)
    visits = CustomerVisitHistory.objects.filter(
        customer=customer,
        station=request.user
    ).order_by('-visit_date', '-visit_time')
    logger.info(f"[api_visit_history] visits count: {visits.count()}")
    records = []
    for v in visits:
        logger.info(f"[api_visit_history] visit: {v.visit_date} {v.visit_time} {v.sale_amount} {v.product_pack}")
        records.append({
            'date': v.visit_date.strftime('%Y-%m-%d') if v.visit_date else '',
            'time': v.visit_time.strftime('%H:%M') if v.visit_time else '',
            'amount': int(v.sale_amount) if v.sale_amount else 0,
            'product': v.product_pack or ''
        })
    logger.info(f"[api_visit_history] records len: {len(records)}")
    return JsonResponse({'records': records})


# ========== 자동 쿠폰 관련 API ==========

@login_required
@require_http_methods(["POST"])
def configure_auto_coupons(request):
    """자동 쿠폰 설정"""
    if not request.user.is_station:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        coupon_type = request.POST.get('coupon_type')
        
        if coupon_type == 'signup':
            return configure_signup_coupon(request)
        elif coupon_type == 'cumulative':
            return configure_cumulative_coupon(request)
        elif coupon_type == 'monthly':
            return configure_monthly_coupon(request)
        else:
            return JsonResponse({'status': 'error', 'message': '유효하지 않은 쿠폰 유형입니다.'})
            
    except Exception as e:
        logger.error(f"자동 쿠폰 설정 오류: {str(e)}")
        return JsonResponse({'status': 'error', 'message': '설정 중 오류가 발생했습니다.'})


def configure_signup_coupon(request):
    """회원가입 쿠폰 설정"""
    from .models import CouponType, CouponTemplate
    from datetime import datetime
    
    enabled = request.POST.get('enabled') == 'true'
    coupon_name = request.POST.get('coupon_name')
    benefit_type = request.POST.get('benefit_type')
    discount_amount = request.POST.get('discount_amount')
    product_name = request.POST.get('product_name')
    description = request.POST.get('description')
    is_permanent = request.POST.get('is_permanent') == 'true'
    valid_from = request.POST.get('valid_from')
    valid_until = request.POST.get('valid_until')
    
    # 날짜 변환
    valid_from_date = None
    valid_until_date = None
    if not is_permanent:
        if valid_from:
            try:
                valid_from_date = datetime.strptime(valid_from, '%Y-%m-%d').date()
            except ValueError:
                valid_from_date = None
        if valid_until:
            try:
                valid_until_date = datetime.strptime(valid_until, '%Y-%m-%d').date()
            except ValueError:
                valid_until_date = None
    
    if enabled and not all([coupon_name, benefit_type]):
        return JsonResponse({'status': 'error', 'message': '필수 정보를 모두 입력해주세요.'})
    
    # 회원가입 쿠폰 유형 확인/생성
    signup_type, created = CouponType.objects.get_or_create(
        station=request.user,
        type_code='SIGNUP',
        defaults={
            'type_name': '회원가입',
            'is_default': True
        }
    )
    
    if enabled:
        # 기존 회원가입 쿠폰 템플릿 비활성화
        CouponTemplate.objects.filter(
            station=request.user,
            coupon_type=signup_type,
            is_active=True
        ).update(is_active=False)
        
        # 새 템플릿 생성 또는 업데이트
        template, created = CouponTemplate.objects.update_or_create(
            station=request.user,
            coupon_type=signup_type,
            coupon_name=coupon_name,
            defaults={
                'benefit_type': benefit_type,
                'discount_amount': discount_amount if benefit_type in ['DISCOUNT', 'BOTH'] else None,
                'product_name': product_name if benefit_type in ['PRODUCT', 'BOTH'] else None,
                'description': description,
                'is_permanent': is_permanent,
                'valid_from': valid_from_date,
                'valid_until': valid_until_date,
                'is_active': True
            }
        )
    else:
        # 모든 회원가입 쿠폰 템플릿 비활성화
        CouponTemplate.objects.filter(
            station=request.user,
            coupon_type=signup_type
        ).update(is_active=False)
    
    return JsonResponse({
        'status': 'success',
        'message': f'회원가입 쿠폰이 {"활성화" if enabled else "비활성화"}되었습니다.'
    })


def configure_cumulative_coupon(request):
    """누적매출 쿠폰 설정"""
    from .models import CouponType, CouponTemplate, CumulativeSalesTracker
    from datetime import datetime
    
    enabled = request.POST.get('enabled') == 'true'
    coupon_name = request.POST.get('coupon_name')
    benefit_type = request.POST.get('benefit_type')
    discount_amount = request.POST.get('discount_amount')
    product_name = request.POST.get('product_name')
    description = request.POST.get('description')
    threshold_amount = request.POST.get('threshold_amount')
    is_permanent = request.POST.get('is_permanent') == 'true'
    valid_from = request.POST.get('valid_from')
    valid_until = request.POST.get('valid_until')
    
    # 날짜 변환
    valid_from_date = None
    valid_until_date = None
    if not is_permanent:
        if valid_from:
            try:
                valid_from_date = datetime.strptime(valid_from, '%Y-%m-%d').date()
            except ValueError:
                valid_from_date = None
        if valid_until:
            try:
                valid_until_date = datetime.strptime(valid_until, '%Y-%m-%d').date()
            except ValueError:
                valid_until_date = None
    
    if enabled:
        if not all([coupon_name, benefit_type]):
            return JsonResponse({'status': 'error', 'message': '필수 정보를 모두 입력해주세요.'})
        if not threshold_amount or int(threshold_amount) <= 0:
            return JsonResponse({'status': 'error', 'message': '유효한 임계값을 입력해주세요.'})
    
    # 누적매출 쿠폰 유형 확인/생성
    cumulative_type, created = CouponType.objects.get_or_create(
        station=request.user,
        type_code='CUMULATIVE',
        defaults={
            'type_name': '누적매출',
            'is_default': True
        }
    )
    
    if enabled:
        # 기존 누적매출 쿠폰 템플릿 비활성화
        CouponTemplate.objects.filter(
            station=request.user,
            coupon_type=cumulative_type,
            is_active=True
        ).update(is_active=False)
        
        # 새 템플릿 생성 또는 업데이트
        template, created = CouponTemplate.objects.update_or_create(
            station=request.user,
            coupon_type=cumulative_type,
            coupon_name=coupon_name,
            defaults={
                'benefit_type': benefit_type,
                'discount_amount': discount_amount if benefit_type in ['DISCOUNT', 'BOTH'] else None,
                'product_name': product_name if benefit_type in ['PRODUCT', 'BOTH'] else None,
                'description': description,
                'is_permanent': is_permanent,
                'valid_from': valid_from_date,
                'valid_until': valid_until_date,
                'is_active': True
            }
        )
        
        # 기존 추적기들의 임계값 업데이트
        CumulativeSalesTracker.objects.filter(
            station=request.user
        ).update(threshold_amount=threshold_amount)
        
    else:
        # 모든 누적매출 쿠폰 템플릿 비활성화
        CouponTemplate.objects.filter(
            station=request.user,
            coupon_type=cumulative_type
        ).update(is_active=False)
    
    return JsonResponse({
        'status': 'success',
        'message': f'누적매출 쿠폰이 {"활성화" if enabled else "비활성화"}되었습니다.'
    })


def configure_monthly_coupon(request):
    """전월매출 쿠폰 설정"""
    from .models import CouponType, CouponTemplate
    from datetime import datetime
    
    enabled = request.POST.get('enabled') == 'true'
    coupon_name = request.POST.get('coupon_name')
    benefit_type = request.POST.get('benefit_type')
    discount_amount = request.POST.get('discount_amount')
    product_name = request.POST.get('product_name')
    description = request.POST.get('description')
    threshold_amount = request.POST.get('threshold_amount')
    is_permanent = request.POST.get('is_permanent') == 'true'
    valid_from = request.POST.get('valid_from')
    valid_until = request.POST.get('valid_until')
    
    # 날짜 변환
    valid_from_date = None
    valid_until_date = None
    if not is_permanent:
        if valid_from:
            try:
                valid_from_date = datetime.strptime(valid_from, '%Y-%m-%d').date()
            except ValueError:
                valid_from_date = None
        if valid_until:
            try:
                valid_until_date = datetime.strptime(valid_until, '%Y-%m-%d').date()
            except ValueError:
                valid_until_date = None
    
    if enabled:
        if not all([coupon_name, benefit_type]):
            return JsonResponse({'status': 'error', 'message': '필수 정보를 모두 입력해주세요.'})
        if not threshold_amount or int(threshold_amount) <= 0:
            return JsonResponse({'status': 'error', 'message': '유효한 기준 금액을 입력해주세요.'})
    
    # 전월매출 쿠폰 유형 확인/생성
    monthly_type, created = CouponType.objects.get_or_create(
        station=request.user,
        type_code='MONTHLY',
        defaults={
            'type_name': '전월매출',
            'is_default': True
        }
    )
    
    if enabled:
        # 기존 전월매출 쿠폰 템플릿 비활성화
        CouponTemplate.objects.filter(
            station=request.user,
            coupon_type=monthly_type,
            is_active=True
        ).update(is_active=False)
        
        # 새 템플릿 생성 또는 업데이트
        template, created = CouponTemplate.objects.update_or_create(
            station=request.user,
            coupon_type=monthly_type,
            coupon_name=coupon_name,
            defaults={
                'benefit_type': benefit_type,
                'discount_amount': discount_amount if benefit_type in ['DISCOUNT', 'BOTH'] else None,
                'product_name': product_name if benefit_type in ['PRODUCT', 'BOTH'] else None,
                'description': description,
                'is_permanent': is_permanent,
                'valid_from': valid_from_date,
                'valid_until': valid_until_date,
                'is_active': True,
                'extra_data': {'threshold_amount': threshold_amount}  # 임계값 저장
            }
        )
    else:
        # 모든 전월매출 쿠폰 템플릿 비활성화
        CouponTemplate.objects.filter(
            station=request.user,
            coupon_type=monthly_type
        ).update(is_active=False)
    
    return JsonResponse({
        'status': 'success',
        'message': f'전월매출 쿠폰이 {"활성화" if enabled else "비활성화"}되었습니다.'
    })


@login_required
@require_http_methods(["GET"])
def get_auto_coupon_status(request):
    """자동 쿠폰 설정 상태 조회"""
    if not request.user.is_station:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        from .models import CouponType, CouponTemplate, CumulativeSalesTracker
        
        status = {}
        
        # 회원가입 쿠폰 상태
        signup_templates = CouponTemplate.objects.filter(
            station=request.user,
            coupon_type__type_code='SIGNUP',
            is_active=True
        )
        signup_template = signup_templates.first()
        status['signup'] = {
            'enabled': signup_templates.exists(),
            'coupon_name': signup_template.coupon_name if signup_template else None,
            'benefit_type': signup_template.benefit_type if signup_template else None,
            'discount_amount': signup_template.discount_amount if signup_template else None,
            'product_name': signup_template.product_name if signup_template else None,
            'description': signup_template.description if signup_template else None,
            'is_permanent': signup_template.is_permanent if signup_template else False,
            'valid_from': signup_template.valid_from.strftime('%Y-%m-%d') if signup_template and signup_template.valid_from else None,
            'valid_until': signup_template.valid_until.strftime('%Y-%m-%d') if signup_template and signup_template.valid_until else None
        }
        
        # 누적매출 쿠폰 상태
        cumulative_templates = CouponTemplate.objects.filter(
            station=request.user,
            coupon_type__type_code='CUMULATIVE',
            is_active=True
        )
        cumulative_template = cumulative_templates.first()
        cumulative_tracker = CumulativeSalesTracker.objects.filter(
            station=request.user
        ).first()
        
        status['cumulative'] = {
            'enabled': cumulative_templates.exists(),
            'coupon_name': cumulative_template.coupon_name if cumulative_template else None,
            'benefit_type': cumulative_template.benefit_type if cumulative_template else None,
            'discount_amount': cumulative_template.discount_amount if cumulative_template else None,
            'product_name': cumulative_template.product_name if cumulative_template else None,
            'description': cumulative_template.description if cumulative_template else None,
            'threshold_amount': float(cumulative_tracker.threshold_amount) if cumulative_tracker else 50000,
            'is_permanent': cumulative_template.is_permanent if cumulative_template else False,
            'valid_from': cumulative_template.valid_from.strftime('%Y-%m-%d') if cumulative_template and cumulative_template.valid_from else None,
            'valid_until': cumulative_template.valid_until.strftime('%Y-%m-%d') if cumulative_template and cumulative_template.valid_until else None
        }
        
        # 전월매출 쿠폰 상태
        monthly_templates = CouponTemplate.objects.filter(
            station=request.user,
            coupon_type__type_code='MONTHLY',
            is_active=True
        )
        monthly_template = monthly_templates.first()
        monthly_threshold = None
        if monthly_template and hasattr(monthly_template, 'extra_data') and monthly_template.extra_data:
            monthly_threshold = monthly_template.extra_data.get('threshold_amount', 50000)
        
        status['monthly'] = {
            'enabled': monthly_templates.exists(),
            'coupon_name': monthly_template.coupon_name if monthly_template else None,
            'benefit_type': monthly_template.benefit_type if monthly_template else None,
            'discount_amount': monthly_template.discount_amount if monthly_template else None,
            'product_name': monthly_template.product_name if monthly_template else None,
            'description': monthly_template.description if monthly_template else None,
            'threshold_amount': monthly_threshold or 50000,
            'is_permanent': monthly_template.is_permanent if monthly_template else False,
            'valid_from': monthly_template.valid_from.strftime('%Y-%m-%d') if monthly_template and monthly_template.valid_from else None,
            'valid_until': monthly_template.valid_until.strftime('%Y-%m-%d') if monthly_template and monthly_template.valid_until else None
        }
        
        return JsonResponse({'status': 'success', 'data': status})
        
    except Exception as e:
        logger.error(f"자동 쿠폰 상태 조회 오류: {str(e)}")
        return JsonResponse({'status': 'error', 'message': '상태 조회 중 오류가 발생했습니다.'})


@login_required
@require_http_methods(["GET"])
def get_coupon_types(request):
    """쿠폰 유형 목록 조회"""
    if not request.user.is_station:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        from .models import CouponType
        
        coupon_types = CouponType.objects.filter(
            station=request.user
        ).values('id', 'type_code', 'type_name')
        
        return JsonResponse({
            'status': 'success',
            'data': list(coupon_types)
        })
        
    except Exception as e:
        logger.error(f"쿠폰 유형 조회 오류: {str(e)}")
        return JsonResponse({'status': 'error', 'message': '조회 중 오류가 발생했습니다.'})


# ========== 쿠폰 구매 요청 관련 API ==========

@login_required
@require_http_methods(["POST"])
def request_coupon_purchase(request):
    """쿠폰 구매 요청"""
    if not request.user.is_station:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        from .models import CouponPurchaseRequest
        
        quantity = request.POST.get('quantity')
        
        # 유효성 검증
        try:
            quantity = int(quantity)
        except (ValueError, TypeError):
            return JsonResponse({'status': 'error', 'message': '유효한 수량을 입력해주세요.'})
        
        if quantity <= 0 or quantity > 1000:
            return JsonResponse({'status': 'error', 'message': '수량은 1~1000개 사이여야 합니다.'})
        
        # 중복 요청 체크
        existing_request = CouponPurchaseRequest.objects.filter(
            station=request.user,
            status='PENDING'
        ).exists()
        
        if existing_request:
            return JsonResponse({'status': 'error', 'message': '이미 처리 중인 구매 요청이 있습니다.'})
        
        # 구매 요청 생성
        purchase_request = CouponPurchaseRequest.objects.create(
            station=request.user,
            requested_quantity=quantity
        )
        
        return JsonResponse({
            'status': 'success',
            'message': f'{quantity}개 쿠폰 구매 요청이 접수되었습니다.',
            'request_id': purchase_request.id
        })
        
    except Exception as e:
        logger.error(f"쿠폰 구매 요청 오류: {str(e)}")
        return JsonResponse({'status': 'error', 'message': '구매 요청 중 오류가 발생했습니다.'})


@login_required
@require_http_methods(["GET"])
def get_purchase_request_status(request):
    """쿠폰 구매 요청 상태 조회"""
    if not request.user.is_station:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        from .models import CouponPurchaseRequest, StationCouponQuota
        
        # 최근 구매 요청들
        requests = CouponPurchaseRequest.objects.filter(
            station=request.user
        ).order_by('-requested_at')[:10]
        
        request_list = []
        for req in requests:
            request_list.append({
                'id': req.id,
                'quantity': req.requested_quantity,
                'status': req.get_status_display(),
                'status_code': req.status,
                'requested_at': req.requested_at.strftime('%Y-%m-%d %H:%M'),
                'processed_at': req.processed_at.strftime('%Y-%m-%d %H:%M') if req.processed_at else None,
                'notes': req.notes or ''
            })
        
        # 현재 쿠폰 수량 정보
        quota = StationCouponQuota.objects.filter(station=request.user).first()
        quota_info = {
            'total_quota': quota.total_quota if quota else 0,
            'used_quota': quota.used_quota if quota else 0,
            'remaining_quota': quota.remaining_quota if quota else 0
        }
        
        return JsonResponse({
            'status': 'success',
            'data': {
                'requests': request_list,
                'quota': quota_info
            }
        })
        
    except Exception as e:
        logger.error(f"쿠폰 구매 요청 상태 조회 오류: {str(e)}")
        return JsonResponse({'status': 'error', 'message': '상태 조회 중 오류가 발생했습니다.'})


@login_required
@require_http_methods(["GET"])
def get_coupon_statistics(request):
    """쿠폰 관리 통계 조회 API"""
    if not request.user.is_station:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        from django.db.models import Count, Sum, Q, Avg
        from django.utils import timezone
        from datetime import datetime, timedelta
        from .models import (
            CouponTemplate, CustomerCoupon, StationCouponQuota, 
            CouponPurchaseRequest, CumulativeSalesTracker
        )
        
        now = timezone.now()
        current_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_month = (current_month - timedelta(days=1)).replace(day=1)
        
        # 1. 기본 쿠폰 통계
        templates = CouponTemplate.objects.filter(station=request.user)
        total_templates = templates.count()
        active_templates = templates.filter(is_active=True).count()
        
        # 2. 발행 및 사용 통계
        from django.db.models import Q
        station_filter = Q(coupon_template__station=request.user) | Q(auto_coupon_template__station=request.user)
        coupons = CustomerCoupon.objects.filter(station_filter)
        
        # 이번달 발행/사용 통계
        current_month_issued = coupons.filter(
            issued_date__gte=current_month
        ).count()
        
        current_month_used = coupons.filter(
            used_date__gte=current_month,
            status='USED'
        ).count()
        
        # 전체 통계
        total_issued = coupons.count()
        total_used = coupons.filter(status='USED').count()
        total_available = coupons.filter(status='AVAILABLE').count()
        total_expired = coupons.filter(status='EXPIRED').count()
        
        # 사용률 계산
        usage_rate = (total_used / total_issued * 100) if total_issued > 0 else 0
        
        # 3. 쿠폰 타입별 통계
        type_stats = []
        for template in templates.filter(is_active=True):
            template_coupons = coupons.filter(coupon_template=template)
            issued_count = template_coupons.count()
            used_count = template_coupons.filter(status='USED').count()
            
            type_stats.append({
                'name': template.coupon_name,
                'type_code': template.coupon_type.type_code,
                'issued': issued_count,
                'used': used_count,
                'usage_rate': (used_count / issued_count * 100) if issued_count > 0 else 0
            })
        
        # 4. 월별 발행 추이 (최근 6개월)
        monthly_stats = []
        for i in range(6):
            month_start = (current_month - timedelta(days=32*i)).replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            month_issued = coupons.filter(
                issued_date__gte=month_start,
                issued_date__lte=month_end
            ).count()
            
            month_used = coupons.filter(
                used_date__gte=month_start,
                used_date__lte=month_end,
                status='USED'
            ).count()
            
            monthly_stats.append({
                'month': month_start.strftime('%Y-%m'),
                'issued': month_issued,
                'used': month_used
            })
        
        monthly_stats.reverse()  # 시간순으로 정렬
        
        # 5. 쿠폰 수량 정보
        quota = StationCouponQuota.objects.filter(station=request.user).first()
        quota_info = {
            'total_quota': quota.total_quota if quota else 0,
            'used_quota': quota.used_quota if quota else 0,
            'remaining_quota': quota.remaining_quota if quota else 0,
            'quota_usage_rate': (quota.used_quota / quota.total_quota * 100) if quota and quota.total_quota > 0 else 0
        }
        
        # 6. 구매 요청 통계
        purchase_requests = CouponPurchaseRequest.objects.filter(station=request.user)
        purchase_stats = {
            'total_requests': purchase_requests.count(),
            'pending_requests': purchase_requests.filter(status='PENDING').count(),
            'approved_requests': purchase_requests.filter(status='APPROVED').count(),
            'rejected_requests': purchase_requests.filter(status='REJECTED').count(),
        }
        
        # 7. 자동 쿠폰 시스템 통계
        auto_coupon_stats = {
            'signup_coupons': coupons.filter(
                coupon_template__coupon_type__type_code='SIGNUP'
            ).count(),
            'cumulative_coupons': coupons.filter(
                coupon_template__coupon_type__type_code='CUMULATIVE'
            ).count(),
            'monthly_coupons': coupons.filter(
                coupon_template__coupon_type__type_code='MONTHLY'
            ).count(),
        }
        
        # 8. 최근 활동
        recent_activities = []
        
        # 최근 발행된 쿠폰 (5개)
        recent_issued = coupons.filter(
            issued_date__gte=now - timedelta(days=7)
        ).order_by('-issued_date')[:5]
        
        for coupon in recent_issued:
            recent_activities.append({
                'type': 'issued',
                'message': f'{coupon.customer.username}에게 {coupon.coupon_template.coupon_name} 발행',
                'timestamp': coupon.issued_date.strftime('%Y-%m-%d %H:%M')
            })
        
        # 최근 사용된 쿠폰 (5개)
        recent_used = coupons.filter(
            used_date__gte=now - timedelta(days=7),
            status='USED'
        ).order_by('-used_date')[:5]
        
        for coupon in recent_used:
            recent_activities.append({
                'type': 'used',
                'message': f'{coupon.customer.username}이 {coupon.coupon_template.coupon_name} 사용',
                'timestamp': coupon.used_date.strftime('%Y-%m-%d %H:%M')
            })
        
        # 시간순 정렬
        recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)
        recent_activities = recent_activities[:10]  # 최대 10개
        
        return JsonResponse({
            'status': 'success',
            'data': {
                'basic_stats': {
                    'total_templates': total_templates,
                    'active_templates': active_templates,
                    'total_issued': total_issued,
                    'total_used': total_used,
                    'total_available': total_available,
                    'total_expired': total_expired,
                    'usage_rate': round(usage_rate, 1),
                    'current_month_issued': current_month_issued,
                    'current_month_used': current_month_used
                },
                'type_stats': type_stats,
                'monthly_stats': monthly_stats,
                'quota_info': quota_info,
                'purchase_stats': purchase_stats,
                'auto_coupon_stats': auto_coupon_stats,
                'recent_activities': recent_activities
            }
        })
        
    except Exception as e:
        logger.error(f"쿠폰 통계 조회 오류: {str(e)}")
        return JsonResponse({'status': 'error', 'message': '통계 조회 중 오류가 발생했습니다.'})


# ========== 자동 쿠폰 CRUD API ==========

@login_required
@require_http_methods(["GET"])
def auto_coupon_list(request):
    """자동 쿠폰 템플릿 목록 조회"""
    if not request.user.is_station:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        from .models import AutoCouponTemplate
        
        coupon_type = request.GET.get('type')  # SIGNUP, CUMULATIVE, MONTHLY
        
        templates = AutoCouponTemplate.objects.filter(station=request.user)
        
        if coupon_type:
            templates = templates.filter(coupon_type=coupon_type)
        
        templates = templates.order_by('-created_at')
        
        data = []
        for template in templates:
            data.append({
                'id': template.id,
                'coupon_name': template.coupon_name,
                'coupon_type': template.coupon_type,
                'coupon_type_display': template.get_coupon_type_display(),
                'benefit_type': template.benefit_type,
                'benefit_type_display': template.get_benefit_type_display(),
                'benefit_description': template.get_benefit_description(),
                'discount_amount': float(template.discount_amount),
                'product_name': template.product_name,
                'description': template.description,
                'is_active': template.is_active,
                'issued_count': template.issued_count,
                'total_issued': template.total_issued,
                'total_used': template.total_used,
                'usage_rate': template.get_usage_rate(),
                'is_permanent': template.is_permanent,
                'valid_from': template.valid_from.strftime('%Y-%m-%d') if template.valid_from else None,
                'valid_until': template.valid_until.strftime('%Y-%m-%d') if template.valid_until else None,
                'condition_data': template.condition_data,
                'created_at': template.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                'updated_at': template.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            })
        
        return JsonResponse({
            'status': 'success',
            'data': data,
            'total_count': len(data)
        })
        
    except Exception as e:
        logger.error(f"자동 쿠폰 목록 조회 오류: {str(e)}")
        return JsonResponse({'status': 'error', 'message': '목록 조회 중 오류가 발생했습니다.'})


@login_required
@require_http_methods(["POST"])
def auto_coupon_create(request):
    """새 자동 쿠폰 템플릿 생성"""
    if not request.user.is_station:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        from .models import AutoCouponTemplate
        from datetime import datetime
        
        # 필수 필드 확인
        required_fields = ['coupon_name', 'coupon_type', 'benefit_type']
        for field in required_fields:
            if not request.POST.get(field):
                return JsonResponse({'status': 'error', 'message': f'{field} 필드는 필수입니다.'})
        
        coupon_type = request.POST.get('coupon_type')
        
        # 유효기간 처리
        is_permanent = request.POST.get('is_permanent') == 'true'
        valid_from_date = None
        valid_until_date = None
        
        if not is_permanent:
            valid_from = request.POST.get('valid_from')
            valid_until = request.POST.get('valid_until')
            if valid_from:
                try:
                    valid_from_date = datetime.strptime(valid_from, '%Y-%m-%d').date()
                except ValueError:
                    pass
            if valid_until:
                try:
                    valid_until_date = datetime.strptime(valid_until, '%Y-%m-%d').date()
                except ValueError:
                    pass
        
        # 조건 데이터 처리
        condition_data = {}
        if coupon_type in ['CUMULATIVE', 'MONTHLY']:
            threshold_amount = request.POST.get('threshold_amount')
            if threshold_amount:
                try:
                    condition_data['threshold_amount'] = float(threshold_amount)
                except ValueError:
                    pass
        
        
        
        # 템플릿 생성
        template = AutoCouponTemplate.objects.create(
            station=request.user,
            coupon_type=coupon_type,
            coupon_name=request.POST.get('coupon_name'),
            description=request.POST.get('description', ''),
            benefit_type=request.POST.get('benefit_type'),
            discount_amount=request.POST.get('discount_amount') or 0,
            product_name=request.POST.get('product_name', ''),
            condition_data=condition_data,
            is_permanent=is_permanent,
            valid_from=valid_from_date,
            valid_until=valid_until_date,
            created_by=request.user
        )
        
        return JsonResponse({
            'status': 'success',
            'message': '자동 쿠폰 템플릿이 생성되었습니다.',
            'template_id': template.id
        })
        
    except Exception as e:
        logger.error(f"자동 쿠폰 생성 오류: {str(e)}")
        return JsonResponse({'status': 'error', 'message': '생성 중 오류가 발생했습니다.'})


@login_required
@require_http_methods(["GET"])
def auto_coupon_detail(request, template_id):
    """자동 쿠폰 템플릿 상세 조회"""
    if not request.user.is_station:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        from .models import AutoCouponTemplate
        
        template = AutoCouponTemplate.objects.get(
            id=template_id,
            station=request.user
        )
        
        data = {
            'id': template.id,
            'coupon_name': template.coupon_name,
            'coupon_type': template.coupon_type,
            'coupon_type_display': template.get_coupon_type_display(),
            'benefit_type': template.benefit_type,
            'benefit_type_display': template.get_benefit_type_display(),
            'benefit_description': template.get_benefit_description(),
            'discount_amount': float(template.discount_amount),
            'product_name': template.product_name,
            'description': template.description,
            'is_active': template.is_active,
            'max_issue_count': template.max_issue_count,
            'issued_count': template.issued_count,
            'total_issued': template.total_issued,
            'total_used': template.total_used,
            'usage_rate': template.get_usage_rate(),
            'is_permanent': template.is_permanent,
            'valid_from': template.valid_from.strftime('%Y-%m-%d') if template.valid_from else None,
            'valid_until': template.valid_until.strftime('%Y-%m-%d') if template.valid_until else None,
            'condition_data': template.condition_data,
            'created_at': template.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': template.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
            'created_by': template.created_by.username if template.created_by else None,
        }
        
        return JsonResponse({
            'status': 'success',
            'data': data
        })
        
    except AutoCouponTemplate.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '템플릿을 찾을 수 없습니다.'}, status=404)
    except Exception as e:
        logger.error(f"자동 쿠폰 상세 조회 오류: {str(e)}")
        return JsonResponse({'status': 'error', 'message': '조회 중 오류가 발생했습니다.'})


@login_required
@require_http_methods(["POST", "PUT"])
def auto_coupon_update(request, template_id):
    """자동 쿠폰 템플릿 수정"""
    if not request.user.is_station:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        from .models import AutoCouponTemplate
        from datetime import datetime
        
        template = AutoCouponTemplate.objects.get(
            id=template_id,
            station=request.user
        )
        
        # 필수 필드만 체크 (업데이트는 부분 수정 가능)
        
        # 기본 정보 업데이트
        if request.POST.get('coupon_name'):
            template.coupon_name = request.POST.get('coupon_name')
        if request.POST.get('description') is not None:
            template.description = request.POST.get('description')
        if request.POST.get('benefit_type'):
            template.benefit_type = request.POST.get('benefit_type')
        if request.POST.get('discount_amount') is not None:
            template.discount_amount = request.POST.get('discount_amount', 0)
        if request.POST.get('product_name') is not None:
            template.product_name = request.POST.get('product_name', '')
        
        
        # 유효기간 업데이트
        if 'is_permanent' in request.POST:
            is_permanent = request.POST.get('is_permanent') == 'true'
            template.is_permanent = is_permanent
            
            if not is_permanent:
                valid_from = request.POST.get('valid_from')
                valid_until = request.POST.get('valid_until')
                if valid_from:
                    try:
                        template.valid_from = datetime.strptime(valid_from, '%Y-%m-%d').date()
                    except ValueError:
                        pass
                if valid_until:
                    try:
                        template.valid_until = datetime.strptime(valid_until, '%Y-%m-%d').date()
                    except ValueError:
                        pass
            else:
                template.valid_from = None
                template.valid_until = None
        
        # 조건 데이터 업데이트
        if 'threshold_amount' in request.POST:
            condition_data = template.condition_data.copy()
            
            threshold_amount = request.POST.get('threshold_amount')
            if threshold_amount:
                try:
                    condition_data['threshold_amount'] = float(threshold_amount)
                except ValueError:
                    condition_data.pop('threshold_amount', None)
            else:
                condition_data.pop('threshold_amount', None)
            
            template.condition_data = condition_data
        
        template.save()
        
        return JsonResponse({
            'status': 'success',
            'message': '자동 쿠폰 템플릿이 수정되었습니다.'
        })
        
    except AutoCouponTemplate.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '템플릿을 찾을 수 없습니다.'}, status=404)
    except Exception as e:
        logger.error(f"자동 쿠폰 수정 오류: {str(e)}")
        return JsonResponse({'status': 'error', 'message': '수정 중 오류가 발생했습니다.'})


@login_required
@require_http_methods(["DELETE", "POST"])
def auto_coupon_delete(request, template_id):
    """자동 쿠폰 템플릿 삭제"""
    if not request.user.is_station:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        from .models import AutoCouponTemplate
        
        template = AutoCouponTemplate.objects.get(
            id=template_id,
            station=request.user
        )
        
        # 발행된 쿠폰이 있는지 확인
        if template.total_issued > 0:
            # 발행된 쿠폰이 있으면 비활성화만
            template.is_active = False
            template.save()
            return JsonResponse({
                'status': 'success',
                'message': '발행된 쿠폰이 있어 템플릿을 비활성화했습니다.',
                'action': 'deactivated'
            })
        else:
            # 발행된 쿠폰이 없으면 완전 삭제
            coupon_name = template.coupon_name
            template.delete()
            return JsonResponse({
                'status': 'success',
                'message': f'"{coupon_name}" 템플릿이 삭제되었습니다.',
                'action': 'deleted'
            })
        
    except AutoCouponTemplate.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '템플릿을 찾을 수 없습니다.'}, status=404)
    except Exception as e:
        logger.error(f"자동 쿠폰 삭제 오류: {str(e)}")
        return JsonResponse({'status': 'error', 'message': '삭제 중 오류가 발생했습니다.'})


@login_required
@require_http_methods(["POST"])
def auto_coupon_toggle(request, template_id):
    """자동 쿠폰 템플릿 활성/비활성 토글"""
    if not request.user.is_station:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        from .models import AutoCouponTemplate
        
        template = AutoCouponTemplate.objects.get(
            id=template_id,
            station=request.user
        )
        
        template.is_active = not template.is_active
        template.save()
        
        status_text = "활성화" if template.is_active else "비활성화"
        
        return JsonResponse({
            'status': 'success',
            'message': f'"{template.coupon_name}" 템플릿이 {status_text}되었습니다.',
            'is_active': template.is_active
        })
        
    except AutoCouponTemplate.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '템플릿을 찾을 수 없습니다.'}, status=404)
    except Exception as e:
        logger.error(f"자동 쿠폰 토글 오류: {str(e)}")
        return JsonResponse({'status': 'error', 'message': '상태 변경 중 오류가 발생했습니다.'})



@login_required
@require_http_methods(["GET"])
def auto_coupon_stats(request, template_id):
    """자동 쿠폰 템플릿별 상세 통계"""
    if not request.user.is_station:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        from .models import AutoCouponTemplate
        from django.utils import timezone
        from datetime import timedelta
        
        template = AutoCouponTemplate.objects.get(
            id=template_id,
            station=request.user
        )
        
        # 기본 통계
        basic_stats = {
            'total_issued': template.total_issued,
            'total_used': template.total_used,
            'usage_rate': template.get_usage_rate(),
            'is_active': template.is_active,
            'is_valid': template.is_valid_today(),
        }
        
        # 최근 7일 발행 추이 (구현 필요)
        daily_stats = []
        
        # 조건별 통계 (구현 필요)
        condition_stats = {}
        
        return JsonResponse({
            'status': 'success',
            'data': {
                'template_info': {
                    'id': template.id,
                        'coupon_type': template.get_coupon_type_display(),
                    'benefit_description': template.get_benefit_description(),
                },
                'basic_stats': basic_stats,
                'daily_stats': daily_stats,
                'condition_stats': condition_stats,
            }
        })
        
    except AutoCouponTemplate.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '템플릿을 찾을 수 없습니다.'}, status=404)
    except Exception as e:
        logger.error(f"자동 쿠폰 통계 조회 오류: {str(e)}")
        return JsonResponse({'status': 'error', 'message': '통계 조회 중 오류가 발생했습니다.'})

@login_required
@csrf_exempt
def upload_cards_excel(request):
    """엑셀 파일을 통한 카드 일괄 등록"""
    logger.info(f"=== 엑셀 카드 업로드 요청 시작 ===")
    logger.info(f"사용자: {request.user.username}")
    logger.info(f"메소드: {request.method}")
    logger.info(f"Content-Type: {request.content_type}")
    logger.info(f"FILES 키: {list(request.FILES.keys()) if request.FILES else '없음'}")
    logger.info(f"POST 키: {list(request.POST.keys()) if request.POST else '없음'}")
    
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 엑셀 업로드 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    if request.method == 'POST':
        try:
            # 주유소 프로필에서 정유사 코드와 대리점 코드 가져오기
            logger.info(f"주유소 프로필 조회 시작: {request.user.username}")
            station_profile = request.user.station_profile
            logger.info(f"주유소 프로필 조회 결과: {station_profile}")
            
            if not station_profile:
                logger.error(f"주유소 프로필을 찾을 수 없음: {request.user.username}")
                return JsonResponse({
                    'status': 'error',
                    'message': '주유소 프로필 정보가 없습니다.'
                }, status=400)

            # 정유사 코드와 대리점 코드는 기본값 사용 (필수가 아님)
            oil_company_code = getattr(station_profile, 'oil_company_code', '0')
            agency_code = getattr(station_profile, 'agency_code', '000')
            logger.info(f"정유사 코드: {oil_company_code}")
            logger.info(f"대리점 코드: {agency_code}")

            # 파일 업로드 확인
            logger.info("파일 업로드 확인 시작")
            if 'excel_file' not in request.FILES:
                logger.warning("엑셀 파일이 업로드되지 않음")
                logger.warning(f"업로드된 파일 키: {list(request.FILES.keys())}")
                return JsonResponse({
                    'status': 'error',
                    'message': '엑셀 파일을 선택해주세요.'
                }, status=400)
            
            excel_file = request.FILES['excel_file']
            logger.info(f"업로드된 파일명: {excel_file.name}")
            logger.info(f"파일 크기: {excel_file.size} bytes")
            
            # 현재 로그인된 주유소의 TID 값 사용
            tid = station_profile.tid if hasattr(station_profile, 'tid') and station_profile.tid else ''
            logger.info(f"주유소 TID: {tid}")
            
            if not tid:
                logger.warning(f"주유소 {request.user.username}의 TID가 설정되지 않음")
                return JsonResponse({
                    'status': 'error',
                    'message': '주유소 TID가 설정되지 않았습니다. 주유소 프로필에서 TID를 설정해주세요.'
                }, status=400)
            
            # 파일 확장자 검사
            file_name = excel_file.name.lower()
            logger.info(f"파일명 (소문자): {file_name}")
            if not (file_name.endswith('.xlsx') or file_name.endswith('.xls')):
                logger.warning(f"지원하지 않는 파일 형식: {file_name}")
                return JsonResponse({
                    'status': 'error',
                    'message': '엑셀 파일(.xlsx, .xls)만 업로드 가능합니다.'
                }, status=400)
            
            # pandas를 사용하여 엑셀 파일 읽기
            logger.info("엑셀 파일 읽기 시작")
            try:
                import pandas as pd
                import io
                
                # 파일 내용을 메모리에서 읽기
                file_content = excel_file.read()
                excel_file.seek(0)  # 파일 포인터를 처음으로 되돌림
                logger.info(f"파일 내용 읽기 완료: {len(file_content)} bytes")
                
                # 엑셀 파일 읽기
                if file_name.endswith('.xlsx'):
                    logger.info("openpyxl 엔진으로 엑셀 파일 읽기")
                    df = pd.read_excel(io.BytesIO(file_content), engine='openpyxl')
                else:
                    logger.info("xlrd 엔진으로 엑셀 파일 읽기")
                    df = pd.read_excel(io.BytesIO(file_content), engine='xlrd')
                
                logger.info(f"엑셀 파일 읽기 완료: {len(df)}행, {len(df.columns)}열")
                logger.info(f"데이터프레임 컬럼: {list(df.columns)}")
                logger.info(f"첫 번째 행 데이터: {df.iloc[0].tolist() if not df.empty else '빈 데이터'}")
                
            except ImportError as e:
                logger.error(f"pandas 또는 openpyxl이 설치되지 않음: {str(e)}")
                return JsonResponse({
                    'status': 'error',
                    'message': '엑셀 파일 처리를 위한 라이브러리가 설치되지 않았습니다.'
                }, status=500)
            except Exception as e:
                logger.error(f"엑셀 파일 읽기 오류: {str(e)}")
                logger.error(f"오류 타입: {type(e)}")
                import traceback
                logger.error(f"스택 트레이스: {traceback.format_exc()}")
                return JsonResponse({
                    'status': 'error',
                    'message': f'엑셀 파일을 읽을 수 없습니다: {str(e)}'
                }, status=400)
            
            # 데이터 검증 및 처리
            logger.info("데이터 검증 시작")
            if df.empty:
                logger.warning("엑셀 파일에 데이터가 없음")
                return JsonResponse({
                    'status': 'error',
                    'message': '엑셀 파일에 데이터가 없습니다.'
                }, status=400)
            
            # 카드번호가 있는 컬럼 찾기
            logger.info(f"데이터프레임 컬럼: {list(df.columns)}")
            
            # 'point number' 컬럼이 있으면 사용, 없으면 첫 번째 컬럼 사용
            card_column = None
            if 'point number' in df.columns:
                card_column = 'point number'
                logger.info("'point number' 컬럼을 사용합니다.")
            elif 'point_number' in df.columns:
                card_column = 'point_number'
                logger.info("'point_number' 컬럼을 사용합니다.")
            elif 'card_number' in df.columns:
                card_column = 'card_number'
                logger.info("'card_number' 컬럼을 사용합니다.")
            else:
                # 첫 번째 컬럼 사용
                card_column = df.columns[0]
                logger.info(f"첫 번째 컬럼 '{card_column}'을 사용합니다.")
            
            # 카드번호 추출 및 문자열 변환
            card_numbers = df[card_column].astype(str).str.strip()
            logger.info(f"추출된 카드번호 개수: {len(card_numbers)}")
            logger.info(f"첫 5개 카드번호: {card_numbers.head().tolist()}")
            
            # 카드번호 검증
            valid_cards = []
            invalid_cards = []
            
            for idx, card_number in enumerate(card_numbers, 1):
                if pd.isna(card_number) or card_number == '' or card_number == 'nan':
                    logger.debug(f"행 {idx}: 빈 값 건너뛰기")
                    continue
                
                # 소수점 제거 (예: 1234567890123450.0 -> 1234567890123450)
                if '.' in card_number:
                    card_number = card_number.split('.')[0]
                    logger.debug(f"행 {idx}: 소수점 제거 후 {card_number}")
                
                # 16자리 숫자인지 확인
                if len(card_number) == 16 and card_number.isdigit():
                    valid_cards.append(card_number)
                    logger.debug(f"행 {idx}: 유효한 카드번호 {card_number}")
                else:
                    invalid_cards.append(f"행 {idx}: {card_number}")
                    logger.debug(f"행 {idx}: 잘못된 카드번호 {card_number} (길이: {len(card_number)}, 숫자여부: {card_number.isdigit()})")
            
            logger.info(f"유효한 카드번호: {len(valid_cards)}개")
            logger.info(f"잘못된 카드번호: {len(invalid_cards)}개")
            
            if not valid_cards:
                logger.warning("유효한 카드번호가 없음")
                return JsonResponse({
                    'status': 'error',
                    'message': '유효한 카드번호가 없습니다. 16자리 숫자만 입력해주세요.'
                }, status=400)
            
            # 카드 등록 처리
            logger.info("카드 등록 처리 시작")
            registered_count = 0
            duplicate_count = 0
            error_count = 0
            
            for card_number in valid_cards:
                try:
                    logger.debug(f"카드 등록 시도: {card_number}")
                    # get_or_create를 사용하여 중복 생성 방지
                    card, created = PointCard.objects.get_or_create(
                        number=card_number,
                        defaults={
                            'oil_company_code': oil_company_code,
                            'agency_code': agency_code,
                            'tids': []
                        }
                    )
                    
                    if created:
                        registered_count += 1
                        logger.info(f"새 카드 등록: {card_number}")
                    else:
                        duplicate_count += 1
                        logger.info(f"기존 카드 발견: {card_number}")
                    
                    # TID 추가
                    if tid not in card.tids:
                        card.add_tid(tid)
                        logger.info(f"카드에 TID 추가: {tid}")
                    
                    # 카드와 주유소 매핑 생성
                    mapping, mapping_created = StationCardMapping.objects.get_or_create(
                        station=request.user,
                        tid=tid,
                        card=card,
                        defaults={'is_active': True}
                    )
                    
                    # 이미 매핑이 존재하지만 비활성화된 경우 활성화
                    if not mapping_created and not mapping.is_active:
                        mapping.is_active = True
                        mapping.save()
                        logger.info(f"비활성화된 매핑을 활성화함: mapping_id={mapping.id}")
                        
                except Exception as e:
                    error_count += 1
                    logger.error(f"카드 {card_number} 등록 중 오류: {str(e)}")
                    import traceback
                    logger.error(f"스택 트레이스: {traceback.format_exc()}")
            
            # 결과 메시지 생성
            message_parts = []
            if registered_count > 0:
                message_parts.append(f"새로 등록된 카드: {registered_count}장")
            if duplicate_count > 0:
                message_parts.append(f"기존 카드: {duplicate_count}장")
            if error_count > 0:
                message_parts.append(f"오류 발생: {error_count}장")
            if invalid_cards:
                message_parts.append(f"잘못된 형식: {len(invalid_cards)}개")
            
            message = ", ".join(message_parts)
            logger.info(f"업로드 결과: {message}")
            
            details = ""
            if invalid_cards:
                details = f"잘못된 카드번호: {', '.join(invalid_cards[:5])}"
                if len(invalid_cards) > 5:
                    details += f" 외 {len(invalid_cards) - 5}개"
            
            logger.info("=== 엑셀 카드 업로드 요청 완료 ===")
            return JsonResponse({
                'status': 'success',
                'message': f'엑셀 업로드 완료: {message}',
                'details': details,
                'registered_count': registered_count,
                'duplicate_count': duplicate_count,
                'error_count': error_count,
                'invalid_count': len(invalid_cards)
            })
            
        except Exception as e:
            logger.error(f"엑셀 업로드 중 오류 발생: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': f'엑셀 업로드 중 오류가 발생했습니다: {str(e)}'
            }, status=500)
    
    return JsonResponse({'status': 'error', 'message': '잘못된 요청 방식입니다.'}, status=405)

@login_required
def download_customer_template(request):
    """고객 등록 템플릿 다운로드"""
    logger.info(f"=== 고객 등록 템플릿 다운로드 요청 ===")
    logger.info(f"사용자: {request.user.username}")
    
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 템플릿 다운로드 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        # 템플릿 파일 경로
        template_path = os.path.join(
            settings.BASE_DIR, 
            'Cust_StationApp', 
            'templates', 
            'Cust_Station', 
            'customer_sample.xlsx'
        )
        
        logger.info(f"템플릿 파일 경로: {template_path}")
        
        if not os.path.exists(template_path):
            logger.error(f"템플릿 파일이 존재하지 않음: {template_path}")
            return JsonResponse({
                'status': 'error',
                'message': '템플릿 파일을 찾을 수 없습니다.'
            }, status=404)
        
        # 파일 응답
        response = FileResponse(
            open(template_path, 'rb'),
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        response['Content-Disposition'] = 'attachment; filename="고객등록_템플릿.xlsx"'
        
        logger.info("고객 등록 템플릿 다운로드 완료")
        return response
        
    except Exception as e:
        logger.error(f"템플릿 다운로드 중 오류: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': f'템플릿 다운로드 중 오류가 발생했습니다: {str(e)}'
        }, status=500)

@login_required
@csrf_exempt
def upload_customers_excel(request):
    """엑셀 파일을 통한 고객 일괄 등록"""
    logger.info(f"=== 엑셀 고객 업로드 요청 시작 ===")
    logger.info(f"사용자: {request.user.username}")
    logger.info(f"메소드: {request.method}")
    logger.info(f"Content-Type: {request.content_type}")
    logger.info(f"FILES 키: {list(request.FILES.keys()) if request.FILES else '없음'}")
    logger.info(f"POST 키: {list(request.POST.keys()) if request.POST else '없음'}")
    
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 엑셀 업로드 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    if request.method == 'POST':
        try:
            # 주유소 프로필에서 정유사 코드와 대리점 코드 가져오기
            logger.info(f"주유소 프로필 조회 시작: {request.user.username}")
            station_profile = request.user.station_profile
            logger.info(f"주유소 프로필 조회 결과: {station_profile}")
            
            if not station_profile:
                logger.error(f"주유소 프로필을 찾을 수 없음: {request.user.username}")
                return JsonResponse({
                    'status': 'error',
                    'message': '주유소 프로필 정보가 없습니다.'
                }, status=400)

            # 정유사 코드와 대리점 코드는 기본값 사용 (필수가 아님)
            oil_company_code = getattr(station_profile, 'oil_company_code', '0')
            agency_code = getattr(station_profile, 'agency_code', '000')
            logger.info(f"정유사 코드: {oil_company_code}")
            logger.info(f"대리점 코드: {agency_code}")

            # 파일 업로드 확인
            logger.info("파일 업로드 확인 시작")
            if 'excel_file' not in request.FILES:
                logger.warning("엑셀 파일이 업로드되지 않음")
                logger.warning(f"업로드된 파일 키: {list(request.FILES.keys())}")
                return JsonResponse({
                    'status': 'error',
                    'message': '엑셀 파일을 선택해주세요.'
                }, status=400)
            
            excel_file = request.FILES['excel_file']
            logger.info(f"업로드된 파일명: {excel_file.name}")
            logger.info(f"파일 크기: {excel_file.size} bytes")
            
            # 현재 로그인된 주유소의 TID 값 사용
            tid = station_profile.tid if hasattr(station_profile, 'tid') and station_profile.tid else ''
            logger.info(f"주유소 TID: {tid}")
            
            if not tid:
                logger.warning(f"주유소 {request.user.username}의 TID가 설정되지 않음")
                return JsonResponse({
                    'status': 'error',
                    'message': '주유소 TID가 설정되지 않았습니다. 주유소 프로필에서 TID를 설정해주세요.'
                }, status=400)
            
            # 파일 확장자 검사
            file_name = excel_file.name.lower()
            logger.info(f"파일명 (소문자): {file_name}")
            if not (file_name.endswith('.xlsx') or file_name.endswith('.xls')):
                logger.warning(f"지원하지 않는 파일 형식: {file_name}")
                return JsonResponse({
                    'status': 'error',
                    'message': '엑셀 파일(.xlsx, .xls)만 업로드 가능합니다.'
                }, status=400)
            
            # pandas를 사용하여 엑셀 파일 읽기
            logger.info("엑셀 파일 읽기 시작")
            try:
                import pandas as pd
                import io
                
                # 파일 내용을 메모리에서 읽기
                file_content = excel_file.read()
                excel_file.seek(0)  # 파일 포인터를 처음으로 되돌림
                logger.info(f"파일 내용 읽기 완료: {len(file_content)} bytes")
                
                # 엑셀 파일 읽기
                if file_name.endswith('.xlsx'):
                    logger.info("openpyxl 엔진으로 엑셀 파일 읽기")
                    df = pd.read_excel(io.BytesIO(file_content), engine='openpyxl')
                else:
                    logger.info("xlrd 엔진으로 엑셀 파일 읽기")
                    df = pd.read_excel(io.BytesIO(file_content), engine='xlrd')
                
                logger.info(f"엑셀 파일 읽기 완료: {len(df)}행, {len(df.columns)}열")
                logger.info(f"데이터프레임 컬럼: {list(df.columns)}")
                logger.info(f"첫 번째 행 데이터: {df.iloc[0].tolist() if not df.empty else '빈 데이터'}")
                
            except ImportError as e:
                logger.error(f"pandas 또는 openpyxl이 설치되지 않음: {str(e)}")
                return JsonResponse({
                    'status': 'error',
                    'message': '엑셀 파일 처리를 위한 라이브러리가 설치되지 않았습니다.'
                }, status=500)
            except Exception as e:
                logger.error(f"엑셀 파일 읽기 오류: {str(e)}")
                logger.error(f"오류 타입: {type(e)}")
                import traceback
                logger.error(f"스택 트레이스: {traceback.format_exc()}")
                return JsonResponse({
                    'status': 'error',
                    'message': f'엑셀 파일을 읽을 수 없습니다: {str(e)}'
                }, status=400)
            
            # 데이터 검증 및 처리
            logger.info("데이터 검증 시작")
            if df.empty:
                logger.warning("엑셀 파일에 데이터가 없음")
                return JsonResponse({
                    'status': 'error',
                    'message': '엑셀 파일에 데이터가 없습니다.'
                }, status=400)
            
            # 컬럼 찾기
            logger.info(f"데이터프레임 컬럼: {list(df.columns)}")
            
            # 컬럼명 매핑
            phone_column = None
            card_column = None
            car_column = None
            
            # 전화번호 컬럼 찾기
            for col in df.columns:
                col_lower = str(col).lower()
                if 'phone' in col_lower or '전화' in col_lower or '폰' in col_lower:
                    phone_column = col
                    logger.info(f"전화번호 컬럼 발견: {col}")
                    break
            
            # 카드번호 컬럼 찾기
            for col in df.columns:
                col_lower = str(col).lower()
                if 'card' in col_lower or '카드' in col_lower or 'point' in col_lower:
                    card_column = col
                    logger.info(f"카드번호 컬럼 발견: {col}")
                    break
            
            # 차량번호 컬럼 찾기
            for col in df.columns:
                col_lower = str(col).lower()
                if 'car' in col_lower or '차량' in col_lower or '차' in col_lower:
                    car_column = col
                    logger.info(f"차량번호 컬럼 발견: {col}")
                    break
            
            # 필수 컬럼 확인
            if not phone_column:
                phone_column = df.columns[0] if len(df.columns) > 0 else None
                logger.info(f"전화번호 컬럼을 첫 번째 컬럼으로 설정: {phone_column}")
            
            if not card_column:
                card_column = df.columns[1] if len(df.columns) > 1 else None
                logger.info(f"카드번호 컬럼을 두 번째 컬럼으로 설정: {card_column}")
            
            if not car_column and len(df.columns) > 2:
                car_column = df.columns[2]
                logger.info(f"차량번호 컬럼을 세 번째 컬럼으로 설정: {car_column}")
            
            # 데이터 추출
            phone_numbers = df[phone_column].astype(str).str.strip() if phone_column else pd.Series()
            card_numbers = df[card_column].astype(str).str.strip() if card_column else pd.Series()
            car_numbers = df[car_column].astype(str).str.strip() if car_column else pd.Series()
            
            logger.info(f"추출된 전화번호 개수: {len(phone_numbers)}")
            logger.info(f"추출된 카드번호 개수: {len(card_numbers)}")
            logger.info(f"추출된 차량번호 개수: {len(car_numbers)}")
            
            # 데이터 검증 및 처리
            valid_customers = []
            invalid_customers = []
            
            for idx, (phone, card, car) in enumerate(zip(phone_numbers, card_numbers, car_numbers), 1):
                # 빈 값 처리
                if pd.isna(phone) or phone == '' or phone == 'nan':
                    logger.debug(f"행 {idx}: 전화번호 빈 값 건너뛰기")
                    continue
                
                if pd.isna(card) or card == '' or card == 'nan':
                    logger.debug(f"행 {idx}: 카드번호 빈 값 건너뛰기")
                    continue
                
                # 소수점 제거
                if '.' in str(phone):
                    phone = str(phone).split('.')[0]
                if '.' in str(card):
                    card = str(card).split('.')[0]
                if car and '.' in str(car):
                    car = str(car).split('.')[0]
                
                # 전화번호 검증 및 정리
                phone_clean = re.sub(r'[^0-9]', '', str(phone))
                
                # 엑셀에서 앞의 0이 제거된 경우 복원
                if len(phone_clean) == 10 and phone_clean.startswith('1'):
                    phone_clean = '0' + phone_clean
                elif len(phone_clean) == 9 and phone_clean.startswith('1'):
                    phone_clean = '0' + phone_clean
                
                if not re.match(r'^\d{10,11}$', phone_clean):
                    error_detail = f"행 {idx}: 전화번호 형식 오류 - '{phone}' (올바른 형식: 01012345678)"
                    invalid_customers.append(f"행 {idx}: 전화번호 형식 오류 ({phone} -> {phone_clean})")
                    logger.debug(f"행 {idx}: 잘못된 전화번호 {phone} -> {phone_clean}")
                    
                    # 오류 상세 정보 저장
                    if 'error_details' not in locals():
                        error_details = []
                    error_details.append(error_detail)
                    continue
                
                # 카드번호 검증 (16자리 숫자)
                card_clean = re.sub(r'[^0-9]', '', str(card))
                if not re.match(r'^\d{16}$', card_clean):
                    error_detail = f"행 {idx}: 카드번호 형식 오류 - '{card}' (올바른 형식: 16자리 숫자)"
                    invalid_customers.append(f"행 {idx}: 카드번호 형식 오류 ({card})")
                    logger.debug(f"행 {idx}: 잘못된 카드번호 {card}")
                    
                    # 오류 상세 정보 저장
                    if 'error_details' not in locals():
                        error_details = []
                    error_details.append(error_detail)
                    continue
                
                # 차량번호 정리 (선택사항)
                car_clean = None
                if car and str(car).strip() and str(car).strip() != 'nan':
                    car_clean = str(car).strip()
                
                valid_customers.append({
                    'phone': phone_clean,
                    'card': card_clean,
                    'car': car_clean,
                    'row': idx
                })
                logger.debug(f"행 {idx}: 유효한 고객 데이터 - 전화번호: {phone_clean}, 카드번호: {card_clean}, 차량번호: {car_clean}")
            
            logger.info(f"유효한 고객 데이터: {len(valid_customers)}개")
            logger.info(f"잘못된 고객 데이터: {len(invalid_customers)}개")
            
            if not valid_customers:
                logger.warning("유효한 고객 데이터가 없음")
                return JsonResponse({
                    'status': 'error',
                    'message': '유효한 고객 데이터가 없습니다. 전화번호와 카드번호를 확인해주세요.'
                }, status=400)
            
            # 고객 등록 처리
            logger.info("고객 등록 처리 시작")
            registered_count = 0
            duplicate_count = 0
            error_count = 0
            
            for customer_data in valid_customers:
                try:
                    logger.debug(f"고객 등록 시도: {customer_data}")
                    
                    phone = customer_data['phone']
                    card_number = customer_data['card']
                    car_number = customer_data['car']
                    
                    # 카드 존재 확인
                    try:
                        card = PointCard.objects.get(number=card_number)
                        logger.debug(f"카드 발견: {card_number}")
                    except PointCard.DoesNotExist:
                        error_detail = f"행 {customer_data['row']}: 카드번호 {card_number}가 등록되지 않았습니다. 먼저 카드 관리에서 카드를 등록해주세요."
                        logger.warning(f"카드가 존재하지 않음: {card_number}")
                        error_count += 1
                        
                        # 오류 상세 정보 저장
                        if 'error_details' not in locals():
                            error_details = []
                        error_details.append(error_detail)
                        continue
                    
                    # 기존 고객 확인 (전화번호 기준)
                    from Cust_User.models import CustomerProfile
                    existing_customer = CustomerProfile.objects.filter(
                        customer_phone=phone
                    ).select_related('user').first()
                    
                    if existing_customer:
                        error_detail = f"행 {customer_data['row']}: 전화번호 {phone}가 이미 회원가입한 고객입니다. (사용자: {existing_customer.user.username})"
                        logger.info(f"기존 고객 발견: {existing_customer.user.username} (전화번호: {phone})")
                        duplicate_count += 1
                        continue
                    
                    # 카드가 이미 다른 전화번호와 매핑되어 있는지 확인
                    from Cust_StationApp.models import PhoneCardMapping
                    existing_card_mapping = PhoneCardMapping.objects.filter(
                        membership_card=card,
                        station=request.user
                    ).first()
                    
                    if existing_card_mapping:
                        error_detail = f"행 {customer_data['row']}: 카드번호 {card_number}가 이미 전화번호 {existing_card_mapping.phone_number}와 매핑되어 있습니다."
                        logger.warning(f"카드가 이미 다른 전화번호와 매핑됨: {card_number} -> {existing_card_mapping.phone_number}")
                        error_count += 1
                        
                        # 오류 상세 정보 저장
                        if 'error_details' not in locals():
                            error_details = []
                        error_details.append(error_detail)
                        continue
                    
                    # 미회원 매핑 생성
                    logger.info(f"신규 고객 등록 - 미회원 매핑 생성: 전화번호 {phone}, 카드번호 {card_number}")
                    
                    # 차량 번호가 빈 문자열이면 None으로 설정
                    car_number_clean = car_number.strip() if car_number else None
                    if car_number_clean == '':
                        car_number_clean = None
                    
                    # 미회원 매핑 생성
                    from Cust_StationApp.models import PhoneCardMapping
                    mapping, created = PhoneCardMapping.objects.get_or_create(
                        phone_number=phone,
                        membership_card=card,
                        station=request.user,
                        defaults={
                            'car_number': car_number_clean,
                            'is_used': False
                        }
                    )
                    
                    if created:
                        registered_count += 1
                        logger.info(f"새 고객 등록 완료: 전화번호 {phone}")
                    else:
                        duplicate_count += 1
                        logger.info(f"기존 매핑 발견: 전화번호 {phone}")
                        
                except Exception as e:
                    error_count += 1
                    error_detail = f"행 {customer_data['row']}: {str(e)}"
                    logger.error(f"고객 {customer_data} 등록 중 오류: {str(e)}")
                    import traceback
                    logger.error(f"스택 트레이스: {traceback.format_exc()}")
                    
                    # 오류 상세 정보 저장
                    if 'error_details' not in locals():
                        error_details = []
                    error_details.append(error_detail)
            
            # 결과 메시지 생성
            message_parts = []
            if registered_count > 0:
                message_parts.append(f"새로 등록된 고객: {registered_count}명")
            if duplicate_count > 0:
                message_parts.append(f"기존 고객: {duplicate_count}명")
            if error_count > 0:
                message_parts.append(f"오류 발생: {error_count}명")
            if invalid_customers:
                message_parts.append(f"잘못된 형식: {len(invalid_customers)}개")
            
            message = ", ".join(message_parts)
            logger.info(f"업로드 결과: {message}")
            
            details = ""
            if invalid_customers:
                details = f"잘못된 데이터: {', '.join(invalid_customers[:5])}"
                if len(invalid_customers) > 5:
                    details += f" 외 {len(invalid_customers) - 5}개"
            
            # 오류 상세 정보 추가
            error_details_text = ""
            if 'error_details' in locals() and error_details:
                error_details_text = "\n\n오류 상세 정보:\n" + "\n".join(error_details[:10])  # 최대 10개까지만 표시
                if len(error_details) > 10:
                    error_details_text += f"\n... 외 {len(error_details) - 10}개 오류"
            
            logger.info("=== 엑셀 고객 업로드 요청 완료 ===")
            return JsonResponse({
                'status': 'success',
                'message': f'고객 일괄 등록 완료: {message}',
                'details': details + error_details_text,
                'registered_count': registered_count,
                'duplicate_count': duplicate_count,
                'error_count': error_count,
                'invalid_count': len(invalid_customers),
                'error_details': error_details if 'error_details' in locals() else []
            })
            
        except Exception as e:
            logger.error(f"엑셀 고객 업로드 중 오류 발생: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': f'고객 일괄 등록 중 오류가 발생했습니다: {str(e)}'
            }, status=500)
    
    logger.warning(f"잘못된 요청 방식: {request.method}")
    return JsonResponse({'status': 'error', 'message': '잘못된 요청 방식입니다.'}, status=405)