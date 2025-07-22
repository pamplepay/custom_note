from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.generic import TemplateView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.contrib import messages
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from Cust_User.models import CustomerStationRelation, CustomUser, StationProfile
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import JsonResponse

from Cust_StationApp.models import CustomerCoupon

import json

@method_decorator(csrf_exempt, name='dispatch')
class CustomerMainView(LoginRequiredMixin, TemplateView):
    template_name = 'Cust_main/customer_main.html'
    login_url = 'users:login'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'CUSTOMER':
            messages.error(request, '고객 계정으로만 접근할 수 있습니다.')
            return redirect('users:login')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        
        # 연결된 주유소 정보 가져오기
        context['registered_stations'] = self.request.user.station_relations.filter(
            is_active=True
        ).select_related('station__station_profile')
        
        # 주 거래처 정보
        context['primary_station'] = context['registered_stations'].filter(
            is_primary=True
        ).first()

        # 주유소 선택 파라미터
        station_id = self.request.GET.get('station_id')
        if not station_id:
            if context['primary_station']:
                station_id = str(context['primary_station'].station.id)
            else:
                station_id = 'all'
        selected_station = None
        selected_station_name = '전체'
        if station_id != 'all':
            try:
                selected_station = None
                for relation in context['registered_stations']:
                    if str(relation.station.id) == str(station_id):
                        selected_station = relation.station
                        selected_station_name = relation.station.station_profile.station_name
                        break
            except Exception:
                selected_station = None
                selected_station_name = '전체'
        
        from .models import CustomerVisitHistory
        from datetime import datetime, date
        from django.db.models import Sum, Count
        
        current_date = datetime.now()
        current_month = current_date.month
        current_year = current_date.year
        
        # 이번달 방문 기록 조회 (주유소별 or 전체)
        visit_filter = {
            'customer': self.request.user,
            'visit_date__year': current_year,
            'visit_date__month': current_month
        }
        if selected_station:
            visit_filter['station'] = selected_station
        monthly_visits = CustomerVisitHistory.objects.filter(**visit_filter)
        
        # 통계 계산
        monthly_visit_count = monthly_visits.count()
        monthly_total_amount = monthly_visits.aggregate(
            total=Sum('sale_amount')
        )['total'] or 0
        monthly_total_fuel = monthly_visits.aggregate(
            total=Sum('fuel_quantity')
        )['total'] or 0

        

        total_coupons = CustomerCoupon.objects.filter(customer=self.request.user, status='AVAILABLE').count()
        
        context.update({
            'monthly_visit_count': monthly_visit_count,
            'monthly_total_amount': monthly_total_amount,
            'monthly_total_fuel': monthly_total_fuel,
            'monthly_visits': monthly_visits[:5],  # 최근 5개 기록만
            'selected_station_id': station_id or 'all',
            'selected_station': selected_station,
            'selected_station_name': selected_station_name,
            # 쿠폰 관련 컨텍스트 (혜택 유형별)
            'discount_coupon_count': _get_customer_coupon_count_by_benefit_include_both(self.request.user, 'DISCOUNT'),
            'product_coupon_count': _get_customer_coupon_count_by_benefit_include_both(self.request.user, 'PRODUCT'),
            'total_coupons': total_coupons,            
        })
        
        return context

