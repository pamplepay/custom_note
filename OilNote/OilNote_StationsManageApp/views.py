from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from .models import StationBusinessInfo, ProductInfo, TankInfo, NozzleInfo, HomeloriVehicle, PaymentType


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
def tank_inventory(request):
    """탱크 기초재고 등록 및 관리 페이지"""
    try:
        # 현재 사용자의 탱크 정보 가져오기
        tanks = TankInfo.objects.filter(user=request.user)
    except:
        tanks = []
    
    if request.method == 'POST':
        # 폼 데이터 처리
        tank_number = request.POST.get('tank_number', '')
        fuel_type = request.POST.get('fuel_type', '')
        permitted_capacity = request.POST.get('permitted_capacity', '')
        initial_inventory = request.POST.get('initial_inventory', '')
        
        # 필수 필드 검증
        if not all([tank_number, fuel_type, permitted_capacity, initial_inventory]):
            messages.error(request, '필수 항목을 모두 입력해주세요.')
            context = {
                'page_title': '탱크 기초재고',
                'subtitle': 'Tank Initial Inventory',
                'tanks': tanks,
                'form_data': request.POST
            }
            return render(request, 'OilNote_StationsManageApp/tank_inventory.html', context)
        
        # 데이터 저장
        try:
            tank_info = TankInfo.objects.create(
                user=request.user,
                tank_number=tank_number,
                fuel_type=fuel_type,
                permitted_capacity=permitted_capacity,
                initial_inventory=initial_inventory
            )
            messages.success(request, '탱크 기초재고가 성공적으로 등록되었습니다.')
            return redirect('stations_manage:tank_inventory')
        except Exception as e:
            messages.error(request, f'저장 중 오류가 발생했습니다: {str(e)}')
    
    context = {
        'page_title': '탱크 기초재고',
        'subtitle': 'Tank Initial Inventory',
        'tanks': tanks
    }
    return render(request, 'OilNote_StationsManageApp/tank_inventory.html', context)

@login_required
def dispenser_meter(request):
    """주유기 기초계기자료 등록 및 관리 페이지"""
    try:
        # 현재 사용자의 노즐 정보 가져오기
        nozzles = NozzleInfo.objects.filter(user=request.user)
    except:
        nozzles = []
    
    if request.method == 'POST':
        # 폼 데이터 처리
        nozzle_number = request.POST.get('nozzle_number', '')
        connected_tank = request.POST.get('connected_tank', '')
        fuel_type = request.POST.get('fuel_type', '')
        initial_meter_data = request.POST.get('initial_meter_data', '')
        
        # 필수 필드 검증
        if not all([nozzle_number, connected_tank, fuel_type, initial_meter_data]):
            messages.error(request, '필수 항목을 모두 입력해주세요.')
            context = {
                'page_title': '주유기 기초계기자료',
                'subtitle': 'Fuel Dispenser Initial Meter Data',
                'nozzles': nozzles,
                'form_data': request.POST
            }
            return render(request, 'OilNote_StationsManageApp/dispenser_meter.html', context)
        
        # 데이터 저장
        try:
            nozzle_info = NozzleInfo.objects.create(
                user=request.user,
                nozzle_number=nozzle_number,
                connected_tank_id=connected_tank,
                fuel_type=fuel_type,
                initial_meter_data=initial_meter_data
            )
            messages.success(request, '주유기 기초계기자료가 성공적으로 등록되었습니다.')
            return redirect('stations_manage:dispenser_meter')
        except Exception as e:
            messages.error(request, f'저장 중 오류가 발생했습니다: {str(e)}')
    
    context = {
        'page_title': '주유기 기초계기자료',
        'subtitle': 'Fuel Dispenser Initial Meter Data',
        'nozzles': nozzles
    }
    return render(request, 'OilNote_StationsManageApp/dispenser_meter.html', context)

