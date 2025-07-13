from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, FileResponse
from django.contrib import messages
from django.db.models import Q
from Cust_User.models import CustomUser, CustomerProfile, CustomerStationRelation
from .models import PointCard, StationCardMapping, SalesData
from datetime import datetime, timedelta
import json
import logging
import re
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.db.transaction import TransactionManagementError
from django.views.decorators.http import require_http_methods
import os
from django.conf import settings
from django.db.utils import IntegrityError
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from excel_sample.models import SalesData as ExcelSalesData

logger = logging.getLogger(__name__)

@login_required
def station_main(request):
    """주유소 메인 페이지"""
    if not request.user.is_station:
        messages.error(request, '주유소 회원만 접근할 수 있습니다.')
        return redirect('home')
    
    # 카드 통계
    total_cards = StationCardMapping.objects.filter(is_active=True).count()
    active_cards = StationCardMapping.objects.filter(is_active=True, card__is_used=False).count()
    inactive_cards = StationCardMapping.objects.filter(is_active=True, card__is_used=True).count()
    
    context = {
        'total_cards': total_cards,
        'active_cards': active_cards,
        'inactive_cards': inactive_cards,
    }
    return render(request, 'Cust_Station/station_main.html', context)

@login_required
def station_management(request):
    """주유소 관리 페이지"""
    if not request.user.is_station:
        messages.error(request, '주유소 회원만 접근할 수 있습니다.')
        return redirect('home')
    
    # 현재 주유소의 카드 매핑 수 조회
    mappings = StationCardMapping.objects.filter(is_active=True)
    total_cards = mappings.count()
    active_cards = mappings.filter(card__is_used=False).count()
    inactive_cards = mappings.filter(card__is_used=True).count()
    
    # 비율 계산
    active_percentage = (active_cards / total_cards * 100) if total_cards > 0 else 0
    inactive_percentage = (inactive_cards / total_cards * 100) if total_cards > 0 else 0
    
    context = {
        'total_cards': total_cards,
        'active_cards': active_cards,
        'inactive_cards': inactive_cards,
        'active_percentage': active_percentage,
        'inactive_percentage': inactive_percentage,
    }
    
    return render(request, 'Cust_Station/station_management.html', context)

@login_required
def station_profile(request):
    """주유소 프로필 페이지"""
    if not request.user.is_station:
        messages.error(request, '주유소 회원만 접근할 수 있습니다.')
        return redirect('home')
    
    # 현재 주유소 프로필 가져오기 또는 생성
    try:
        station_profile = request.user.station_profile
    except:
        from Cust_User.models import StationProfile
        station_profile = StationProfile(user=request.user)
        station_profile.save()
    
    if request.method == 'POST':
        # POST 요청 처리
        station_profile.station_name = request.POST.get('station_name')
        station_profile.phone = request.POST.get('phone')
        station_profile.address = request.POST.get('address')
        station_profile.business_number = request.POST.get('business_number')
        station_profile.oil_company_code = request.POST.get('oil_company_code')
        station_profile.agency_code = request.POST.get('agency_code')
        station_profile.tid = request.POST.get('tid')
        
        try:
            station_profile.save()
            messages.success(request, '주유소 정보가 성공적으로 업데이트되었습니다.')
            return redirect('station:profile')
        except Exception as e:
            messages.error(request, f'정보 업데이트 중 오류가 발생했습니다: {str(e)}')
    
    # GET 요청 처리
    context = {
        'station_name': station_profile.station_name,
        'phone': station_profile.phone,
        'address': station_profile.address,
        'business_number': station_profile.business_number,
        'oil_company_code': station_profile.oil_company_code,
        'agency_code': station_profile.agency_code,
        'tid': station_profile.tid,
    }
    
    return render(request, 'Cust_Station/station_profile.html', context)

@login_required
def station_cardmanage(request):
    """주유소 카드 관리 페이지"""
    if not request.user.is_station:
        messages.error(request, '주유소 회원만 접근할 수 있습니다.')
        return redirect('home')
    
    # 현재 주유소의 카드 매핑 수 조회
    mappings = StationCardMapping.objects.filter(is_active=True)
    total_cards = mappings.count()
    
    # 카드 상태별 통계
    active_cards = mappings.filter(card__is_used=False).count()
    used_cards = mappings.filter(card__is_used=True).count()
    
    # 비율 계산
    active_percentage = (active_cards / total_cards * 100) if total_cards > 0 else 0
    used_percentage = (used_cards / total_cards * 100) if total_cards > 0 else 0
    
    # 최근 등록된 카드 3장 가져오기
    recent_cards = StationCardMapping.objects.select_related('card').filter(
        is_active=True
    ).order_by('-registered_at')[:3]
    
    cards_data = []
    for mapping in recent_cards:
        card = mapping.card
        cards_data.append({
            'number': card.number,
            'is_used': card.is_used,
            'created_at': mapping.registered_at.strftime('%Y-%m-%d %H:%M:%S')
        })
    
    # 주유소 TID 가져오기
    station_tid = None
    if hasattr(request.user, 'station_profile'):
        station_tid = request.user.station_profile.tid
        if not station_tid:
            messages.warning(request, '주유소 단말기 번호(TID)가 설정되어 있지 않습니다. 관리자에게 문의하세요.')
    
    context = {
        'total_cards': total_cards,
        'active_cards': active_cards,
        'used_cards': used_cards,
        'active_percentage': active_percentage,
        'used_percentage': used_percentage,
        'station_name': request.user.username,
        'recent_cards': cards_data,
        'station_tid': station_tid
    }
    
    return render(request, 'Cust_Station/station_cardmanage.html', context)