@method_decorator(csrf_exempt, name='dispatch')
class CustomerRecordsView(LoginRequiredMixin, TemplateView):
    template_name = 'Cust_main/records.html'
    login_url = 'users:login'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'CUSTOMER':
            messages.error(request, '고객 계정으로만 접근할 수 있습니다.')
            return redirect('users:login')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from .models import CustomerVisitHistory
        from datetime import datetime
        from django.db.models import F

        # year, month GET 파라미터 처리
        now = datetime.now()
        year = self.request.GET.get('year')
        month = self.request.GET.get('month')
        try:
            year = int(year)
        except (TypeError, ValueError):
            year = now.year
        try:
            month = int(month)
        except (TypeError, ValueError):
            month = now.month

        # 해당 월의 방문 기록만 필터링
        visit_records = CustomerVisitHistory.objects.filter(
            customer=self.request.user,
            visit_date__year=year,
            visit_date__month=month
        ).select_related('station').order_by('-visit_date', '-visit_time')

        # 해당 월의 총 주유금액
        from django.db.models import Sum
        monthly_total_amount = visit_records.aggregate(total=Sum('sale_amount'))['total'] or 0

        # 사용자가 기록한 월 목록(최신순)
        month_list = CustomerVisitHistory.objects.filter(
            customer=self.request.user
        ).annotate(
            year_val=F('visit_date__year'),
            month_val=F('visit_date__month')
        ).values_list('year_val', 'month_val').distinct().order_by('-year_val', '-month_val')

        context['visit_records'] = visit_records
        context['year'] = year
        context['month'] = month
        context['month_list'] = month_list
        context['monthly_total_amount'] = monthly_total_amount
        return context



@method_decorator(csrf_exempt, name='dispatch')
class CustomerProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'Cust_main/profile.html'
    login_url = 'users:login'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'CUSTOMER':
            messages.error(request, '고객 계정으로만 접근할 수 있습니다.')
            return redirect('users:login')
        return super().dispatch(request, *args, **kwargs)
        
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from django.core.exceptions import ObjectDoesNotExist
        from Cust_User.models import CustomerStationRelation
        try:
            customer_profile = self.request.user.customer_profile
        except ObjectDoesNotExist:
            from Cust_User.models import CustomerProfile
            customer_profile = CustomerProfile.objects.create(
                user=self.request.user
            )
        # 연결된 주유소 목록 및 주거래 주유소
        registered_stations = CustomerStationRelation.objects.filter(customer=self.request.user, is_active=True).select_related('station__station_profile')
        primary_station = registered_stations.filter(is_primary=True).first()
        # 그룹 목록
        from Cust_StationApp.models import Group
        connected_stations = registered_stations.values_list('station_id', flat=True)
        groups = Group.objects.filter(station_id__in=connected_stations).order_by('name')
        context.update({
            'username': self.request.user.username,
            'name': customer_profile.name or self.request.user.first_name or '',
            'phone': customer_profile.customer_phone or '',
            'car_number': customer_profile.car_number or '',
            'email': self.request.user.email or '',
            'membership_card': customer_profile.membership_card or '',
            'current_group': customer_profile.group or '',
            'available_groups': groups,
            'registered_stations': registered_stations,
            'primary_station': primary_station,
        })
        return context
        
    def post(self, request, *args, **kwargs):
        from django.core.exceptions import ObjectDoesNotExist
        from django.db import transaction
        from django.urls import reverse
        from Cust_User.models import CustomerStationRelation
        user = request.user
        try:
            customer_profile = user.customer_profile
        except ObjectDoesNotExist:
            from Cust_User.models import CustomerProfile
            customer_profile = CustomerProfile.objects.create(
                user=user
            )
        with transaction.atomic():
            # 기존 정보 업데이트 ...
            name = request.POST.get('name', '').strip()
            phone = request.POST.get('phone', '').strip()
            car_number = request.POST.get('car_number', '').strip()
            email = request.POST.get('email', '').strip()
            membership_card = request.POST.get('membership_card', '').strip()
            group = request.POST.get('group', '').strip()
            primary_station_id = request.POST.get('primary_station_id')
            # ... 기존 필드 업데이트 ...
            if name:
                customer_profile.name = name
                user.first_name = name
            if car_number:
                customer_profile.car_number = car_number
            phone_changed = False
            if phone and phone != customer_profile.customer_phone:
                customer_profile.customer_phone = phone
                phone_changed = True
                # ... (생략) ...
            if email:
                user.email = email
            if membership_card and not phone_changed:
                customer_profile.membership_card = membership_card
            if group:
                customer_profile.group = group
            else:
                customer_profile.group = None
            # 주거래 주유소 설정
            if primary_station_id:
                relations = CustomerStationRelation.objects.filter(customer=user, is_active=True)
                for rel in relations:
                    rel.is_primary = (str(rel.station.id) == str(primary_station_id))
                    rel.save()
            user.save()
            customer_profile.save()
            messages.success(request, '프로필이 성공적으로 수정되었습니다.')
            return redirect('customer:main')
        return redirect('customer:profile')

