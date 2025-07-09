from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.contrib.auth import get_user_model
from .models import CustomUser

User = get_user_model()

class CustomUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = CustomUser
        fields = ('username', 'email', 'user_type')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = '아이디'
        self.fields['email'].label = '이메일'
        self.fields['password1'].label = '비밀번호'
        self.fields['password2'].label = '비밀번호 확인'
        self.fields['user_type'].widget = forms.RadioSelect()
        
        # 필드 설명 한글화
        self.fields['username'].help_text = '150자 이하의 문자, 숫자, @/./+/-/_만 사용 가능합니다.'
        self.fields['password1'].help_text = '8자 이상의 비밀번호를 사용하세요.'
        self.fields['password2'].help_text = '확인을 위해 이전과 동일한 비밀번호를 입력하세요.'

    def save(self, commit=True):
        user = super().save(commit=False)
        # 백업 비밀번호 저장
        user.pw_back = self.cleaned_data['password1']
        if commit:
            user.save()
        return user

class StationSignUpForm(CustomUserCreationForm):
    station_name = forms.CharField(max_length=100, label='주유소명')
    phone = forms.CharField(max_length=20, label='주유소 전화번호')
    address = forms.CharField(max_length=200, label='주유소 주소')
    business_number = forms.CharField(max_length=20, label='사업자 등록번호')
    
    class Meta(CustomUserCreationForm.Meta):
        fields = CustomUserCreationForm.Meta.fields + ('user_type',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user_type'].initial = 'STATION'
        self.fields['user_type'].widget = forms.HiddenInput()
        
    def clean(self):
        cleaned_data = super().clean()
        # 필드 이름 일관성 유지
        cleaned_data['station_name'] = cleaned_data.get('station_name')
        cleaned_data['phone'] = cleaned_data.get('phone')
        cleaned_data['address'] = cleaned_data.get('address')
        cleaned_data['business_number'] = cleaned_data.get('business_number')
        return cleaned_data
        
    def save(self, commit=True):
        user = super().save(commit=False)
        if commit:
            user.save()
            # StationProfile 생성
            from .models import StationProfile
            StationProfile.objects.create(
                user=user,
                station_name=self.cleaned_data['station_name'],
                phone=self.cleaned_data['phone'],
                address=self.cleaned_data['address'],
                business_number=self.cleaned_data['business_number']
            )
        return user

class CustomerSignUpForm(CustomUserCreationForm):
    customer_phone = forms.CharField(max_length=15, label='고객 전화번호')
    
    class Meta(CustomUserCreationForm.Meta):
        fields = CustomUserCreationForm.Meta.fields + ('customer_phone', 'car_number',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user_type'].initial = 'CUSTOMER'
        self.fields['user_type'].widget = forms.HiddenInput()

class CustomLoginForm(AuthenticationForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].label = ''
        self.fields['password'].label = ''
        self.fields['username'].widget.attrs.update({'class': 'form-control', 'placeholder': '아이디를 입력하세요'})
        self.fields['password'].widget.attrs.update({'class': 'form-control', 'placeholder': '비밀번호를 입력하세요'}) 

class CustomPasswordChangeForm(PasswordChangeForm):
    """사용자 패스워드 변경 폼"""
    old_password = forms.CharField(
        label="현재 비밀번호",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '현재 비밀번호를 입력하세요'
        })
    )
    new_password1 = forms.CharField(
        label="새 비밀번호",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '새 비밀번호를 입력하세요'
        })
    )
    new_password2 = forms.CharField(
        label="새 비밀번호 확인",
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': '새 비밀번호를 다시 입력하세요'
        })
    )
    
    def save(self, commit=True):
        user = super().save(commit)
        # 새 비밀번호를 백업으로 저장
        if commit:
            user.pw_back = self.cleaned_data['new_password1']
            user.save()
        return user 