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
        
        context.update({
            'monthly_visit_count': monthly_visit_count,
            'monthly_total_amount': monthly_total_amount,
            'monthly_total_fuel': monthly_total_fuel,
            'monthly_visits': monthly_visits[:5],  # 최근 5개 기록만
            'selected_station_id': station_id or 'all',
            'selected_station': selected_station,
            'selected_station_name': selected_station_name,
            # 쿠폰 관련 컨텍스트 (임시 데이터)
            'car_wash_coupon_count': 2,  # 실제 구현 시에는 데이터베이스에서 계산
            'product_coupon_count': 1,    # 실제 구현 시에는 데이터베이스에서 계산
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
        
        try:
            customer_profile = self.request.user.customer_profile
        except ObjectDoesNotExist:
            # CustomerProfile이 없는 경우 새로 생성
            from Cust_User.models import CustomerProfile
            customer_profile = CustomerProfile.objects.create(
                user=self.request.user
            )
        
        # 연결된 주유소들의 그룹 목록 가져오기
        from Cust_StationApp.models import Group
        connected_stations = CustomerStationRelation.objects.filter(
            customer=self.request.user,
            is_active=True
        ).values_list('station_id', flat=True)
        
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
        })
        return context
        
    def post(self, request, *args, **kwargs):
        from django.core.exceptions import ObjectDoesNotExist
        from django.db import transaction
        from django.urls import reverse
        
        user = request.user
        try:
            customer_profile = user.customer_profile
        except ObjectDoesNotExist:
            from Cust_User.models import CustomerProfile
            customer_profile = CustomerProfile.objects.create(
                user=user
            )
        
        with transaction.atomic():
            # 프로필 정보 업데이트
            name = request.POST.get('name', '').strip()
            phone = request.POST.get('phone', '').strip()
            car_number = request.POST.get('car_number', '').strip()
            email = request.POST.get('email', '').strip()
            membership_card = request.POST.get('membership_card', '').strip()
            group = request.POST.get('group', '').strip()
            
            # 이름 업데이트
            if name:
                customer_profile.name = name
                user.first_name = name
            
            # 차량 번호 업데이트
            if car_number:
                customer_profile.car_number = car_number
            
            # 전화번호 업데이트 및 멤버십카드 연동
            phone_changed = False
            if phone and phone != customer_profile.customer_phone:
                customer_profile.customer_phone = phone
                phone_changed = True
                
                # 전화번호로 멤버십카드 연동 시도
                try:
                    from Cust_StationApp.models import PhoneCardMapping
                    # 폰번호로 모든 연동 정보 찾기
                    phone_mappings = PhoneCardMapping.find_all_by_phone(phone)
                    
                    linked_cards = []
                    linked_stations = []
                    
                    for phone_mapping in phone_mappings:
                        # 연동 가능한 조건:
                        # 1. is_used=False (미사용 상태)
                        # 2. is_used=True이지만 linked_user가 None (사용 중이지만 연동된 사용자가 없음)
                        can_link = (not phone_mapping.is_used) or (phone_mapping.is_used and not phone_mapping.linked_user)
                        
                        if can_link:
                            try:
                                # 연동 정보가 있고 연동 가능한 경우
                                phone_mapping.link_to_user(user)
                                
                                # 연동된 카드와 주유소 정보 수집
                                linked_cards.append(phone_mapping.membership_card.full_number)
                                linked_stations.append(phone_mapping.station)
                                
                                # 주유소와 고객 관계 생성
                                from .models import CustomerStationRelation
                                CustomerStationRelation.objects.get_or_create(
                                    customer=user,
                                    station=phone_mapping.station,
                                    defaults={'is_active': True}
                                )
                            except Exception as e:
                                # 연동 실패 시에도 계속 진행
                                pass
                    
                    # 고객 프로필에 멤버십카드 정보 업데이트 (여러 카드 지원)
                    if linked_cards:
                        # 기존 카드가 있으면 추가, 없으면 새로 설정
                        current_cards = customer_profile.membership_card or ''
                        if current_cards:
                            existing_cards = current_cards.split(',')
                            for card in linked_cards:
                                if card not in existing_cards:
                                    existing_cards.append(card)
                            customer_profile.membership_card = ','.join(existing_cards)
                        else:
                            customer_profile.membership_card = ','.join(linked_cards)
                        customer_profile.save()
                        
                        station_names = [station.station_profile.station_name for station in linked_stations if hasattr(station, 'station_profile')]
                        if station_names:
                            messages.success(request, f'전화번호 {phone}로 {len(linked_cards)}개의 멤버십카드가 연동되었습니다. (주유소: {", ".join(station_names)})')
                        else:
                            messages.success(request, f'전화번호 {phone}로 {len(linked_cards)}개의 멤버십카드가 연동되었습니다.')
                    else:
                        messages.info(request, f'전화번호 {phone}에 해당하는 미사용 멤버십카드 정보를 찾을 수 없습니다.')
                        
                except Exception as e:
                    # 연동 실패 시에도 회원가입은 계속 진행
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.warning(f"폰번호 {phone} 멤버십카드 연동 실패: {str(e)}")
                    messages.warning(request, f'멤버십카드 연동 중 오류가 발생했습니다: {str(e)}')
            
            # 이메일 업데이트
            if email:
                user.email = email
            
            # 멤버십카드 수동 업데이트 (전화번호 연동이 실패한 경우)
            if membership_card and not phone_changed:
                customer_profile.membership_card = membership_card
            
            # 그룹 업데이트
            if group:
                customer_profile.group = group
            else:
                customer_profile.group = None
            
            # 변경사항 저장
            user.save()
            customer_profile.save()
            
            messages.success(request, '프로필이 성공적으로 수정되었습니다.')
            return redirect('customer:main')  # 홈으로 리다이렉트
            
        return redirect('customer:profile')  # 실패 시 프로필 페이지로 리다이렉트

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
        
        context.update({
            'car_wash_coupon_list': car_wash_coupon_list,
            'product_coupon_list': product_coupon_list,
            'total_coupons': total_coupons,
            'car_wash_coupons': car_wash_coupons,
            'product_coupons': product_coupons,
        })
        
        return context 