@method_decorator(csrf_exempt, name='dispatch')
class StationListView(LoginRequiredMixin, ListView):
    template_name = 'Cust_main/station_list.html'
    context_object_name = 'stations'
    login_url = 'users:login'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'CUSTOMER':
            messages.error(request, '고객 계정으로만 접근할 수 있습니다.')
            return redirect('users:login')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        # 승인된 주유소만 표시
        queryset = CustomUser.objects.filter(
            user_type='STATION',
            station_profile__is_approved=True
        ).select_related('station_profile')
        
        # 검색어가 있는 경우 필터링
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(station_profile__station_name__icontains=search_query) |
                Q(station_profile__station_address__icontains=search_query)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 이미 등록된 주유소 ID 목록
        context['registered_station_ids'] = list(
            CustomerStationRelation.objects.filter(
                customer=self.request.user
            ).values_list('station_id', flat=True)
        )
        
        # 각 주유소의 서비스 목록을 미리 처리
        stations_with_services = []
        for station in context['stations']:
            services = []
            if station.station_profile.services:
                services = [service.strip() for service in station.station_profile.services.split(',')]
            stations_with_services.append({
                'station': station,
                'services': services
            })
        context['stations_with_services'] = stations_with_services
        
        return context

@csrf_exempt
@login_required
def register_station(request, station_id):
    if request.method != 'POST':
        return redirect('customer:station_list')
        
    if request.user.user_type != 'CUSTOMER':
        messages.error(request, '고객 계정으로만 접근할 수 있습니다.')
        return redirect('users:login')
    
    station = get_object_or_404(CustomUser, id=station_id, user_type='STATION')
    
    # 이미 등록된 주유소인지 확인
    if CustomerStationRelation.objects.filter(customer=request.user, station=station).exists():
        messages.warning(request, '이미 등록된 주유소입니다.')
        return redirect('customer:station_list')
    
    # 주유소 등록
    CustomerStationRelation.objects.create(
        customer=request.user,
        station=station
    )
    
    messages.success(request, '주유소가 등록되었습니다.')
    return redirect('customer:station_list') 

@csrf_exempt
@login_required
def get_customer_groups(request):
    """고객이 속한 주유소들의 그룹 목록 조회 (AJAX)"""
    if request.user.user_type != 'CUSTOMER':
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        # 연결된 주유소들의 그룹 목록 가져오기
        from Cust_StationApp.models import Group
        connected_stations = CustomerStationRelation.objects.filter(
            customer=request.user,
            is_active=True
        ).values_list('station_id', flat=True)
        
        groups = Group.objects.filter(station_id__in=connected_stations).order_by('name')
        
        groups_list = []
        for group in groups:
            groups_list.append({
                'id': group.id,
                'name': group.name,
                'station_name': group.station.station_profile.station_name if hasattr(group.station, 'station_profile') else group.station.username
            })
        
        return JsonResponse({
            'status': 'success',
            'groups': groups_list
        })
        
    except Exception as e:
        return JsonResponse({
            'status': 'error',
            'message': '그룹 목록을 불러오는 중 오류가 발생했습니다.'
        }, status=500)