@login_required
def product_inventory(request):
    """유외상품 기초재고 등록 및 관리 페이지"""
    try:
        # 현재 사용자의 유외상품 정보 가져오기
        products = ProductInfo.objects.filter(user=request.user)
    except:
        products = []
    
    if request.method == 'POST':
        # 폼 데이터 처리
        item_name = request.POST.get('item_name', '')
        product_category = request.POST.get('product_category', '')
        inventory_management = request.POST.get('inventory_management', '')
        initial_inventory_quantity = request.POST.get('initial_inventory_quantity', '')
        
        # 필수 필드 검증
        if not all([item_name, product_category, inventory_management, initial_inventory_quantity]):
            messages.error(request, '필수 항목을 모두 입력해주세요.')
            context = {
                'page_title': '유외상품 기초재고',
                'subtitle': 'Non-Fuel Product Initial Inventory',
                'products': products,
                'form_data': request.POST
            }
            return render(request, 'OilNote_StationsManageApp/product_inventory.html', context)
        
        # 데이터 저장
        try:
            product_info = ProductInfo.objects.create(
                user=request.user,
                item_name=item_name,
                product_category=product_category,
                inventory_management=inventory_management,
                initial_inventory_quantity=initial_inventory_quantity
            )
            messages.success(request, '유외상품 기초재고가 성공적으로 등록되었습니다.')
            return redirect('stations_manage:product_inventory')
        except Exception as e:
            messages.error(request, f'저장 중 오류가 발생했습니다: {str(e)}')
    
    context = {
        'page_title': '유외상품 기초재고',
        'subtitle': 'Non-Fuel Product Initial Inventory',
        'products': products
    }
    return render(request, 'OilNote_StationsManageApp/product_inventory.html', context)

@login_required
def receivables(request):
    """외상채권 기초잔액 등록 및 관리 페이지"""
    try:
        # 현재 사용자의 외상채권 정보 가져오기
        receivables_list = StationBusinessInfo.objects.filter(user=request.user)
    except:
        receivables_list = []
    
    if request.method == 'POST':
        # 폼 데이터 처리
        customer_name = request.POST.get('customer_name', '')
        initial_balance = request.POST.get('initial_balance', '')
        
        # 필수 필드 검증
        if not all([customer_name, initial_balance]):
            messages.error(request, '필수 항목을 모두 입력해주세요.')
            context = {
                'page_title': '외상채권 기초잔액',
                'subtitle': 'Accounts Receivable Initial Balance',
                'receivables': receivables_list,
                'form_data': request.POST
            }
            return render(request, 'OilNote_StationsManageApp/receivables.html', context)
        
        # 데이터 저장
        try:
            # 기존 거래처가 있는지 확인
            business_info, created = StationBusinessInfo.objects.get_or_create(
                user=request.user,
                business_name=customer_name,
                defaults={
                    'business_code': f"{len(receivables_list) + 1:06d}",
                    'business_type': '외상',
                    'initial_balance': initial_balance
                }
            )
            
            if not created:
                # 기존 거래처인 경우 잔액 업데이트
                business_info.initial_balance = initial_balance
                business_info.save()
            
            messages.success(request, '외상채권 기초잔액이 성공적으로 등록되었습니다.')
            return redirect('stations_manage:receivables')
        except Exception as e:
            messages.error(request, f'저장 중 오류가 발생했습니다: {str(e)}')
    
    context = {
        'page_title': '외상채권 기초잔액',
        'subtitle': 'Accounts Receivable Initial Balance',
        'receivables': receivables_list
    }
    return render(request, 'OilNote_StationsManageApp/receivables.html', context)

@login_required
def customer_registration(request):
    """거래처 등록 및 수정 페이지"""
    context = {
        'page_title': '거래처 등록 및 수정',
        'subtitle': 'Customer Registration and Modification'
    }
    return render(request, 'OilNote_StationsManageApp/customer_registration.html', context)

@login_required
def vehicle_credit_registration(request):
    """차량 / 외상카드 등록 페이지"""
    context = {
        'page_title': '차량 / 외상카드 등록',
        'subtitle': 'Vehicle / Credit Card Registration'
    }
    return render(request, 'OilNote_StationsManageApp/vehicle_credit_registration.html', context)

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
def delete_nozzle(request):
    """노즐 삭제"""
    if request.method == 'POST':
        nozzle_id = request.POST.get('nozzle_id')
        try:
            nozzle = NozzleInfo.objects.get(id=nozzle_id, user=request.user)
            nozzle_code = nozzle.nozzle_code
            nozzle.delete()
            messages.success(request, f'노즐 "{nozzle_code}"이(가) 삭제되었습니다.')
            return JsonResponse({'success': True})
        except NozzleInfo.DoesNotExist:
            return JsonResponse({'success': False, 'error': '삭제할 노즐을 찾을 수 없습니다.'})
    
    return JsonResponse({'success': False, 'error': '잘못된 요청입니다.'})

