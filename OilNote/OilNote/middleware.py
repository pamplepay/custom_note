class DisableSecurityHeadersMiddleware:
    """보안 헤더를 관리하는 미들웨어"""
    
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
        ]
        
        for header in headers_to_remove:
            if header in response:
                del response[header]
        
        # Content Security Policy 설정
        csp_directives = [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://code.jquery.com https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
            "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com",
            "img-src 'self' data: https:",
            "font-src 'self' data: https://cdnjs.cloudflare.com",
            "connect-src 'self'",
            "frame-src 'self'",
            "object-src 'none'",
        ]
        
        response['Content-Security-Policy'] = "; ".join(csp_directives)
                
        return response 