from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import StationBusinessInfo, ProductInfo, TankInfo


@login_required
def dashboard(request):
    """주유소 관리 시스템 대시보드"""
    context = {
        'page_title': '주유소 관리 시스템',
        'subtitle': 'Service Station Management System'
    }
    return render(request, 'OilNote_StationsManageApp/dashboard.html', context)

@login_required
def business_registration(request):
    """주유소 사업자 등록 페이지"""
    try:
        # 현재 사용자의 주유소 사업자 정보 가져오기
        business_info = StationBusinessInfo.objects.get(user=request.user)
        is_new = False
    except StationBusinessInfo.DoesNotExist:
        business_info = None
        is_new = True
    
    if request.method == 'POST':
        # 폼 데이터 처리
        station_name = request.POST.get('station_name', '')
        representative_name = request.POST.get('representative_name', '')
        business_registration_number = request.POST.get('business_registration_number', '')
        sub_business_number = request.POST.get('sub_business_number', '')
        business_address = request.POST.get('business_address', '')
        business_type = request.POST.get('business_type', '')
        business_category = request.POST.get('business_category', '')
        phone_number = request.POST.get('phone_number', '')
        refinery_company = request.POST.get('refinery_company', '')
        petroleum_management_code = request.POST.get('petroleum_management_code', '')
        oil_code = request.POST.get('oil_code', '')
        
        # 필수 필드 검증
        if not all([station_name, representative_name, business_registration_number, business_address]):
            messages.error(request, '필수 항목을 모두 입력해주세요.')
            context = {
                'page_title': '주유소 사업자 등록',
                'subtitle': 'Gas Station Business Registration',
                'business_info': business_info,
                'is_new': is_new,
                'form_data': request.POST
            }
            return render(request, 'OilNote_StationsManageApp/business_registration.html', context)
        
        # 데이터 저장 또는 업데이트
        if business_info:
            # 기존 데이터 업데이트
            business_info.station_name = station_name
            business_info.representative_name = representative_name
            business_info.business_registration_number = business_registration_number
            business_info.sub_business_number = sub_business_number
            business_info.business_address = business_address
            business_info.business_type = business_type
            business_info.business_category = business_category
            business_info.phone_number = phone_number
            business_info.refinery_company = refinery_company
            business_info.petroleum_management_code = petroleum_management_code
            business_info.oil_code = oil_code
            business_info.save()
            messages.success(request, '주유소 사업자 정보가 성공적으로 수정되었습니다.')
        else:
            # 새 데이터 생성
            business_info = StationBusinessInfo.objects.create(
                user=request.user,
                station_name=station_name,
                representative_name=representative_name,
                business_registration_number=business_registration_number,
                sub_business_number=sub_business_number,
                business_address=business_address,
                business_type=business_type,
                business_category=business_category,
                phone_number=phone_number,
                refinery_company=refinery_company,
                petroleum_management_code=petroleum_management_code,
                oil_code=oil_code
            )
            messages.success(request, '주유소 사업자 정보가 성공적으로 등록되었습니다.')
        
        return redirect('stations_manage:business_registration')
    
    context = {
        'page_title': '주유소 사업자 등록',
        'subtitle': 'Gas Station Business Registration',
        'business_info': business_info,
        'is_new': is_new
    }
    return render(request, 'OilNote_StationsManageApp/business_registration.html', context)

@login_required
def delete_business_info(request):
    """주유소 사업자 정보 삭제"""
    if request.method == 'POST':
        try:
            business_info = StationBusinessInfo.objects.get(user=request.user)
            business_info.delete()
            messages.success(request, '주유소 사업자 정보가 삭제되었습니다.')
            return JsonResponse({'success': True})
        except StationBusinessInfo.DoesNotExist:
            return JsonResponse({'success': False, 'error': '삭제할 정보가 없습니다.'})
    
    return JsonResponse({'success': False, 'error': '잘못된 요청입니다.'})

@login_required
def product_registration(request):
    """유종 및 유외상품 등록 페이지"""
    # 현재 사용자의 상품 목록 가져오기
    products = ProductInfo.objects.filter(user=request.user).order_by('item_code')
    
    if request.method == 'POST':
        # 폼 데이터 처리
        item_code = request.POST.get('item_code', '').strip()
        item_name = request.POST.get('item_name', '').strip()
        product_category = request.POST.get('product_category', '')
        inventory_management = request.POST.get('inventory_management', '예')
        
        # 필수 필드 검증
        if not all([item_code, item_name, product_category]):
            messages.error(request, '필수 항목을 모두 입력해주세요.')
            context = {
                'page_title': '유종 및 유외상품 등록',
                'subtitle': 'Product and External Product Registration',
                'products': products,
                'form_data': request.POST
            }
            return render(request, 'OilNote_StationsManageApp/product_registration.html', context)
        
        # 품목 코드 중복 검사
        if ProductInfo.objects.filter(item_code=item_code).exists():
            messages.error(request, '이미 존재하는 품목 코드입니다.')
            context = {
                'page_title': '유종 및 유외상품 등록',
                'subtitle': 'Product and External Product Registration',
                'products': products,
                'form_data': request.POST
            }
            return render(request, 'OilNote_StationsManageApp/product_registration.html', context)
        
        # 새 상품 생성
        try:
            product = ProductInfo.objects.create(
                user=request.user,
                item_code=item_code,
                item_name=item_name,
                product_category=product_category,
                inventory_management=inventory_management
            )
            messages.success(request, f'상품 "{item_name}"이(가) 성공적으로 등록되었습니다.')
            return redirect('stations_manage:product_registration')
        except Exception as e:
            messages.error(request, f'상품 등록 중 오류가 발생했습니다: {str(e)}')
    
    context = {
        'page_title': '유종 및 유외상품 등록',
        'subtitle': 'Product and External Product Registration',
        'products': products
    }
    return render(request, 'OilNote_StationsManageApp/product_registration.html', context)