@login_required
def station_usermanage(request):
    """고객 관리 페이지"""
    if not request.user.is_station:
        return redirect('home')
    
    # 페이지네이션 설정
    page = request.GET.get('page', 1)
    search_query = request.GET.get('search', '')
    
    # 고객 목록 조회
    customer_relations = CustomerStationRelation.objects.filter(
        station=request.user
    ).select_related(
        'customer',
        'customer__customer_profile'
    ).order_by('-created_at')
    
    # 검색 필터링
    if search_query:
        customer_relations = customer_relations.filter(
            Q(customer__username__icontains=search_query) |
            Q(customer__customer_profile__customer_phone__icontains=search_query) |
            Q(customer__customer_profile__membership_card__icontains=search_query)
        )
    
    # 페이지네이터 설정
    paginator = Paginator(customer_relations, 10)  # 페이지당 10개
    
    try:
        current_page = paginator.page(page)
    except PageNotAnInteger:
        current_page = paginator.page(1)
    except EmptyPage:
        current_page = paginator.page(paginator.num_pages)
    
    # 페이지 범위 계산
    page_range = range(
        max(1, current_page.number - 2),
        min(paginator.num_pages + 1, current_page.number + 3)
    )
    
    # 고객 데이터 가공
    customers = []
    for relation in current_page:
        customer = relation.customer
        profile = customer.customer_profile
        
        customers.append({
            'id': customer.id,
            'phone': profile.customer_phone,
            'card_number': profile.membership_card,
            'last_visit': None,  # TODO: 방문 기록 추가
            'visit_count': 0,    # TODO: 방문 횟수 추가
            'created_at': relation.created_at
        })
    
    context = {
        'customers': customers,
        'current_page': int(page),
        'total_pages': paginator.num_pages,
        'page_range': page_range,
        'search_query': search_query,
        'station_tid': request.user.station_profile.tid if hasattr(request.user, 'station_profile') else None
    }
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse(context)
    
    return render(request, 'Cust_Station/station_usermanage.html', context)

