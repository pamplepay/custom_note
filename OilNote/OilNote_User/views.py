from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.views import LoginView, PasswordChangeView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.views.generic import CreateView
from django.urls import reverse_lazy
from django.contrib import messages
from django.http import JsonResponse, HttpResponseRedirect
from .forms import CustomerSignUpForm, StationSignUpForm, CustomLoginForm, CustomPasswordChangeForm
from .models import CustomUser
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404
from django.db import IntegrityError

def check_auth(request):
    """인증 상태를 확인하는 API 엔드포인트"""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'authenticated': request.user.is_authenticated,
            'user_type': request.user.user_type if request.user.is_authenticated else None
        })
    return JsonResponse({'error': '잘못된 요청입니다.'}, status=400)

def test_sw(request):
    """Service Worker 테스트 페이지"""
    return render(request, 'test_sw.html')

# Create your views here.

class CustomerSignUpView(CreateView):
    model = CustomUser
    form_class = CustomerSignUpForm
    template_name = 'OilNote_User/signup.html'
    success_url = reverse_lazy('users:login')

    def dispatch(self, request, *args, **kwargs):
        # 이미 로그인된 사용자는 메인 페이지로 리다이렉트
        if request.user.is_authenticated:
            if request.user.user_type == 'CUSTOMER':
                return redirect('customer:main')
            else:
                return redirect('station:main')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        import logging
        logger = logging.getLogger(__name__)
        
        logger.info(f"CustomerSignUpView form_valid 시작")
        logger.info(f"요청 데이터: username={form.cleaned_data.get('username', 'N/A')}")
        logger.info(f"전화번호: {form.cleaned_data.get('customer_phone', 'N/A')}")
        logger.info(f"폼 유효성: {form.is_valid()}")
        logger.info(f"폼 오류: {form.errors}")
        
        try:
            # 폼에서 이미 user를 생성하고 저장했으므로, 여기서는 user 객체만 가져옴
            user = form.instance
            logger.info(f"form.instance: {user}, pk: {getattr(user, 'pk', 'N/A')}")
            
            if not user.pk:  # 아직 저장되지 않은 경우에만 저장
                logger.info("user.pk가 없으므로 form.save() 호출")
                user = form.save()
                logger.info(f"form.save() 완료: user.pk = {user.pk}")
            else:
                logger.info(f"user.pk가 이미 존재함: {user.pk}")
                
            login(self.request, user)
            logger.info(f"로그인 완료: {user.username}")
            
            # 멤버십카드 연동 여부 확인
            phone = form.cleaned_data.get('customer_phone', '')
            if phone:
                try:
                    from OilNote_StationApp.models import PhoneCardMapping
                    from .models import CustomerProfile
                    
                    # 연동된 카드 정보 확인
                    phone_mappings = PhoneCardMapping.find_all_by_phone(phone)
                    linked_cards = []
                    linked_stations = []
                    
                    for phone_mapping in phone_mappings:
                        if phone_mapping.linked_user == user:
                            linked_cards.append(phone_mapping.membership_card.full_number)
                            linked_stations.append(phone_mapping.station)
                    
                    if linked_cards:
                        station_names = [station.station_profile.station_name for station in linked_stations if hasattr(station, 'station_profile')]
                        if station_names:
                            messages.success(self.request, f'회원가입이 완료되었습니다. 전화번호 {phone}로 {len(linked_cards)}개의 멤버십카드가 연동되었습니다. (주유소: {", ".join(station_names)})')
                        else:
                            messages.success(self.request, f'회원가입이 완료되었습니다. 전화번호 {phone}로 {len(linked_cards)}개의 멤버십카드가 연동되었습니다.')
                    else:
                        messages.success(self.request, f'회원가입이 완료되었습니다. 전화번호 {phone}에 해당하는 미사용 멤버십카드 정보를 찾을 수 없습니다.')
                except Exception as e:
                    messages.success(self.request, '회원가입이 완료되었습니다.')
                    messages.warning(self.request, f'멤버십카드 연동 중 오류가 발생했습니다: {str(e)}')
            else:
                messages.success(self.request, '회원가입이 완료되었습니다.')
            
            return redirect('customer:main')
            
        except IntegrityError as e:
            # 중복된 username 오류 처리
            logger.error(f"CustomerSignUpView IntegrityError 발생: {str(e)}")
            logger.error(f"요청 데이터: username={form.cleaned_data.get('username', 'N/A')}")
            logger.error(f"전화번호: {form.cleaned_data.get('customer_phone', 'N/A')}")
            logger.error(f"폼 오류: {form.errors}")
            
            if "Duplicate entry" in str(e) and "username" in str(e):
                logger.error(f"중복 username 오류 확인됨: {str(e)}")
                messages.error(self.request, '이미 사용 중인 사용자명입니다. 다른 사용자명을 선택해주세요.')
            else:
                logger.error(f"기타 IntegrityError: {str(e)}")
                messages.error(self.request, '회원가입 중 오류가 발생했습니다. 다시 시도해주세요.')
            
            # 폼 오류를 다시 표시
            return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, f'회원가입 중 예상치 못한 오류가 발생했습니다: {str(e)}')
            return self.form_invalid(form)

