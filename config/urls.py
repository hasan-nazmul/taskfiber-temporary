from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.defaults import page_not_found, server_error, permission_denied

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.accounts.urls')),
    path('customers/', include('apps.customers.urls')),
    path('tickets/', include('apps.tickets.urls')),
    path('stock/', include('apps.stock.urls')),
    path('schedule/', include('apps.schedule.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    # Preview error pages during development
    urlpatterns += [
        path('test-404/', lambda r: page_not_found(r, Exception('Test 404'))),
        path('test-403/', lambda r: permission_denied(r, Exception('Test 403'))),
        path('test-500/', lambda r: server_error(r)),
    ]

# Custom error handlers
handler404 = 'django.views.defaults.page_not_found'
handler403 = 'django.views.defaults.permission_denied'
handler500 = 'django.views.defaults.server_error'