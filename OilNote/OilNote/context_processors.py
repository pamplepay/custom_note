from django.conf import settings

def debug_settings(request):
    return {
        'DEBUG': settings.DEBUG,
        'IS_DEVELOPMENT': settings.DEBUG or request.get_host().startswith(('127.0.0.1', 'localhost')),
    } 