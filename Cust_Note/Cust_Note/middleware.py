class DisableSecurityHeadersMiddleware:
    """개발 환경에서 보안 헤더를 비활성화하는 미들웨어"""
    
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # Cross-Origin-Opener-Policy 헤더 제거
        if 'Cross-Origin-Opener-Policy' in response:
            del response['Cross-Origin-Opener-Policy']
            
        # 기타 문제가 될 수 있는 헤더들 제거
        headers_to_remove = [
            'Cross-Origin-Embedder-Policy',
            'Cross-Origin-Resource-Policy',
            'Referrer-Policy',
            'Content-Security-Policy',
            'Content-Security-Policy-Report-Only',
        ]
        
        for header in headers_to_remove:
            if header in response:
                del response[header]
                
        return response 