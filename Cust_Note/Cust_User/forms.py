from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.contrib.auth import get_user_model
from django.contrib import messages
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
            # StationProfile 생성 (중복 방지)
            from .models import StationProfile
            try:
                station_profile = StationProfile.objects.get(user=user)
                # 이미 존재하는 경우 정보 업데이트
                station_profile.station_name = self.cleaned_data['station_name']
                station_profile.phone = self.cleaned_data['phone']
                station_profile.address = self.cleaned_data['address']
                station_profile.business_number = self.cleaned_data['business_number']
                station_profile.save()
            except StationProfile.DoesNotExist:
                # 존재하지 않는 경우 새로 생성
                StationProfile.objects.create(
                    user=user,
                    station_name=self.cleaned_data['station_name'],
                    phone=self.cleaned_data['phone'],
                    address=self.cleaned_data['address'],
                    business_number=self.cleaned_data['business_number']
                )
        return user

class CustomerSignUpForm(CustomUserCreationForm):
    customer_phone = forms.CharField(
        max_length=15, 
        label='고객 전화번호',
        help_text='주유소에서 등록한 전화번호를 입력하면 멤버십카드가 자동으로 연동됩니다.'
    )
    
    class Meta(CustomUserCreationForm.Meta):
        fields = CustomUserCreationForm.Meta.fields + ('customer_phone', 'car_number',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user_type'].initial = 'CUSTOMER'
        self.fields['user_type'].widget = forms.HiddenInput()
        
        # 전화번호 필드에 패턴 추가
        self.fields['customer_phone'].widget.attrs.update({
            'pattern': '[0-9]{10,11}',
            'placeholder': '01012345678 (숫자만 입력)'
        })

    def clean_customer_phone(self):
        """전화번호 검증 및 정리"""
        phone = self.cleaned_data.get('customer_phone', '')
        if phone:
            # 하이픈과 공백 제거
            phone = phone.replace('-', '').replace(' ', '')
            
            # 숫자만 있는지 확인
            if not phone.isdigit():
                raise forms.ValidationError('전화번호는 숫자만 입력해주세요.')
            
            # 길이 확인 (10-11자리)
            if len(phone) not in [10, 11]:
                raise forms.ValidationError('전화번호는 10-11자리로 입력해주세요.')
            
            # 010으로 시작하는지 확인 (11자리인 경우)
            if len(phone) == 11 and not phone.startswith('010'):
                raise forms.ValidationError('올바른 휴대폰 번호 형식이 아닙니다.')
        
        return phone

    def save(self, commit=True):
        import logging
        logger = logging.getLogger(__name__)
        
        user = super().save(commit=False)
        
        if commit:
            user.save()
            logger.info(f"고객 사용자 생성 완료: {user.username}")
            
            # 고객 프로필 생성 (중복 방지)
            from .models import CustomerProfile
            phone = self.cleaned_data.get('customer_phone', '')
            logger.info(f"전화번호 정보: {phone}")
            
            try:
                customer_profile = CustomerProfile.objects.get(user=user)
                # 이미 존재하는 경우 전화번호만 업데이트
                if phone:
                    customer_profile.customer_phone = phone
                    customer_profile.save()
                    logger.info(f"기존 프로필 전화번호 업데이트: {phone}")
            except CustomerProfile.DoesNotExist:
                # 존재하지 않는 경우 새로 생성
                customer_profile = CustomerProfile.objects.create(
                    user=user,
                    customer_phone=phone
                )
                logger.info(f"새 프로필 생성 완료: {phone}")
            
            # 폰번호가 입력된 경우 멤버십카드 연동 시도
            if phone:
                try:
                    from Cust_StationApp.models import PhoneCardMapping
                    # 폰번호로 모든 연동 정보 찾기
                    phone_mappings = PhoneCardMapping.find_all_by_phone(phone)
                    logger.info(f"전화번호 {phone}로 찾은 매핑 수: {phone_mappings.count()}")
                    
                    linked_cards = []
                    linked_stations = []
                    
                    for phone_mapping in phone_mappings:
                        logger.info(f"매핑 확인: 카드={phone_mapping.membership_card.full_number}, 사용여부={phone_mapping.is_used}, 연동사용자={phone_mapping.linked_user.username if phone_mapping.linked_user else '없음'}")
                        
                        # 연동 가능한 조건:
                        # 1. is_used=False (미사용 상태)
                        # 2. is_used=True이지만 linked_user가 None (사용 중이지만 연동된 사용자가 없음)
                        can_link = (not phone_mapping.is_used) or (phone_mapping.is_used and not phone_mapping.linked_user)
                        
                        if can_link:
                            try:
                                # 연동 정보가 있고 연동 가능한 경우
                                phone_mapping.link_to_user(user)
                                logger.info(f"카드 연동 완료: {phone_mapping.membership_card.full_number}")
                                
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
                                logger.info(f"주유소-고객 관계 생성: {phone_mapping.station.username}")
                            except Exception as e:
                                logger.error(f"카드 연동 실패: {phone_mapping.membership_card.full_number}, 오류: {str(e)}")
                        else:
                            logger.info(f"카드 연동 불가: {phone_mapping.membership_card.full_number} (이미 다른 사용자와 연동됨)")
                    
                    # 고객 프로필에 멤버십카드 정보 업데이트 (여러 카드 지원)
                    if linked_cards:
                        customer_profile.membership_card = ','.join(linked_cards)
                        customer_profile.save()
                        logger.info(f"멤버십카드 정보 업데이트: {customer_profile.membership_card}")
                        
                        station_names = [station.station_profile.station_name for station in linked_stations if hasattr(station, 'station_profile')]
                        if station_names:
                            logger.info(f"연동된 주유소: {', '.join(station_names)}")
                        else:
                            logger.info("연동된 주유소 정보 없음")
                    else:
                        logger.info("연동된 멤버십카드 없음")
                        
                except Exception as e:
                    # 연동 실패 시에도 회원가입은 계속 진행
                    logger.error(f"폰번호 {phone} 멤버십카드 연동 실패: {str(e)}")
                    import traceback
                    logger.error(traceback.format_exc())
        
        return user

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