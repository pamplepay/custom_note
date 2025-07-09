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
    template_name = 'Cust_User/signup.html'
    success_url = reverse_lazy('users:login')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, '회원가입이 완료되었습니다.')
        return redirect('customer:main')

class StationSignUpView(CreateView):
    model = CustomUser
    form_class = StationSignUpForm
    template_name = 'Cust_User/signup.html'
    success_url = reverse_lazy('users:login')

    def form_valid(self, form):
        user = form.save()
        login(self.request, user)
        messages.success(self.request, '주유소 회원가입이 완료되었습니다.')
        return redirect('station:main')

class CustomLoginView(LoginView):
    form_class = CustomLoginForm
    template_name = 'Cust_User/login.html'
    
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
    template_name = 'Cust_User/password_change.html'
    
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