@login_required
def update_customer_info(request):
    """고객 정보 업데이트"""
    if not request.user.is_station:
        return JsonResponse({'error': '권한이 없습니다.'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            customer_id = data.get('customer_id')
            phone = data.get('phone', '').strip()
            card_number = data.get('cardNumber', '').strip()
            
            customer = get_object_or_404(CustomUser, id=customer_id, user_type='CUSTOMER')
            
            # CustomerProfile 가져오기 또는 생성
            profile, created = CustomerProfile.objects.get_or_create(user=customer)
            
            # 전화번호와 카드번호 업데이트
            if phone:
                profile.customer_phone = phone
            if card_number:
                profile.membership_card = card_number
            
            profile.save()
            
            return JsonResponse({
                'success': True,
                'message': '고객 정보가 업데이트되었습니다.',
                'phone': profile.customer_phone,
                'cardNumber': profile.membership_card
            })
            
        except json.JSONDecodeError:
            return JsonResponse({'error': '잘못된 요청 형식입니다.'}, status=400)
        except CustomUser.DoesNotExist:
            return JsonResponse({'error': '고객을 찾을 수 없습니다.'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': '잘못된 요청 방식입니다.'}, status=405)

@login_required
def get_cards(request):
    """등록된 카드 목록 조회"""
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 접근 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        # 현재 주유소에 등록된 카드 매핑 조회
        mappings = StationCardMapping.objects.select_related('card').filter(
            is_active=True
        ).order_by('-registered_at')
        
        # 전체 카드 수 계산 (캐시되지 않도록 실제 쿼리 실행)
        total_count = mappings.count()
        logger.info(f"주유소 {request.user.username}의 등록 카드 수: {total_count}")
        
        # 카드 상태별 수 계산 (캐시되지 않도록 실제 쿼리 실행)
        active_count = mappings.filter(card__is_used=False).count()
        used_count = mappings.filter(card__is_used=True).count()
        
        logger.info(f"통계 정보 - 전체: {total_count}, 사용가능: {active_count}, 사용중: {used_count}")
        
        # 카드 목록 데이터 생성
        cards_data = []
        for mapping in mappings:
            card = mapping.card
            card_info = {
                'number': card.number,
                'is_used': card.is_used,
                'created_at': mapping.registered_at.strftime('%Y-%m-%d %H:%M:%S')
            }
            cards_data.append(card_info)
            logger.debug(f"카드 정보: {card_info}")
        
        return JsonResponse({
            'status': 'success',
            'cards': cards_data,
            'total_count': total_count,
            'active_count': active_count,
            'used_count': used_count
        })
    except Exception as e:
        logger.error(f"카드 목록 조회 중 오류 발생: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': str(e)
        }, status=500)

@login_required
def register_cards_single(request):
    """카드 개별 등록"""
    logger.info(f"개별 카드 등록 요청 - 사용자: {request.user.username}, 메소드: {request.method}")
    
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 카드 등록 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    if request.method == 'POST':
        try:
            logger.info(f"요청 본문: {request.body.decode('utf-8')}")
            data = json.loads(request.body)
            card_number = data.get('cardNumber', '').strip()
            tid = data.get('tid', '').strip()  # TID 값 추가
            logger.info(f"추출된 카드번호: '{card_number}', TID: '{tid}'")
            
            # 입력 검증
            if not card_number or len(card_number) != 16 or not card_number.isdigit():
                logger.warning(f"잘못된 카드번호 형식: '{card_number}' (길이: {len(card_number) if card_number else 0})")
                return JsonResponse({
                    'status': 'error',
                    'message': '카드번호는 16자리 숫자여야 합니다.'
                })
            
            if not tid:
                logger.warning("TID가 제공되지 않음")
                return JsonResponse({
                    'status': 'error',
                    'message': 'TID는 필수 입력값입니다.'
                })
            
            logger.info(f"카드 생성 시도: {card_number}")
            # get_or_create를 사용하여 중복 생성 방지
            card, created = PointCard.objects.get_or_create(
                number=card_number,
                defaults={'tids': []}
            )
            logger.info(f"카드 생성 결과: created={created}, card_id={card.id}")
            
            # TID 추가
            if tid not in card.tids:
                card.add_tid(tid)
                logger.info(f"카드에 TID 추가: {tid}")
            
            # 카드와 주유소 매핑 생성
            logger.info(f"매핑 생성 시도: 주유소={request.user.username}, 카드={card_number}")
            mapping, mapping_created = StationCardMapping.objects.get_or_create(
                tid=tid,
                card=card,
                defaults={'is_active': True}
            )
            logger.info(f"매핑 생성 결과: created={mapping_created}, mapping_id={mapping.id}")
            
            # 이미 매핑이 존재하지만 비활성화된 경우 활성화
            if not mapping_created and not mapping.is_active:
                mapping.is_active = True
                mapping.save()
                logger.info(f"비활성화된 매핑을 활성화함: mapping_id={mapping.id}")
            
            message = '카드가 성공적으로 등록되었습니다.'
            if not created and mapping_created:
                message = '기존 카드가 주유소에 등록되었습니다.'
            elif not created and not mapping_created:
                message = '이미 등록된 카드입니다.'
            
            return JsonResponse({
                'status': 'success',
                'message': message,
                'created': created,
                'mapping_created': mapping_created
            })
            
        except json.JSONDecodeError:
            logger.error("JSON 디코딩 오류")
            return JsonResponse({
                'status': 'error',
                'message': '잘못된 요청 형식입니다.'
            }, status=400)
        except Exception as e:
            logger.error(f"카드 등록 중 오류 발생: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': f'카드 등록 중 오류가 발생했습니다: {str(e)}'
            }, status=500)
    
    return JsonResponse({'status': 'error', 'message': '잘못된 요청 방식입니다.'}, status=405)

@login_required
def register_cards_bulk(request):
    """카드 일괄 등록"""
    logger.info(f"일괄 카드 등록 요청 - 사용자: {request.user.username}, 메소드: {request.method}")
    
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 카드 등록 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    if request.method == 'POST':
        try:
            # 주유소 프로필에서 정유사 코드와 대리점 코드 가져오기
            station_profile = request.user.station_profile
            if not station_profile:
                logger.error(f"주유소 프로필을 찾을 수 없음: {request.user.username}")
                return JsonResponse({
                    'status': 'error',
                    'message': '주유소 프로필 정보가 없습니다.'
                }, status=400)

            oil_company_code = station_profile.oil_company_code
            agency_code = station_profile.agency_code

            if not oil_company_code or len(oil_company_code) != 1:
                logger.error(f"잘못된 정유사 코드: {oil_company_code}")
                return JsonResponse({
                    'status': 'error',
                    'message': '주유소 프로필의 정유사 코드가 올바르지 않습니다.'
                }, status=400)

            if not agency_code or len(agency_code) != 3:
                logger.error(f"잘못된 대리점 코드: {agency_code}")
                return JsonResponse({
                    'status': 'error',
                    'message': '주유소 프로필의 대리점 코드가 올바르지 않습니다.'
                }, status=400)

            logger.info(f"요청 본문: {request.body.decode('utf-8')}")
            data = json.loads(request.body)
            start_num = data.get('startNumber', '').strip()
            try:
                card_count = int(data.get('cardCount', 0))
            except (ValueError, TypeError):
                logger.warning(f"잘못된 카드 수 형식: {data.get('cardCount')}")
                return JsonResponse({
                    'status': 'error',
                    'message': '카드 수는 숫자여야 합니다.'
                }, status=400)
            tid = data.get('tid', '').strip()
            
            logger.info(f"시작번호: {start_num}, 카드수: {card_count}, TID: {tid}")
            
            # 입력값 검증
            if not start_num or len(start_num) != 16 or not start_num.isdigit():
                logger.warning(f"잘못된 시작번호 형식: {start_num}")
                return JsonResponse({
                    'status': 'error',
                    'message': '시작번호는 16자리 숫자여야 합니다.'
                })
            
            if not card_count or card_count <= 0:
                logger.warning(f"잘못된 카드 수: {card_count}")
                return JsonResponse({
                    'status': 'error',
                    'message': '카드 수는 1개 이상이어야 합니다.'
                })
            
            if not tid:
                logger.warning("TID가 제공되지 않음")
                return JsonResponse({
                    'status': 'error',
                    'message': 'TID는 필수 입력값입니다.'
                })
            
            try:
                start_num = int(start_num)
            except ValueError:
                logger.warning(f"시작번호를 정수로 변환할 수 없음: {start_num}")
                return JsonResponse({
                    'status': 'error',
                    'message': '시작번호는 숫자여야 합니다.'
                }, status=400)

            registered_cards = []
            
            for i in range(card_count):
                card_number = str(start_num + i).zfill(16)
                logger.debug(f"카드 생성 시도: {card_number}")
                
                try:
                    # get_or_create를 사용하여 중복 생성 방지
                    card, created = PointCard.objects.get_or_create(
                        number=card_number,
                        defaults={
                            'tids': [],
                            'oil_company_code': oil_company_code,
                            'agency_code': agency_code
                        }
                    )
                    logger.debug(f"카드 생성 결과: created={created}, card_id={card.id}")
                    
                    # TID 추가
                    if tid not in card.tids:
                        logger.debug(f"카드 {card_number}에 TID {tid} 추가 시도")
                        card.tids.append(tid)
                        card.save()
                        logger.debug(f"카드 {card_number}의 업데이트된 TID 목록: {card.tids}")
                    
                    # 카드와 주유소 매핑 생성
                    logger.debug(f"매핑 생성 시도: 카드={card_number}, TID={tid}")
                    mapping, mapping_created = StationCardMapping.objects.get_or_create(
                        tid=tid,
                        card=card,
                        defaults={'is_active': True}
                    )
                    logger.debug(f"매핑 생성 결과: created={mapping_created}, mapping_id={mapping.id}")
                    
                    # 매핑이 이미 존재하지만 비활성화된 경우 활성화
                    if not mapping_created and not mapping.is_active:
                        mapping.is_active = True
                        mapping.save()
                        logger.info(f"비활성화된 매핑을 활성화함: mapping_id={mapping.id}")
                    
                    registered_cards.append({
                        'number': card.number,
                        'is_used': card.is_used,
                        'created_at': card.created_at.strftime('%Y-%m-%d %H:%M:%S')
                    })
                    
                except Exception as e:
                    logger.error(f"카드 {card_number} 생성 중 오류: {str(e)}", exc_info=True)
                    return JsonResponse({
                        'status': 'error',
                        'message': f'카드 {card_number} 생성 중 오류가 발생했습니다.'
                    }, status=500)
            
            return JsonResponse({
                'status': 'success',
                'message': f'{len(registered_cards)}개의 카드가 성공적으로 등록되었습니다.',
                'cards': registered_cards
            })
            
        except json.JSONDecodeError:
            logger.error("잘못된 JSON 형식")
            return JsonResponse({
                'status': 'error',
                'message': '잘못된 요청 형식입니다.'
            }, status=400)
        except Exception as e:
            logger.error(f"카드 일괄 등록 중 오류 발생: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': '카드 일괄 등록 중 오류가 발생했습니다.'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': '잘못된 요청 메소드입니다.'
    }, status=405)

@login_required
def update_card_status(request):
    """카드 사용 상태 업데이트"""
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 상태 업데이트 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            card_number = data.get('cardNumber', '').strip()
            is_used = data.get('isUsed', False)
            tid = data.get('tid', '').strip()  # TID 값 추가
            
            # 입력 검증
            if not card_number or len(card_number) != 16 or not card_number.isdigit():
                return JsonResponse({
                    'status': 'error',
                    'message': '카드번호가 올바르지 않습니다.'
                })
            
            if not tid:
                return JsonResponse({
                    'status': 'error',
                    'message': 'TID는 필수 입력값입니다.'
                })
            
            # 카드와 매핑 상태 업데이트
            try:
                # 카드 존재 여부 확인
                card = PointCard.objects.get(number=card_number)
                
                # 현재 주유소의 카드 매핑 확인
                mapping = StationCardMapping.objects.get(
                    tid=tid,
                    card=card,
                    is_active=True
                )
                
                # 카드 상태 업데이트
                old_status = card.is_used
                card.is_used = is_used
                card.save()
                
                # 상태 변경 로깅
                logger.info(
                    f"카드 상태 변경: {card_number}, "
                    f"주유소: {request.user.username}, "
                    f"이전 상태: {'사용중' if old_status else '미사용'}, "
                    f"변경 상태: {'사용중' if is_used else '미사용'}"
                )
                
                return JsonResponse({
                    'status': 'success',
                    'message': '카드 상태가 업데이트되었습니다.',
                    'cardNumber': card.number,
                    'isUsed': card.is_used
                })
            except PointCard.DoesNotExist:
                logger.warning(f"존재하지 않는 카드 상태 업데이트 시도: {card_number}")
                return JsonResponse({
                    'status': 'error',
                    'message': '등록되지 않은 카드번호입니다.'
                })
            except StationCardMapping.DoesNotExist:
                logger.warning(f"권한 없는 카드 상태 업데이트 시도: {card_number}, 주유소: {request.user.username}")
                return JsonResponse({
                    'status': 'error',
                    'message': '해당 카드에 대한 권한이 없습니다.'
                })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': '잘못된 요청 형식입니다.'
            }, status=400)
        except Exception as e:
            logger.error(f"카드 상태 업데이트 중 오류 발생: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': f'카드 상태 업데이트 중 오류가 발생했습니다: {str(e)}'
            }, status=500)
    
    return JsonResponse({'status': 'error', 'message': '잘못된 요청 방식입니다.'}, status=405)

