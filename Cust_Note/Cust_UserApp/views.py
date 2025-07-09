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

@method_decorator(csrf_exempt, name='dispatch')
class CustomerStatsView(LoginRequiredMixin, TemplateView):
    template_name = 'Cust_main/stats.html'
    login_url = 'users:login'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'CUSTOMER':
            messages.error(request, '고객 계정으로만 접근할 수 있습니다.')
            return redirect('users:login')
        return super().dispatch(request, *args, **kwargs)

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
        
        context.update({
            'name': customer_profile.name or self.request.user.first_name or '',
            'phone': customer_profile.customer_phone or '',
            'email': self.request.user.email or '',
            'membership_card': customer_profile.membership_card or '',
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
            email = request.POST.get('email', '').strip()
            membership_card = request.POST.get('membership_card', '').strip()
            
            # 이름 업데이트
            if name:
                customer_profile.name = name
                user.first_name = name
            
            # 전화번호 업데이트
            if phone:
                customer_profile.customer_phone = phone
            
            # 이메일 업데이트
            if email:
                user.email = email
            
            # 멤버십카드 업데이트
            if membership_card:
                customer_profile.membership_card = membership_card
            
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