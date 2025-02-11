# middleware.py

import threading

_thread_locals = threading.local()

def get_current_user():
    return getattr(_thread_locals, 'user', None)

class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _thread_locals.user = request.user
        response = self.get_response(request)
        return response


import logging
from django.utils.deprecation import MiddlewareMixin

logger = logging.getLogger('myapp')

class RequestLogMiddleware(MiddlewareMixin):
    def process_request(self, request):
        logger.info(f'Incoming request: {request.method} {request.path} by user {request.user}')

    def process_response(self, request, response):
        logger.info(f'Response status: {response.status_code} for {request.method} {request.path} by user {request.user}')
        return response

    def process_exception(self, request, exception):
        logger.error(f'Exception occurred: {exception} for {request.method} {request.path} by user {request.user}')