@method_decorator(csrf_exempt, name='dispatch')
class CustomerCouponsView(LoginRequiredMixin, TemplateView):
    template_name = 'Cust_main/coupons.html'
    login_url = 'users:login'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'CUSTOMER':
            messages.error(request, '고객 계정으로만 접근할 수 있습니다.')
            return redirect('users:login')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # 임시 쿠폰 데이터 (실제 구현 시에는 데이터베이스에서 가져와야 함)
        # 세차 쿠폰 예시 데이터
        car_wash_coupon_list = [
            {
                'title': '세차 서비스 50% 할인',
                'description': '주유소 세차장에서 사용 가능한 할인 쿠폰입니다.',
                'discount_type': 'PERCENT',
                'discount_value': 50,
                'min_amount': 10000,
                'expiry_date': '2024-12-31',
                'is_expired': False,
                'is_used': False,
            },
            {
                'title': '세차 서비스 2000원 할인',
                'description': '주유소 세차장에서 사용 가능한 할인 쿠폰입니다.',
                'discount_type': 'AMOUNT',
                'discount_value': 2000,
                'min_amount': 5000,
                'expiry_date': '2024-11-30',
                'is_expired': False,
                'is_used': True,
            },
        ]
        
        # 상품 쿠폰 예시 데이터
        product_coupon_list = [
            {
                'title': '편의점 상품 30% 할인',
                'description': '주유소 편의점에서 사용 가능한 할인 쿠폰입니다.',
                'discount_type': 'PERCENT',
                'discount_value': 30,
                'min_amount': 5000,
                'expiry_date': '2024-12-31',
                'is_expired': False,
                'is_used': False,
            },
            {
                'title': '편의점 상품 1000원 할인',
                'description': '주유소 편의점에서 사용 가능한 할인 쿠폰입니다.',
                'discount_type': 'AMOUNT',
                'discount_value': 1000,
                'min_amount': 3000,
                'expiry_date': '2024-10-31',
                'is_expired': True,
                'is_used': False,
            },
        ]
        
        # 통계 계산
        total_coupons = len(car_wash_coupon_list) + len(product_coupon_list)
        car_wash_coupons = len([c for c in car_wash_coupon_list if not c['is_expired'] and not c['is_used']])
        product_coupons = len([c for c in product_coupon_list if not c['is_expired'] and not c['is_used']])
        
        # 실제 쿠폰 데이터로 교체
        from Cust_StationApp.models import CustomerCoupon
        
        # 고객의 실제 쿠폰 조회 (사용 완료된 쿠폰 제외)
        customer_coupons = CustomerCoupon.objects.filter(
            customer=self.request.user,
            status__in=['AVAILABLE', 'EXPIRED']  # 사용 가능하거나 만료된 쿠폰만 표시
        ).select_related('coupon_template', 'coupon_template__coupon_type').order_by('-issued_date')
        
        # 혜택 유형별 분류
        discount_coupon_list = []  # 세차 할인
        product_coupon_list = []   # 무료 상품
        combo_coupon_list = []     # 할인+상품
        
        for coupon in customer_coupons:
            template = coupon.coupon_template
            
            # 템플릿 기준으로 만료 여부 확인
            is_template_expired = False
            if not template.is_permanent and template.valid_until:
                from django.utils import timezone
                today = timezone.now().date()
                is_template_expired = today > template.valid_until
            
            coupon_data = {
                'id': coupon.id,
                'title': template.coupon_name,
                'description': template.description or f"{template.coupon_type.type_name} 쿠폰입니다. 할인 혜택은 세차장에서 사용 가능합니다." if template.benefit_type in ['DISCOUNT', 'BOTH'] else template.description or f"{template.coupon_type.type_name} 쿠폰입니다.",
                'benefit_description': template.get_benefit_description(),
                'discount_type': 'AMOUNT',  # 정액 할인만 사용
                'discount_value': template.discount_amount,
                'product_name': template.product_name,
                'benefit_type': template.benefit_type,
                'coupon_type_name': template.coupon_type.type_name,  # 발행처 표시용
                'expiry_date': template.valid_until if template.valid_until and not template.is_permanent else None,
                'is_expired': is_template_expired or coupon.status == 'EXPIRED',
                'is_used': coupon.status == 'USED',
                'is_available': coupon.status == 'AVAILABLE' and not is_template_expired,
                'issued_date': coupon.issued_date.strftime('%Y-%m-%d'),
                'used_date': coupon.used_date.strftime('%Y-%m-%d') if coupon.used_date else None,
                'station_name': template.station.station_profile.station_name if hasattr(template.station, 'station_profile') else template.station.username,
                'is_permanent': template.is_permanent,
            }
            
            # 혜택 유형별 분류 (BOTH는 두 섹션 모두에 표시)
            benefit_type = template.benefit_type
            if benefit_type == 'DISCOUNT':
                discount_coupon_list.append(coupon_data)
            elif benefit_type == 'PRODUCT':
                product_coupon_list.append(coupon_data)
            elif benefit_type == 'BOTH':
                # 할인+상품은 두 섹션 모두에 표시
                discount_coupon_list.append(coupon_data)
                product_coupon_list.append(coupon_data)
        
        # 통계 계산 (사용 가능한 쿠폰만 계산)
        available_coupons = customer_coupons.filter(status='AVAILABLE')
        total_coupons = available_coupons.count()
        discount_coupons = available_coupons.filter(
            coupon_template__benefit_type__in=['DISCOUNT', 'BOTH']
        ).count()
        product_coupons = available_coupons.filter(
            coupon_template__benefit_type__in=['PRODUCT', 'BOTH']
        ).count()
        
        context.update({
            'discount_coupon_list': discount_coupon_list,  # 세차 할인 (BOTH 포함)
            'product_coupon_list': product_coupon_list,    # 무료 상품 (BOTH 포함)
            'total_coupons': total_coupons,
            'discount_coupons': discount_coupons,  # 할인 혜택이 있는 쿠폰 수
            'product_coupons': product_coupons,    # 상품 혜택이 있는 쿠폰 수
        })
        
        return context


