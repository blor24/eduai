from django.utils.deprecation import MiddlewareMixin

class AllowPDFIframeMiddleware(MiddlewareMixin):
    def process_response(self, request, response):
        # Only modify media PDF responses
        if request.path.startswith('/media/') and request.path.endswith('.pdf'):
            response.headers['X-Frame-Options'] = 'SAMEORIGIN'  # or use: del response.headers['X-Frame-Options']
        return response