@login_required
def delete_card(request):
    """멤버십 카드 삭제"""
    if not request.user.is_station:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            card_id = data.get('card_id')
            
            if not card_id:
                return JsonResponse({
                    'status': 'error',
                    'message': '멤버십 카드 ID는 필수입니다.'
                }, status=400)
            
            # 카드 매핑 삭제
            mapping = get_object_or_404(
                StationCardMapping,
                point_card_id=card_id,
                station=request.user
            )
            mapping.delete()
            
            return JsonResponse({
                'status': 'success',
                'message': '멤버십 카드가 성공적으로 삭제되었습니다.'
            })
            
        except Exception as e:
            logger.error(f"멤버십 카드 삭제 중 오류 발생: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': f'멤버십 카드 삭제 중 오류가 발생했습니다: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': '잘못된 요청 메소드입니다.'
    }, status=405)

@login_required
def station_couponmanage(request):
    """주유소 쿠폰 관리 페이지"""
    if not request.user.is_station:
        messages.error(request, '주유소 회원만 접근할 수 있습니다.')
        return redirect('home')
    
    context = {
        'station_name': request.user.username,
        'total_coupons': 0,
        'used_coupons': 0,
        'unused_coupons': 0
    }
    
    return render(request, 'Cust_Station/station_couponmanage.html', context)

@require_http_methods(["GET"])
@login_required
def get_unused_cards(request):
    """미사용 카드 목록 조회"""
    logger.info("=== 미사용 카드 목록 조회 시작 ===")
    logger.info(f"요청 사용자: {request.user.username}")
    
    try:
        # 미사용 카드 조회
        unused_cards = PointCard.objects.filter(is_used=False).order_by('-created_at')
        logger.debug(f"미사용 카드 수: {unused_cards.count()}")
        
        # 카드 정보 변환
        cards_data = [{
            'number': card.number,
            'tids': card.tids,
            'created_at': card.created_at.strftime('%Y-%m-%d %H:%M')
        } for card in unused_cards]
        
        logger.info("=== 미사용 카드 목록 조회 완료 ===")
        return JsonResponse({
            'status': 'success',
            'cards': cards_data
        })
        
    except Exception as e:
        logger.error(f"미사용 카드 목록 조회 중 오류: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': '카드 목록을 불러오는데 실패했습니다.'
        }, status=500)

@require_http_methods(["POST"])
def register_card(request):
    """멤버십 카드 등록 뷰"""
    logger.info("\n=== 멤버십 카드 등록 시작 ===")
    logger.info(f"요청 사용자: {request.user.username}")
    
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 카드 등록 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    try:
        # 주유소 프로필에서 정유사 코드와 대리점 코드 가져오기
        station_profile = request.user.station_profile
        if not station_profile:
            logger.error(f"주유소 프로필을 찾을 수 없음: {request.user.username}")
            return JsonResponse({
                'status': 'error',
                'message': '주유소 프로필 정보가 없습니다.'
            }, status=400)

        oil_company_code = station_profile.oil_company_code
        agency_code = station_profile.agency_code

        if not oil_company_code or len(oil_company_code) != 1:
            logger.error(f"잘못된 정유사 코드: {oil_company_code}")
            return JsonResponse({
                'status': 'error',
                'message': '주유소 프로필의 정유사 코드가 올바르지 않습니다.'
            }, status=400)

        if not agency_code or len(agency_code) != 3:
            logger.error(f"잘못된 대리점 코드: {agency_code}")
            return JsonResponse({
                'status': 'error',
                'message': '주유소 프로필의 대리점 코드가 올바르지 않습니다.'
            }, status=400)

        # 요청 데이터 파싱
        data = json.loads(request.body)
        card_number = data.get('card_number', '').strip()
        tid = data.get('tid', '').strip()  # TID 값 추가
        logger.debug(f"입력된 카드번호: {card_number}, TID: {tid}")
        
        # 입력값 검증
        if not card_number or len(card_number) != 16 or not card_number.isdigit():
            logger.warning(f"잘못된 카드번호 형식: {card_number}")
            return JsonResponse({
                'status': 'error',
                'message': '올바른 카드번호를 입력해주세요 (16자리 숫자)'
            })
        
        if not tid:
            logger.warning("TID가 제공되지 않음")
            return JsonResponse({
                'status': 'error',
                'message': 'TID는 필수 입력값입니다.'
            })
        
        # 카드번호 중복 체크
        if PointCard.objects.filter(number=card_number).exists():
            logger.warning(f"중복된 카드번호: {card_number}")
            return JsonResponse({
                'status': 'error',
                'message': '이미 등록된 카드번호입니다'
            })
        
        # 새 카드 생성
        new_card = PointCard.objects.create(
            number=card_number,
            oil_company_code=oil_company_code,
            agency_code=agency_code,
            tids=[tid],
            created_at=timezone.now()
        )
        logger.info(f"새 카드 등록 완료: {new_card.number}, TID: {tid}")
        
        # 주유소-카드 매핑 생성
        StationCardMapping.objects.create(
            tid=tid,
            card=new_card,
            registered_at=timezone.now(),
            is_active=True
        )
        logger.info(f"카드 매핑 생성 완료: {new_card.number}, TID: {tid}")
        
        return JsonResponse({
            'status': 'success',
            'message': '카드가 성공적으로 등록되었습니다.',
            'card': {
                'number': new_card.number,
                'is_used': new_card.is_used,
                'created_at': new_card.created_at.strftime('%Y-%m-%d %H:%M:%S')
            }
        })
        
    except json.JSONDecodeError:
        logger.error("잘못된 JSON 형식")
        return JsonResponse({
            'status': 'error',
            'message': '잘못된 요청 형식입니다.'
        }, status=400)
    except Exception as e:
        logger.error(f"카드 등록 중 오류 발생: {str(e)}", exc_info=True)
        return JsonResponse({
            'status': 'error',
            'message': '카드 등록 중 오류가 발생했습니다.'
        }, status=500)

@login_required
def register_customer(request):
    """신규 고객 등록"""
    logger.info("=== 고객 등록 프로세스 시작 ===")
    logger.info(f"요청 사용자: {request.user.username}")
    
    if not request.user.is_station:
        logger.warning(f"권한 없는 사용자의 접근 시도: {request.user.username}")
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    if request.method == 'POST':
        try:
            logger.info("POST 요청 데이터 처리 시작")
            data = json.loads(request.body)
            logger.debug(f"수신된 데이터: {json.dumps(data, ensure_ascii=False)}")
            
            phone = data.get('phone', '').strip()
            card_number = data.get('card_number', '').strip()
            
            logger.info(f"입력값 확인 - 전화번호: {phone}, 카드번호: {card_number}")
            
            # 입력값 검증
            if not phone or not card_number:
                logger.warning(f"필수 필드 누락 - 전화번호: {bool(phone)}, 카드번호: {bool(card_number)}")
                return JsonResponse({
                    'status': 'error',
                    'message': '전화번호와 카드번호를 모두 입력해주세요.'
                }, status=400)
            
            # 전화번호 형식 확인
            phone = re.sub(r'[^0-9]', '', phone)
            if not re.match(r'^\d{10,11}$', phone):
                logger.warning(f"잘못된 전화번호 형식: {phone} (길이: {len(phone)})")
                return JsonResponse({
                    'status': 'error',
                    'message': '올바른 전화번호 형식이 아닙니다.'
                }, status=400)
            
            # 카드번호 형식 확인
            card_number = re.sub(r'[^0-9]', '', card_number)
            if not re.match(r'^\d{16}$', card_number):
                logger.warning(f"잘못된 카드번호 형식: {card_number} (길이: {len(card_number)})")
                return JsonResponse({
                    'status': 'error',
                    'message': '올바른 카드번호 형식이 아닙니다.'
                }, status=400)
            
            try:
                with transaction.atomic():
                    # 카드 확인 (락 설정)
                    try:
                        card_mapping = StationCardMapping.objects.select_for_update().select_related('card').get(
                            card__number=card_number,
                            is_active=True
                        )
                        card = card_mapping.card
                    except StationCardMapping.DoesNotExist:
                        logger.warning(f"미등록 카드 - 카드번호: {card_number}")
                        return JsonResponse({
                            'status': 'error',
                            'message': '등록되지 않은 카드번호입니다.'
                        }, status=400)
                    
                    if card.is_used:
                        logger.warning(f"이미 사용 중인 카드 사용 시도: {card_number}")
                        return JsonResponse({
                            'status': 'error',
                            'message': '이미 사용 중인 카드입니다.'
                        }, status=400)

                    # 기존 사용자 확인 (락 설정)
                    existing_user = CustomUser.objects.select_for_update().filter(username=phone).first()
                    
                    if existing_user:
                        logger.info(f"기존 고객 발견: {phone} - 멤버십 카드만 연결")
                        
                        # 이미 이 주유소에 등록된 고객인지 확인
                        customer_relation = CustomerStationRelation.objects.filter(
                            customer=existing_user, 
                            station=request.user
                        ).first()

                        if not customer_relation:
                            # 주유소와 고객 관계 생성
                            CustomerStationRelation.objects.create(
                                customer=existing_user,
                                station=request.user
                            )
                            logger.info(f"주유소-고객 관계 생성 완료 - 고객: {existing_user.id}, 주유소: {request.user.username}")

                        # 고객 프로필 업데이트 - 멤버십 카드 추가
                        customer_profile = CustomerProfile.objects.get(user=existing_user)
                        if customer_profile.membership_card:
                            # 기존 카드 번호가 있으면 새 카드 번호를 추가 (쉼표로 구분)
                            existing_cards = set(customer_profile.membership_card.split(','))
                            existing_cards.add(card_number)
                            customer_profile.membership_card = ','.join(existing_cards)
                        else:
                            customer_profile.membership_card = card_number
                        customer_profile.save()
                        logger.info(f"고객 프로필 업데이트 완료 - 사용자: {existing_user.id}")
                        
                    else:
                        logger.info(f"신규 고객 등록 시작: {phone}")
                        # 신규 사용자 생성
                        new_user = CustomUser.objects.create_user(
                            username=phone,
                            password=card_number,
                            user_type='CUSTOMER',
                            pw_back=card_number  # 실제 카드번호를 백업 패스워드로 저장
                        )
                        logger.info(f"신규 사용자 생성 완료 - ID: {new_user.id}, 전화번호: {phone}")
                        
                        # 고객 프로필 생성
                        customer_profile, created = CustomerProfile.objects.get_or_create(
                            user=new_user,
                            defaults={
                                'customer_phone': phone,
                                'membership_card': card_number
                            }
                        )
                        if not created:
                            customer_profile.customer_phone = phone
                            customer_profile.membership_card = card_number
                            customer_profile.save()
                        logger.info(f"고객 프로필 생성 완료 - 사용자: {new_user.id}")
                        
                        # 주유소와 고객 관계 생성
                        CustomerStationRelation.objects.create(
                            customer=new_user,
                            station=request.user
                        )
                        logger.info(f"주유소-고객 관계 생성 완료 - 고객: {new_user.id}, 주유소: {request.user.username}")
                    
                    # 카드 상태 업데이트
                    card.is_used = True
                    card.save()
                    logger.info(f"카드 상태 업데이트 완료 - 카드번호: {card_number}")
                    
                    logger.info("=== 고객 등록 프로세스 완료 ===")
                    return JsonResponse({
                        'status': 'success',
                        'message': '고객이 성공적으로 등록되었습니다.'
                    })
                    
            except IntegrityError as e:
                logger.error(f"데이터베이스 무결성 오류: {str(e)}", exc_info=True)
                return JsonResponse({
                    'status': 'error',
                    'message': '고객 등록 중 무결성 오류가 발생했습니다. 이미 등록된 정보일 수 있습니다.'
                }, status=400)
            except Exception as e:
                logger.error(f"데이터베이스 처리 중 오류: {str(e)}", exc_info=True)
                return JsonResponse({
                    'status': 'error',
                    'message': '고객 등록 중 오류가 발생했습니다.'
                }, status=500)
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON 파싱 오류: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': '잘못된 요청 형식입니다.'
            }, status=400)
        except Exception as e:
            logger.error(f"예상치 못한 오류: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': '서버 오류가 발생했습니다.'
            }, status=500)
    
    logger.warning(f"잘못된 요청 방식: {request.method}")
    return JsonResponse({
        'status': 'error',
        'message': '잘못된 요청 방식입니다.'
    }, status=405)

