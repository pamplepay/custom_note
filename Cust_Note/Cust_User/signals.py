from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CustomUser, CustomerProfile, StationProfile


@receiver(post_save, sender=CustomUser)
def create_user_profile(sender, instance, created, **kwargs):
    """사용자 생성 시 사용자 타입에 따라 프로필 생성"""
    if created:
        if instance.user_type == 'CUSTOMER':
            CustomerProfile.objects.create(user=instance)
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
            instance.customer_profile.save()
    elif instance.user_type == 'STATION':
        if hasattr(instance, 'station_profile'):
            instance.station_profile.save() 