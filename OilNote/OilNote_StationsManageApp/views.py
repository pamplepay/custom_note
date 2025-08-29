from django.shortcuts import render
from django.contrib.auth.decorators import login_required


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
    context = {
        'page_title': '주유소 사업자 등록',
        'subtitle': 'Gas Station Business Registration'
    }
    return render(request, 'OilNote_StationsManageApp/business_registration.html', context)

@login_required
def product_registration(request):
    """유종 및 유외상품 등록 페이지"""
    context = {
        'page_title': '유종 및 유외상품 등록',
        'subtitle': 'Product and External Product Registration'
    }
    return render(request, 'OilNote_StationsManageApp/product_registration.html', context)

@login_required
def tank_registration(request):
    """탱크정보 등록 페이지"""
    context = {
        'page_title': '탱크정보 등록',
        'subtitle': 'Tank Information Registration'
    }
    return render(request, 'OilNote_StationsManageApp/tank_registration.html', context)

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
