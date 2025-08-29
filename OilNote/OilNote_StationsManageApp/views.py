from django.shortcuts import render
from django.contrib.auth.decorators import login_required


@login_required
def dashboard(request):
    """주유소 관리 시스템 대시보드"""
    context = {
        'page_title': '주유소 판매관리 시스템',
        'subtitle': 'Service Station Sales Management System'
    }
    return render(request, 'OilNote_StationsManageApp/dashboard.html', context)
