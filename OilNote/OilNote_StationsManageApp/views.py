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
