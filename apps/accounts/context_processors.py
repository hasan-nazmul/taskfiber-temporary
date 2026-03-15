from django.core.cache import cache


def module_access_processor(request):
    """
    Injects a 'user_access' dictionary into the template context
    with the granular module access levels for the logged in employee.
    Cached per user for 5 minutes to avoid repeated DB lookups.
    """
    levels = {
        'tickets': 'none',
        'customers': 'none',
        'zones': 'none',
        'stock': 'none',
        'schedule': 'none',
        'employees': 'none',
        'teams': 'none',
        'accounts': 'none',
    }
    is_admin = False

    if request.user.is_authenticated:
        cache_key = f'user_access_{request.user.id}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        if getattr(request.user, 'is_superuser', False):
            is_admin = True
            for k in levels:
                levels[k] = 'full'
        elif hasattr(request.user, 'employee'):
            if request.user.employee.is_manager:
                is_admin = True
                for k in levels:
                    levels[k] = 'full'
            else:
                try:
                    access = request.user.employee.module_access
                    levels['tickets'] = access.tickets_access
                    levels['customers'] = access.customers_access
                    levels['zones'] = access.zones_access
                    levels['stock'] = access.stock_access
                    levels['schedule'] = access.schedule_access
                    levels['employees'] = access.employees_access
                    levels['teams'] = access.teams_access
                    levels['accounts'] = access.accounts_finance_access
                except Exception:
                    pass

        result = {
            'user_access': levels,
            'has_admin_privileges': is_admin
        }
        cache.set(cache_key, result, 300)
        return result

    return {
        'user_access': levels,
        'has_admin_privileges': is_admin
    }