@login_required
def delete_product(request):
    """상품 삭제"""
    if request.method == 'POST':
        product_id = request.POST.get('product_id')
        try:
            product = ProductInfo.objects.get(id=product_id, user=request.user)
            product_name = product.item_name
            product.delete()
            messages.success(request, f'상품 "{product_name}"이(가) 삭제되었습니다.')
            return JsonResponse({'success': True})
        except ProductInfo.DoesNotExist:
            return JsonResponse({'success': False, 'error': '삭제할 상품을 찾을 수 없습니다.'})
    
    return JsonResponse({'success': False, 'error': '잘못된 요청입니다.'})

@login_required
def tank_registration(request):
    """탱크 정보 등록 페이지"""
    # 현재 사용자의 탱크 목록 가져오기
    tanks = TankInfo.objects.filter(user=request.user).order_by('tank_code')
    
    if request.method == 'POST':
        # 폼 데이터 처리
        tank_code = request.POST.get('tank_code', '').strip()
        tank_number = request.POST.get('tank_number', '').strip()
        fuel_type = request.POST.get('fuel_type', '')
        permitted_capacity = request.POST.get('permitted_capacity', '').strip()
        
        # 필수 필드 검증
        if not all([tank_code, tank_number, fuel_type, permitted_capacity]):
            messages.error(request, '필수 항목을 모두 입력해주세요.')
            context = {
                'page_title': '탱크 정보 등록',
                'subtitle': 'Tank Information Registration',
                'tanks': tanks,
                'form_data': request.POST
            }
            return render(request, 'OilNote_StationsManageApp/tank_registration.html', context)
        
        # 허가 용량 숫자 검증
        try:
            permitted_capacity = int(permitted_capacity.replace(',', ''))
        except ValueError:
            messages.error(request, '허가 용량은 숫자로 입력해주세요.')
            context = {
                'page_title': '탱크 정보 등록',
                'subtitle': 'Tank Information Registration',
                'tanks': tanks,
                'form_data': request.POST
            }
            return render(request, 'OilNote_StationsManageApp/tank_registration.html', context)
        
        # 탱크 코드 중복 검사
        if TankInfo.objects.filter(tank_code=tank_code).exists():
            messages.error(request, '이미 존재하는 탱크 코드입니다.')
            context = {
                'page_title': '탱크 정보 등록',
                'subtitle': 'Tank Information Registration',
                'tanks': tanks,
                'form_data': request.POST
            }
            return render(request, 'OilNote_StationsManageApp/tank_registration.html', context)
        
        # 새 탱크 생성
        try:
            tank = TankInfo.objects.create(
                user=request.user,
                tank_code=tank_code,
                tank_number=tank_number,
                fuel_type=fuel_type,
                permitted_capacity=permitted_capacity
            )
            messages.success(request, f'탱크 "{tank_code}"이(가) 성공적으로 등록되었습니다.')
            return redirect('stations_manage:tank_registration')
        except Exception as e:
            messages.error(request, f'탱크 등록 중 오류가 발생했습니다: {str(e)}')
    
    context = {
        'page_title': '탱크 정보 등록',
        'subtitle': 'Tank Information Registration',
        'tanks': tanks
    }
    return render(request, 'OilNote_StationsManageApp/tank_registration.html', context)

@login_required
def delete_tank(request):
    """탱크 삭제"""
    if request.method == 'POST':
        tank_id = request.POST.get('tank_id')
        try:
            tank = TankInfo.objects.get(id=tank_id, user=request.user)
            tank_code = tank.tank_code
            tank.delete()
            messages.success(request, f'탱크 "{tank_code}"이(가) 삭제되었습니다.')
            return JsonResponse({'success': True})
        except TankInfo.DoesNotExist:
            return JsonResponse({'success': False, 'error': '삭제할 탱크를 찾을 수 없습니다.'})
    
    return JsonResponse({'success': False, 'error': '잘못된 요청입니다.'})

@login_required
def nozzle_registration(request):
    """주유기 노즐정보 등록 페이지"""
    context = {
        'page_title': '주유기 노즐정보 등록',
        'subtitle': 'Fuel Dispenser Nozzle Information Registration'
    }
    return render(request, 'OilNote_StationsManageApp/nozzle_registration.html', context)

@login_required
def homelori_registration(request):
    """홈로리 차량 등록 페이지"""
    context = {
        'page_title': '홈로리 차량 등록',
        'subtitle': 'Homelori Vehicle Registration'
    }
    return render(request, 'OilNote_StationsManageApp/homelori_registration.html', context)

@login_required
def payment_registration(request):
    """결제 형태 등록 페이지"""
    context = {
        'page_title': '결제 형태 등록',
        'subtitle': 'Payment Type Registration'
    }
    return render(request, 'OilNote_StationsManageApp/payment_registration.html', context)