def _get_customer_coupon_count(user, coupon_type_code):
    """고객의 특정 유형 쿠폰 개수 조회 (사용 가능한 것만)"""
    from Cust_StationApp.models import CustomerCoupon
    
    return CustomerCoupon.objects.filter(
        customer=user,
        status='AVAILABLE',
        coupon_template__coupon_type__type_code=coupon_type_code
    ).count()

def _get_customer_coupon_count_by_benefit(user, benefit_type):
    """고객의 특정 혜택 유형 쿠폰 개수 조회 (사용 가능한 것만)"""
    from Cust_StationApp.models import CustomerCoupon
    
    return CustomerCoupon.objects.filter(
        customer=user,
        status='AVAILABLE',
        coupon_template__benefit_type=benefit_type
    ).count()

def _get_customer_coupon_count_by_benefit_include_both(user, benefit_type):
    """고객의 특정 혜택 유형 쿠폰 개수 조회 (BOTH 타입 포함, 사용 가능한 것만)"""
    from Cust_StationApp.models import CustomerCoupon
    
    if benefit_type == 'DISCOUNT':
        benefit_types = ['DISCOUNT', 'BOTH']
    elif benefit_type == 'PRODUCT':
        benefit_types = ['PRODUCT', 'BOTH']
    else:
        benefit_types = [benefit_type]
    
    return CustomerCoupon.objects.filter(
        customer=user,
        status='AVAILABLE',
        coupon_template__benefit_type__in=benefit_types
    ).count()

