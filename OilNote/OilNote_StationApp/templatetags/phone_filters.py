from django import template
import re

register = template.Library()

@register.filter
def mask_phone(phone_number):
    """
    폰번호의 중간 4자리를 ****로 마스킹 처리
    예: 01012345678 -> 010****5678
    """
    if not phone_number:
        return '-'
    
    # 숫자만 추출
    phone = re.sub(r'[^0-9]', '', str(phone_number))
    
    # 11자리 휴대폰 번호인 경우
    if len(phone) == 11:
        return f"{phone[:3]}****{phone[7:]}"
    # 10자리 전화번호인 경우
    elif len(phone) == 10:
        return f"{phone[:3]}****{phone[7:]}"
    else:
        # 다른 형식의 경우 원본 반환
        return phone_number 