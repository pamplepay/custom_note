from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, CustomerProfile, StationProfile
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    """사용자 생성 시 사용자 타입에 따라 프로필 생성"""
    if created:
        if instance.user_type == 'CUSTOMER':
            # 이미 프로필이 존재하면 생성하지 않음 (폼에서 이미 생성했을 수 있음)
            profile, created_profile = CustomerProfile.objects.get_or_create(user=instance)
            
            # 프로필이 새로 생성된 경우에만 기본값 설정
            if created_profile:
                # CustomUser의 car_number가 있으면 복사
                if instance.car_number:
                    profile.car_number = instance.car_number
                    profile.save(update_fields=['car_number'])
        elif instance.user_type == 'STATION':
            StationProfile.objects.create(
                user=instance,
                station_name=instance.station_name or '',
                address=instance.station_address or '',
                business_number=instance.business_number or '',
                oil_company_code='0',
                agency_code='000',
                station_code='000000000000'
            )


@receiver(post_save, sender=CustomUser)
def save_user_profile(sender, instance, **kwargs):
    """사용자 저장 시 프로필도 함께 저장"""
    if instance.user_type == 'CUSTOMER':
        if hasattr(instance, 'customer_profile'):
            # 기존 프로필 데이터를 보존하면서 저장
            profile = instance.customer_profile
            
            logger.info(f"[SIGNAL] save_user_profile 호출됨 - 사용자: {instance.username}")
            logger.info(f"[SIGNAL] 프로필 전화번호 (시그널 전): {profile.customer_phone}")
            logger.info(f"[SIGNAL] 프로필 차량번호 (시그널 전): {profile.car_number}")
            logger.info(f"[SIGNAL] CustomUser.car_number: {instance.car_number}")
            
            # 프로필에 데이터가 없는 경우에만 CustomUser의 데이터 복사
            # (폼에서 이미 설정한 데이터를 덮어쓰지 않도록)
            if instance.car_number and not profile.car_number:
                profile.car_number = instance.car_number
                # 변경사항이 있을 때만 저장
                profile.save(update_fields=['car_number'])
                logger.info(f"[SIGNAL] 차량번호 업데이트: {instance.car_number}")
            
            # 시그널에서 profile.save()를 호출하지 않음 - 폼에서 이미 저장했으므로
            logger.info(f"[SIGNAL] 프로필 저장하지 않음 (폼에서 이미 처리됨)")
    elif instance.user_type == 'STATION':
        if hasattr(instance, 'station_profile'):
            instance.station_profile.save() 