@csrf_exempt
@login_required
def use_coupon(request, coupon_id):
    """쿠폰 사용 처리"""
    if request.user.user_type != 'CUSTOMER':
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': '잘못된 요청입니다.'}, status=405)
    
    try:
        from Cust_StationApp.models import CustomerCoupon
        
        # 쿠폰 조회
        coupon = CustomerCoupon.objects.get(
            id=coupon_id,
            customer=request.user
        )
        
        # 쿠폰 사용 가능 여부 확인
        if not coupon.is_available():
            return JsonResponse({'status': 'error', 'message': '사용할 수 없는 쿠폰입니다.'})
        
        # 쿠폰 사용 처리
        coupon.use_coupon()
        
        return JsonResponse({
            'status': 'success',
            'message': '쿠폰이 성공적으로 사용되었습니다.',
            'coupon_name': coupon.coupon_template.coupon_name
        })
        
    except CustomerCoupon.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': '존재하지 않는 쿠폰입니다.'})
    except ValueError as e:
        return JsonResponse({'status': 'error', 'message': str(e)})
    except Exception as e:
        return JsonResponse({'status': 'error', 'message': '쿠폰 사용 중 오류가 발생했습니다.'}) 

@csrf_exempt
@login_required
def check_location_coupons(request):
    """현재 위치에서 쿠폰 발행 가능한 주유소 확인"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'POST 요청만 허용됩니다.'})
    
    try:
        data = json.loads(request.body)
        latitude = float(data.get('latitude'))
        longitude = float(data.get('longitude'))
        accuracy = float(data.get('accuracy', 0))
        
        # 위치 정보 유효성 검사
        if not (-90 <= latitude <= 90) or not (-180 <= longitude <= 180):
            return JsonResponse({
                'success': False, 
                'message': '유효하지 않은 위치 정보입니다.'
            })
        
        # 쿠폰을 발행할 수 있는 주유소 찾기 (위치 정보가 있는 주유소)
        from Cust_User.models import StationProfile
        from Cust_StationApp.models import Coupon
        from math import radians, cos, sin, asin, sqrt
        
        # 모든 주유소 프로필 가져오기 (위치 정보가 있는 것만)
        station_profiles = StationProfile.objects.filter(
            latitude__isnull=False,
            longitude__isnull=False
        ).select_related('user')
        
        nearby_stations = []
        max_distance = 1000  # 1km 이내
        
        for profile in station_profiles:
            # 두 지점 간의 거리 계산 (Haversine 공식)
            distance = calculate_distance(
                latitude, longitude,
                float(profile.latitude), float(profile.longitude)
            )
            
            # 지정된 거리 이내인 경우만 추가
            if distance <= max_distance:
                # 해당 주유소의 사용 가능한 쿠폰 정보 조회
                coupon_counts = Coupon.get_coupon_counts_by_type(profile.user)
                
                nearby_stations.append({
                    'station_id': profile.user.id,
                    'station_name': profile.station_name,
                    'address': profile.address,
                    'tid': profile.tid,
                    'distance': round(distance),
                    'latitude': float(profile.latitude),
                    'longitude': float(profile.longitude),
                    'coupon_counts': coupon_counts,
                    'has_coupons': coupon_counts['total'] > 0
                })
        
        # 거리순으로 정렬
        nearby_stations.sort(key=lambda x: x['distance'])
        
        return JsonResponse({
            'success': True,
            'nearby_stations': nearby_stations,
            'accuracy': accuracy,
            'total_count': len(nearby_stations)
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False, 
            'message': '잘못된 JSON 형식입니다.'
        })
    except (ValueError, TypeError) as e:
        return JsonResponse({
            'success': False, 
            'message': f'잘못된 데이터 형식입니다: {str(e)}'
        })
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'message': f'서버 오류가 발생했습니다: {str(e)}'
        })

def calculate_distance(lat1, lon1, lat2, lon2):
    """두 지점 간의 거리 계산 (Haversine 공식) - 미터 단위"""
    # 지구 반지름 (미터)
    R = 6371000
    
    # 라디안으로 변환
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    # 좌표 차이
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    # Haversine 공식
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    
    # 거리 계산 (미터)
    distance = R * c
    
    return distance 