@login_required
def nozzle_registration(request):
    """주유기 노즐정보 등록 페이지"""
    # 현재 사용자의 노즐 정보와 탱크 정보 가져오기
    nozzles = NozzleInfo.objects.filter(user=request.user).order_by('nozzle_code')
    tanks = TankInfo.objects.filter(user=request.user).order_by('tank_code')
    
    if request.method == 'POST':
        # 폼 데이터 처리
        nozzle_code = request.POST.get('nozzle_code', '').strip()
        nozzle_number = request.POST.get('nozzle_number', '').strip()
        connected_tank_id = request.POST.get('connected_tank', '')
        fuel_type = request.POST.get('fuel_type', '').strip()
        
        # 필수 필드 검증
        if not all([nozzle_code, nozzle_number, connected_tank_id, fuel_type]):
            messages.error(request, '필수 항목을 모두 입력해주세요.')
            context = {
                'page_title': '주유기 노즐정보 등록',
                'subtitle': 'Fuel Dispenser Nozzle Information Registration',
                'nozzles': nozzles,
                'tanks': tanks,
                'form_data': request.POST
            }
            return render(request, 'OilNote_StationsManageApp/nozzle_registration.html', context)
        
        # 노즐 코드 중복 검사
        if NozzleInfo.objects.filter(nozzle_code=nozzle_code).exists():
            messages.error(request, '이미 존재하는 노즐 코드입니다.')
            context = {
                'page_title': '주유기 노즐정보 등록',
                'subtitle': 'Fuel Dispenser Nozzle Information Registration',
                'nozzles': nozzles,
                'tanks': tanks,
                'form_data': request.POST
            }
            return render(request, 'OilNote_StationsManageApp/nozzle_registration.html', context)
        
        # 연결된 탱크 정보 가져오기
        try:
            connected_tank = TankInfo.objects.get(id=connected_tank_id, user=request.user)
        except TankInfo.DoesNotExist:
            messages.error(request, '선택한 탱크를 찾을 수 없습니다.')
            context = {
                'page_title': '주유기 노즐정보 등록',
                'subtitle': 'Fuel Dispenser Nozzle Information Registration',
                'nozzles': nozzles,
                'tanks': tanks,
                'form_data': request.POST
            }
            return render(request, 'OilNote_StationsManageApp/nozzle_registration.html', context)
        
        # 새 노즐 생성
        try:
            nozzle = NozzleInfo.objects.create(
                user=request.user,
                nozzle_code=nozzle_code,
                nozzle_number=nozzle_number,
                connected_tank=connected_tank,
                fuel_type=fuel_type
            )
            messages.success(request, f'노즐 "{nozzle_code}"이(가) 성공적으로 등록되었습니다.')
            return redirect('stations_manage:nozzle_registration')
        except Exception as e:
            messages.error(request, f'노즐 등록 중 오류가 발생했습니다: {str(e)}')
    
    context = {
        'page_title': '주유기 노즐정보 등록',
        'subtitle': 'Fuel Dispenser Nozzle Information Registration',
        'nozzles': nozzles,
        'tanks': tanks
    }
    return render(request, 'OilNote_StationsManageApp/nozzle_registration.html', context)

@login_required
def homelori_registration(request):
    """홈로리 차량 등록 페이지"""
    # 현재 사용자의 홈로리 차량 정보 가져오기
    vehicles = HomeloriVehicle.objects.filter(user=request.user).order_by('vehicle_code')
    
    if request.method == 'POST':
        # 폼 데이터 처리
        vehicle_code = request.POST.get('vehicle_code', '').strip()
        vehicle_number = request.POST.get('vehicle_number', '').strip()
        fuel_type = request.POST.get('fuel_type', '').strip()
        permitted_capacity = request.POST.get('permitted_capacity', '').strip()
        
        # 필수 필드 검증
        if not all([vehicle_code, vehicle_number, fuel_type, permitted_capacity]):
            messages.error(request, '필수 항목을 모두 입력해주세요.')
            context = {
                'page_title': '홈로리 차량 등록',
                'subtitle': 'Homelori Vehicle Registration',
                'vehicles': vehicles,
                'form_data': request.POST
            }
            return render(request, 'OilNote_StationsManageApp/homelori_registration.html', context)
        
        # 허가 용량 숫자 검증
        try:
            permitted_capacity = int(permitted_capacity.replace(',', ''))
        except ValueError:
            messages.error(request, '허가 용량은 숫자로 입력해주세요.')
            context = {
                'page_title': '홈로리 차량 등록',
                'subtitle': 'Homelori Vehicle Registration',
                'vehicles': vehicles,
                'form_data': request.POST
            }
            return render(request, 'OilNote_StationsManageApp/homelori_registration.html', context)
        
        # 차량 코드 중복 검사
        if HomeloriVehicle.objects.filter(vehicle_code=vehicle_code).exists():
            messages.error(request, '이미 존재하는 차량 코드입니다.')
            context = {
                'page_title': '홈로리 차량 등록',
                'subtitle': 'Homelori Vehicle Registration',
                'vehicles': vehicles,
                'form_data': request.POST
            }
            return render(request, 'OilNote_StationsManageApp/homelori_registration.html', context)
        
        # 새 차량 생성
        try:
            vehicle = HomeloriVehicle.objects.create(
                user=request.user,
                vehicle_code=vehicle_code,
                vehicle_number=vehicle_number,
                fuel_type=fuel_type,
                permitted_capacity=permitted_capacity
            )
            messages.success(request, f'홈로리 차량 "{vehicle_code}"이(가) 성공적으로 등록되었습니다.')
            return redirect('stations_manage:homelori_registration')
        except Exception as e:
            messages.error(request, f'차량 등록 중 오류가 발생했습니다: {str(e)}')
    
    context = {
        'page_title': '홈로리 차량 등록',
        'subtitle': 'Homelori Vehicle Registration',
        'vehicles': vehicles
    }
    return render(request, 'OilNote_StationsManageApp/homelori_registration.html', context)

