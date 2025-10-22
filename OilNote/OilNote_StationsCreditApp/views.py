from django.shortcuts import render
from django.contrib.auth.decorators import login_required

# Create your views here.

@login_required
def dashboard(request):
    """외상노트 대시보드"""
    context = {
        'title': '외상노트',
        'page_title': '외상 관리 대시보드'
    }
    return render(request, 'OilNote_StationsCreditApp/dashboard.html', context)