@login_required
def delete_customer(request):
    """고객 삭제"""
    if not request.user.is_station:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            customer_id = data.get('customer_id')
            
            if not customer_id:
                return JsonResponse({
                    'status': 'error',
                    'message': '고객 ID는 필수입니다.'
                }, status=400)
            
            # 고객-주유소 관계 삭제
            relation = get_object_or_404(
                CustomerStationRelation,
                customer_id=customer_id,
                station=request.user
            )
            relation.delete()
            
            return JsonResponse({
                'status': 'success',
                'message': '고객이 성공적으로 삭제되었습니다.'
            })
            
        except Exception as e:
            logger.error(f"고객 삭제 중 오류 발생: {str(e)}", exc_info=True)
            return JsonResponse({
                'status': 'error',
                'message': f'고객 삭제 중 오류가 발생했습니다: {str(e)}'
            }, status=500)
    
    return JsonResponse({
        'status': 'error',
        'message': '잘못된 요청 메소드입니다.'
    }, status=405)

@login_required
def check_customer_exists(request):
    """전화번호로 사용자 존재 여부와 상태를 확인하는 뷰"""
    if not request.user.is_station:
        return JsonResponse({'status': 'error', 'message': '권한이 없습니다.'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            phone = data.get('phone', '').strip()
        except json.JSONDecodeError:
            return JsonResponse({
                'status': 'error',
                'message': '잘못된 요청 형식입니다.'
            }, status=400)
    elif request.method == 'GET':
        phone = request.GET.get('phone', '').strip()
    else:
        return JsonResponse({
            'status': 'error',
            'message': '지원하지 않는 요청 방식입니다.'
        }, status=405)

    if not phone:
        return JsonResponse({
            'status': 'error',
            'message': '전화번호를 입력해주세요.'
        }, status=400)

    # 전화번호 형식 확인 (숫자만 허용)
    phone = re.sub(r'[^0-9]', '', phone)
    if not re.match(r'^\d{10,11}$', phone):
        return JsonResponse({
            'status': 'error',
            'message': '올바른 전화번호 형식이 아닙니다.'
        }, status=400)

    try:
        # 사용자 검색
        user = CustomUser.objects.filter(username=phone).first()
        
        if not user:
            return JsonResponse({
                'status': 'success',
                'exists': False,
                'message': '사용 가능한 전화번호입니다.',
                'data': {
                    'can_register': True
                }
            })

        # 프로필 정보 가져오기
        profile = CustomerProfile.objects.filter(user=user).first()
        
        # 현재 주유소와의 관계 확인
        relation = CustomerStationRelation.objects.filter(
            customer=user,
            station=request.user
        ).exists()

        if relation:
            message = '이미 이 주유소에 등록된 고객입니다.'
            can_register = False
        else:
            message = '다른 주유소에 등록된 전화번호입니다. 새로운 카드로 등록 가능합니다.'
            can_register = True

        return JsonResponse({
            'status': 'success',
            'exists': True,
            'message': message,
            'data': {
                'phone': profile.customer_phone if profile else None,
                'membership_card': profile.membership_card if profile else None,
                'is_registered_here': relation,
                'can_register': can_register
            }
        })

    except Exception as e:
        print(f"[DEBUG] 사용자 확인 중 오류 발생: {str(e)}")
        return JsonResponse({
            'status': 'error',
            'message': '사용자 확인 중 오류가 발생했습니다.'
        }, status=500)

@login_required
def station_sales(request):
    """주유소 매출 관리 페이지"""
    if not request.user.is_station:
        messages.error(request, '주유소 회원만 접근할 수 있습니다.')
        return redirect('home')
    
    # 기존 주유소app SalesData
    sales_data = SalesData.objects.filter(station=request.user).order_by('-sales_date')
    # 엑셀에서 불러온 SalesData
    excel_sales_data = ExcelSalesData.objects.all().order_by('-sale_date', '-sale_time')
    
    context = {
        'sales_data': sales_data,
        'excel_sales_data': excel_sales_data,
    }
    
    return render(request, 'Cust_Station/station_sales.html', context)

from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

@login_required
@require_http_methods(["POST"])
def upload_sales_data(request):
    """매출 데이터 엑셀 파일 업로드 (TID별 폴더, TID_원본파일명으로 저장)"""
    if not request.user.is_station:
        return JsonResponse({'error': '권한이 없습니다.'}, status=403)
    
    # 중복 요청 방지를 위한 로깅
    import logging
    logger = logging.getLogger(__name__)
    
    # 중복 요청 방지를 위한 캐시 키 생성
    cache_key = f'upload_sales_{request.user.id}_{request.FILES.get("sales_file", {}).name if request.FILES else "no_file"}'
    
    # 이미 처리 중인 요청인지 확인
    if cache.get(cache_key):
        logger.warning(f'중복 업로드 요청 감지: {cache_key}')
        return JsonResponse({'error': '이미 처리 중인 요청입니다. 잠시 후 다시 시도해주세요.'}, status=429)
    
    # 캐시에 처리 중임을 표시 (5초 동안)
    cache.set(cache_key, True, 5)
    
    try:
        logger.info(f'파일 업로드 요청 시작 - 사용자: {request.user.username}')
        
        if 'sales_file' not in request.FILES:
            cache.delete(cache_key)
            return JsonResponse({'error': '파일이 선택되지 않았습니다.'}, status=400)
        
        sales_file = request.FILES['sales_file']
        if not sales_file.name.endswith('.xlsx'):
            cache.delete(cache_key)
            return JsonResponse({'error': '엑셀 파일(.xlsx)만 업로드 가능합니다.'}, status=400)
        
        # TID 가져오기
        tid = getattr(getattr(request.user, 'station_profile', None), 'tid', None)
        if not tid:
            cache.delete(cache_key)
            return JsonResponse({'error': '주유소 TID가 등록되어 있지 않습니다.'}, status=400)
        
        # 원본 파일명에서 디렉토리 제거
        import os
        original_name = os.path.basename(sales_file.name)
        # 파일명: tid_원본파일명
        file_name = f'{tid}_{original_name}'
        # 저장 경로: Cust_Note/upload/<TID>/
        upload_root = os.path.join(settings.BASE_DIR, 'upload', tid)
        os.makedirs(upload_root, exist_ok=True)
        file_path = os.path.join(upload_root, file_name)
        
        # 파일이 이미 존재하는지 확인
        if os.path.exists(file_path):
            logger.warning(f'파일이 이미 존재합니다: {file_path}')
            cache.delete(cache_key)
            return JsonResponse({'error': '동일한 파일이 이미 업로드되어 있습니다.'}, status=400)
        
        logger.info(f'파일 저장 시작: {file_path}')
        # 파일 저장
        with open(file_path, 'wb+') as destination:
            for chunk in sales_file.chunks():
                destination.write(chunk)
        
        logger.info(f'파일 업로드 완료: {file_name}')
        cache.delete(cache_key)  # 성공 시 캐시 삭제
        return JsonResponse({'message': f'파일이 성공적으로 업로드되었습니다: {file_name}'})
        
    except Exception as e:
        logger.error(f'엑셀 파일 업로드 중 오류 발생: {str(e)}')
        cache.delete(cache_key)  # 오류 시에도 캐시 삭제
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@require_http_methods(["DELETE"])
def delete_sales_data(request, sales_id):
    """매출 데이터 삭제"""
    if not request.user.is_station:
        return JsonResponse({'error': '권한이 없습니다.'}, status=403)
    
    try:
        sales_data = get_object_or_404(SalesData, id=sales_id, station=request.user)
        sales_data.delete()
        return JsonResponse({'message': '매출 데이터가 성공적으로 삭제되었습니다.'})
    
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def download_sales_file(request, sales_id):
    """매출 데이터 파일 다운로드"""
    if not request.user.is_station:
        return JsonResponse({'error': '권한이 없습니다.'}, status=403)
    
    try:
        sales_data = get_object_or_404(SalesData, id=sales_id, station=request.user)
        file_path = os.path.join(settings.MEDIA_ROOT, sales_data.file_name)
        
        if not os.path.exists(file_path):
            return JsonResponse({'error': '파일을 찾을 수 없습니다.'}, status=404)
        
        response = FileResponse(open(file_path, 'rb'))
        response['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        response['Content-Disposition'] = f'attachment; filename="{os.path.basename(file_path)}"'
        return response
        
    except Exception as e:
        logger.error(f'파일 다운로드 중 오류 발생: {str(e)}')
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def search_customer(request):
    """전화번호로 사용자를 검색하는 뷰"""
    if request.method == 'GET':
        phone = request.GET.get('phone')
        if not phone:
            return JsonResponse({
                'status': 'error',
                'message': '전화번호를 입력해주세요.'
            }, status=400)

        try:
            # 사용자 검색
            user = CustomUser.objects.filter(username=phone).first()
            
            if not user:
                return JsonResponse({
                    'status': 'success',
                    'exists': False,
                    'message': '등록되지 않은 사용자입니다.'
                })

            # 프로필 정보 가져오기
            profile = CustomerProfile.objects.filter(user=user).first()
            
            # 현재 주유소와의 관계 확인
            relation = CustomerStationRelation.objects.filter(
                customer=user,
                station=request.user
            ).exists()

            return JsonResponse({
                'status': 'success',
                'exists': True,
                'data': {
                    'phone': profile.customer_phone if profile else None,
                    'membership_card': profile.membership_card if profile else None,
                    'is_registered_here': relation
                },
                'message': '사용자를 찾았습니다.'
            })

        except Exception as e:
            print(f"[DEBUG] 사용자 검색 중 오류 발생: {str(e)}")
            return JsonResponse({
                'status': 'error',
                'message': '사용자 검색 중 오류가 발생했습니다.'
            }, status=500)