@login_required
def delete_homelori_vehicle(request):
    """홈로리 차량 삭제"""
    if request.method == 'POST':
        vehicle_id = request.POST.get('vehicle_id')
        try:
            vehicle = HomeloriVehicle.objects.get(id=vehicle_id, user=request.user)
            vehicle_code = vehicle.vehicle_code
            vehicle.delete()
            messages.success(request, f'홈로리 차량 "{vehicle_code}"이(가) 삭제되었습니다.')
            return JsonResponse({'success': True})
        except HomeloriVehicle.DoesNotExist:
            return JsonResponse({'success': False, 'error': '삭제할 차량을 찾을 수 없습니다.'})
    
    return JsonResponse({'success': False, 'error': '잘못된 요청입니다.'})

@login_required
def payment_registration(request):
    """결제 형태 등록 페이지"""
    # 현재 사용자의 결제 형태 정보 가져오기
    payment_types = PaymentType.objects.filter(user=request.user).order_by('code_number')
    
    if request.method == 'POST':
        # 폼 데이터 처리
        code_number = request.POST.get('code_number', '').strip()
        payment_type_name = request.POST.get('payment_type_name', '').strip()
        
        # 필수 필드 검증
        if not all([code_number, payment_type_name]):
            messages.error(request, '필수 항목을 모두 입력해주세요.')
            context = {
                'page_title': '결제 형태 등록',
                'subtitle': 'Payment Type Registration',
                'payment_types': payment_types,
                'form_data': request.POST
            }
            return render(request, 'OilNote_StationsManageApp/payment_registration.html', context)
        
        # 코드 번호 중복 검사
        if PaymentType.objects.filter(code_number=code_number).exists():
            messages.error(request, '이미 존재하는 코드 번호입니다.')
            context = {
                'page_title': '결제 형태 등록',
                'subtitle': 'Payment Type Registration',
                'payment_types': payment_types,
                'form_data': request.POST
            }
            return render(request, 'OilNote_StationsManageApp/payment_registration.html', context)
        
        # 새 결제 형태 생성
        try:
            payment_type = PaymentType.objects.create(
                user=request.user,
                code_number=code_number,
                payment_type_name=payment_type_name
            )
            messages.success(request, f'결제 형태 "{code_number}"이(가) 성공적으로 등록되었습니다.')
            return redirect('stations_manage:payment_registration')
        except Exception as e:
            messages.error(request, f'결제 형태 등록 중 오류가 발생했습니다: {str(e)}')
    
    context = {
        'page_title': '결제 형태 등록',
        'subtitle': 'Payment Type Registration',
        'payment_types': payment_types
    }
    return render(request, 'OilNote_StationsManageApp/payment_registration.html', context)

@login_required
def delete_payment_type(request):
    """결제 형태 삭제"""
    if request.method == 'POST':
        payment_type_id = request.POST.get('payment_type_id')
        try:
            payment_type = PaymentType.objects.get(id=payment_type_id, user=request.user)
            code_number = payment_type.code_number
            payment_type.delete()
            messages.success(request, f'결제 형태 "{code_number}"이(가) 삭제되었습니다.')
            return JsonResponse({'success': True})
        except PaymentType.DoesNotExist:
            return JsonResponse({'success': False, 'error': '삭제할 결제 형태를 찾을 수 없습니다.'})
    
    return JsonResponse({'success': False, 'error': '잘못된 요청입니다.'})
