from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, FileResponse
from django.contrib import messages
from django.db.models import Q, Sum
from Cust_User.models import CustomUser, CustomerProfile, CustomerStationRelation
from .models import PointCard, StationCardMapping, SalesData, ExcelSalesData, MonthlySalesStatistics, SalesStatistics
from datetime import datetime, timedelta
import json
import logging
import re
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.db.transaction import TransactionManagementError
from django.views.decorators.http import require_http_methods
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
    total_cards = StationCardMapping.objects.filter(is_active=True).count()
    active_cards = StationCardMapping.objects.filter(is_active=True, card__is_used=False).count()
    inactive_cards = StationCardMapping.objects.filter(is_active=True, card__is_used=True).count()
    
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
            
            monthly_stats = {
                'current_month': current_monthly,
                'previous_month': previous_monthly,
                'current_month_str': current_month,
                'previous_month_str': previous_month,
                'previous_top_products': previous_top_products,
                'current_top_products': current_top_products,
                'previous_top_products_by_amount': previous_top_products_by_amount,
                'current_top_products_by_amount': current_top_products_by_amount
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
        from .models import SalesStatistics, MonthlySalesStatistics
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
        
        # 해당 월의 날짜별 데이터 조회
        daily_stats = SalesStatistics.objects.filter(
            tid=tid,
            sale_date__startswith=month_str
        ).order_by('sale_date')
        
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
        from .models import ExcelSalesData
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
        return JsonResponse({'error': f'데이터 조회 중 오류가 발생했습니다: {str(e)}'}, status=500)

@login_required
def station_management(request):
    """주유소 관리 페이지"""
    if not request.user.is_station:
        messages.error(request, '주유소 회원만 접근할 수 있습니다.')
        return redirect('home')
    
    # 현재 주유소의 카드 매핑 수 조회
    mappings = StationCardMapping.objects.filter(is_active=True)
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
    """주유소 프로필 페이지"""
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
    
    if request.method == 'POST':
        # POST 요청 처리
        station_profile.station_name = request.POST.get('station_name')
        station_profile.phone = request.POST.get('phone')
        station_profile.address = request.POST.get('address')
        station_profile.business_number = request.POST.get('business_number')
        station_profile.oil_company_code = request.POST.get('oil_company_code')
        station_profile.agency_code = request.POST.get('agency_code')
        station_profile.tid = request.POST.get('tid')
        
        try:
            station_profile.save()
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
    mappings = StationCardMapping.objects.filter(is_active=True)
    total_cards = mappings.count()
    
    # 카드 상태별 통계
    active_cards = mappings.filter(card__is_used=False).count()
    used_cards = mappings.filter(card__is_used=True).count()
    
    # 비율 계산
    active_percentage = (active_cards / total_cards * 100) if total_cards > 0 else 0
    used_percentage = (used_cards / total_cards * 100) if total_cards > 0 else 0
    
    # 최근 등록된 카드 3장 가져오기
    recent_cards = StationCardMapping.objects.select_related('card').filter(
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
    
    # 고객 목록 조회
    customer_relations = CustomerStationRelation.objects.filter(
        station=request.user
    ).select_related(
        'customer',
        'customer__customer_profile'
    ).order_by('-created_at')
    
    # 검색 필터링
    if search_query:
        customer_relations = customer_relations.filter(
            Q(customer__username__icontains=search_query) |
            Q(customer__customer_profile__customer_phone__icontains=search_query) |
            Q(customer__customer_profile__membership_card__icontains=search_query)
        )
    
    # 페이지네이터 설정
    paginator = Paginator(customer_relations, 10)  # 페이지당 10개
    
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
    
    # 고객 데이터 가공
    customers = []
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
        
        customers.append({
            'id': customer.id,
            'phone': profile.customer_phone,
            'card_number': profile.membership_card,
            'last_visit': last_visit,
            'total_visit_count': total_visit_count,
            'total_fuel_amount': total_fuel_amount,
            'created_at': relation.created_at
        })
    
    context = {
        'customers': customers,
        'current_page': int(page),
        'total_pages': paginator.num_pages,
        'page_range': page_range,
        'search_query': search_query,
        'station_tid': request.user.station_profile.tid if hasattr(request.user, 'station_profile') else None,
        'this_month_visitors': this_month_visitors
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
            card_id = data.get('card_id')
            
            if not card_id:
                return JsonResponse({
                    'status': 'error',
                    'message': '멤버십 카드 ID는 필수입니다.'
                }, status=400)
            
            # 카드 매핑 삭제
            mapping = get_object_or_404(
                StationCardMapping,
                point_card_id=card_id,
                station=request.user
            )
            mapping.delete()
            
            return JsonResponse({
                'status': 'success',
                'message': '멤버십 카드가 성공적으로 삭제되었습니다.'
            })
            
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
    
    context = {
        'station_name': request.user.username,
        'total_coupons': 0,
        'used_coupons': 0,
        'unused_coupons': 0
    }
    
    return render(request, 'Cust_Station/station_couponmanage.html', context)

@require_http_methods(["GET"])
@login_required
def get_unused_cards(request):
    """미사용 카드 목록 조회"""
    logger.info("=== 미사용 카드 목록 조회 시작 ===")
    logger.info(f"요청 사용자: {request.user.username}")
    
    try:
        # 미사용 카드 조회
        unused_cards = PointCard.objects.filter(is_used=False).order_by('-created_at')
        logger.debug(f"미사용 카드 수: {unused_cards.count()}")
        
        # 카드 정보 변환
        cards_data = [{
            'number': card.number,
            'tids': card.tids,
            'created_at': card.created_at.strftime('%Y-%m-%d %H:%M')
        } for card in unused_cards]
        
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
        card_number = data.get('card_number', '').strip()
        tid = data.get('tid', '').strip()  # TID 값 추가
        logger.debug(f"입력된 카드번호: {card_number}, TID: {tid}")
        
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
        
        # 카드번호 중복 체크
        if PointCard.objects.filter(number=card_number).exists():
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
    """신규 고객 등록"""
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
            
            logger.info(f"입력값 확인 - 전화번호: {phone}, 카드번호: {card_number}")
            
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
                    # 카드 확인 (락 설정)
                    try:
                        card_mapping = StationCardMapping.objects.select_for_update().select_related('card').get(
                            card__number=card_number,
                            is_active=True
                        )
                        card = card_mapping.card
                    except StationCardMapping.DoesNotExist:
                        logger.warning(f"미등록 카드 - 카드번호: {card_number}")
                        return JsonResponse({
                            'status': 'error',
                            'message': '등록되지 않은 카드번호입니다.'
                        }, status=400)
                    
                    if card.is_used:
                        logger.warning(f"이미 사용 중인 카드 사용 시도: {card_number}")
                        return JsonResponse({
                            'status': 'error',
                            'message': '이미 사용 중인 카드입니다.'
                        }, status=400)

                    # 기존 사용자 확인 (락 설정)
                    existing_user = CustomUser.objects.select_for_update().filter(username=phone).first()
                    
                    if existing_user:
                        logger.info(f"기존 고객 발견: {phone} - 멤버십 카드만 연결")
                        
                        # 이미 이 주유소에 등록된 고객인지 확인
                        customer_relation = CustomerStationRelation.objects.filter(
                            customer=existing_user, 
                            station=request.user
                        ).first()

                        if not customer_relation:
                            # 주유소와 고객 관계 생성
                            CustomerStationRelation.objects.create(
                                customer=existing_user,
                                station=request.user
                            )
                            logger.info(f"주유소-고객 관계 생성 완료 - 고객: {existing_user.id}, 주유소: {request.user.username}")

                        # 고객 프로필 업데이트 - 멤버십 카드 추가
                        customer_profile = CustomerProfile.objects.get(user=existing_user)
                        if customer_profile.membership_card:
                            # 기존 카드 번호가 있으면 새 카드 번호를 추가 (쉼표로 구분)
                            existing_cards = set(customer_profile.membership_card.split(','))
                            existing_cards.add(card_number)
                            customer_profile.membership_card = ','.join(existing_cards)
                        else:
                            customer_profile.membership_card = card_number
                        customer_profile.save()
                        logger.info(f"고객 프로필 업데이트 완료 - 사용자: {existing_user.id}")
                        
                    else:
                        logger.info(f"신규 고객 등록 시작: {phone}")
                        # 신규 사용자 생성
                        new_user = CustomUser.objects.create_user(
                            username=phone,
                            password=card_number,
                            user_type='CUSTOMER',
                            pw_back=card_number  # 실제 카드번호를 백업 패스워드로 저장
                        )
                        logger.info(f"신규 사용자 생성 완료 - ID: {new_user.id}, 전화번호: {phone}")
                        
                        # 고객 프로필 생성
                        customer_profile, created = CustomerProfile.objects.get_or_create(
                            user=new_user,
                            defaults={
                                'customer_phone': phone,
                                'membership_card': card_number
                            }
                        )
                        if not created:
                            customer_profile.customer_phone = phone
                            customer_profile.membership_card = card_number
                            customer_profile.save()
                        logger.info(f"고객 프로필 생성 완료 - 사용자: {new_user.id}")
                        
                        # 주유소와 고객 관계 생성
                        CustomerStationRelation.objects.create(
                            customer=new_user,
                            station=request.user
                        )
                        logger.info(f"주유소-고객 관계 생성 완료 - 고객: {new_user.id}, 주유소: {request.user.username}")
                    
                    # 카드 상태 업데이트
                    card.is_used = True
                    card.save()
                    logger.info(f"카드 상태 업데이트 완료 - 카드번호: {card_number}")
                    
                    logger.info("=== 고객 등록 프로세스 완료 ===")
                    return JsonResponse({
                        'status': 'success',
                        'message': '고객이 성공적으로 등록되었습니다.'
                    })
                    
            except IntegrityError as e:
                logger.error(f"데이터베이스 무결성 오류: {str(e)}", exc_info=True)
                return JsonResponse({
                    'status': 'error',
                    'message': '고객 등록 중 무결성 오류가 발생했습니다. 이미 등록된 정보일 수 있습니다.'
                }, status=400)
            except Exception as e:
                logger.error(f"데이터베이스 처리 중 오류: {str(e)}", exc_info=True)
                return JsonResponse({
                    'status': 'error',
                    'message': '고객 등록 중 오류가 발생했습니다.'
                }, status=500)
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 오류: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': '잘못된 요청 형식입니다.'
            }, status=400)
        except Exception as e:
            logger.error(f"예상치 못한 오류: {str(e)}", exc_info=True)
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
        # 사용자 검색
        user = CustomUser.objects.filter(username=phone).first()
        
        if not user:
            return JsonResponse({
                'status': 'success',
                'exists': False,
                'message': '사용 가능한 전화번호입니다.',
                'data': {
                    'can_register': True
                }
            })

        # 프로필 정보 가져오기
        profile = CustomerProfile.objects.filter(user=user).first()
        
        # 현재 주유소와의 관계 확인
        relation = CustomerStationRelation.objects.filter(
            customer=user,
            station=request.user
        ).exists()

        if relation:
            message = '이미 이 주유소에 등록된 고객입니다.'
            can_register = False
        else:
            message = '다른 주유소에 등록된 전화번호입니다. 새로운 카드로 등록 가능합니다.'
            can_register = True

        return JsonResponse({
            'status': 'success',
            'exists': True,
            'message': message,
            'data': {
                'phone': profile.customer_phone if profile else None,
                'membership_card': profile.membership_card if profile else None,
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
                                
                                # 고객 프로필의 주유량 정보 업데이트
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
                                
                                customer_profile.save()
                                
                                # 업데이트된 주유량 정보 로그
                                logger.info(f"업데이트된 주유량 정보 - 총: {customer_profile.total_fuel_amount:.2f}L, 월: {customer_profile.monthly_fuel_amount:.2f}L, 최근: {customer_profile.last_fuel_amount:.2f}L")
                                logger.info(f"방문 내역 및 주유량 저장 완료: {customer.username} - {sale_date} {sale_time} (주유량: {fuel_quantity:.2f}L)")
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