class StationSignUpView(CreateView):
    model = CustomUser
    form_class = StationSignUpForm
    template_name = 'OilNote_User/signup.html'
    success_url = reverse_lazy('users:login')

    def dispatch(self, request, *args, **kwargs):
        # 이미 로그인된 사용자는 메인 페이지로 리다이렉트
        if request.user.is_authenticated:
            if request.user.user_type == 'CUSTOMER':
                return redirect('customer:main')
            else:
                return redirect('station:main')
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        try:
            # 폼에서 이미 user를 생성하고 저장했으므로, 여기서는 user 객체만 가져옴
            user = form.instance
            if not user.pk:  # 아직 저장되지 않은 경우에만 저장
                user = form.save()
            login(self.request, user)
            messages.success(self.request, '주유소 회원가입이 완료되었습니다.')
            return redirect('station:main')
            
        except IntegrityError as e:
            # 중복된 username 오류 처리
            if "Duplicate entry" in str(e) and "username" in str(e):
                messages.error(self.request, '이미 사용 중인 사용자명입니다. 다른 사용자명을 선택해주세요.')
            else:
                messages.error(self.request, '회원가입 중 오류가 발생했습니다. 다시 시도해주세요.')
            
            # 폼 오류를 다시 표시
            return self.form_invalid(form)
        except Exception as e:
            messages.error(self.request, f'회원가입 중 예상치 못한 오류가 발생했습니다: {str(e)}')
            return self.form_invalid(form)

class CustomLoginView(LoginView):
    form_class = CustomLoginForm
    template_name = 'OilNote_User/login.html'
    
    def get_success_url(self):
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
            
        if self.request.user.user_type == 'CUSTOMER':
            return reverse_lazy('customer:main')
        else:  # STATION
            return reverse_lazy('station:main')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        # messages.success(self.request, '로그인되었습니다.')
        return response

class CustomPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    form_class = CustomPasswordChangeForm
    template_name = 'OilNote_User/password_change.html'
    
    def get_success_url(self):
        if self.request.user.user_type == 'CUSTOMER':
            return reverse_lazy('customer:profile')
        else:  # STATION
            return reverse_lazy('station:profile')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, '비밀번호가 성공적으로 변경되었습니다.')
        return response

@login_required
def reset_password_to_1111(request):
    """사용자 비밀번호를 1111로 초기화"""
    if request.method == 'POST':
        user = request.user
        user.set_password('1111')
        user.pw_back = '1111'  # 백업도 업데이트
        user.save()
        
        # 세션 업데이트 (로그아웃 방지)
        from django.contrib.auth import update_session_auth_hash
        update_session_auth_hash(request, user)
        
        messages.success(request, '비밀번호가 1111로 초기화되었습니다.')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True, 'message': '비밀번호가 1111로 초기화되었습니다.'})
        
        # 사용자 타입에 따라 리다이렉트
        if user.user_type == 'CUSTOMER':
            return redirect('customer:profile')
        else:
            return redirect('station:profile')
    
    return redirect('home')

@login_required
def restore_backup_password(request):
    """백업 비밀번호로 복원"""
    if request.method == 'POST':
        user = request.user
        
        if user.pw_back:
            user.set_password(user.pw_back)
            user.save()
            
            # 세션 업데이트 (로그아웃 방지)
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, user)
            
            messages.success(request, '백업 비밀번호로 복원되었습니다.')
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': '백업 비밀번호로 복원되었습니다.'})
        else:
            messages.error(request, '백업 비밀번호가 없습니다.')
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'message': '백업 비밀번호가 없습니다.'})
        
        # 사용자 타입에 따라 리다이렉트
        if user.user_type == 'CUSTOMER':
            return redirect('customer:profile')
        else:
            return redirect('station:profile')
    
    return redirect('home')

def logout_view(request):
    logout(request)
    # messages.success(request, '로그아웃되었습니다.')
    return redirect('home')

@staff_member_required
def reset_password_admin(request, user_id):
    """관리자 페이지에서 사용자 비밀번호를 1111로 초기화"""
    user = get_object_or_404(CustomUser, id=user_id)
    user.set_password('1111')
    user.pw_back = '1111'
    user.save()
    messages.success(request, f'사용자 {user.username}의 비밀번호가 1111로 초기화되었습니다.')
    return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/admin/'))
