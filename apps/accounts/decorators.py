from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages
from django.core.exceptions import PermissionDenied

def check_module_access(module_name, required_level='view'):
    """
    Decorator to check if user has access to a specific module.
    Levels: 'none', 'view', 'edit', 'full'
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
                
            if getattr(request.user, 'is_superuser', False):
                return view_func(request, *args, **kwargs)
                
            if not hasattr(request.user, 'employee'):
                messages.error(request, "Employee profile required.")
                return redirect('login')
                
            if request.user.employee.is_manager:
                return view_func(request, *args, **kwargs)
                
            try:
                access = request.user.employee.module_access
                user_level = getattr(access, f"{module_name}_access", 'none')
            except Exception:
                user_level = 'none'

            levels = ['none', 'view', 'edit', 'full']
            try:
                user_idx = levels.index(user_level)
                req_idx = levels.index(required_level)
            except ValueError:
                user_idx = 0
                req_idx = 1
                
            if user_idx < req_idx:
                messages.error(request, f"You don't have '{required_level}' access to the {module_name.title()} module.")
                return redirect('dashboard')
                
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator
