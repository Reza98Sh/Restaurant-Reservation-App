from django.contrib import admin
from django.urls import path, include

from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularSwaggerView,
    SpectacularRedocView,
)


urlpatterns = [
    path('admin/', admin.site.urls),

    path('api/user/', include('users.urls')),      
    path('api/restaurant/', include('restaurant.urls')),      
    path('api/reservation/', include('reservation.urls')),      
    
    
    # API Schema
    path('api/schema/', SpectacularAPIView.as_view(), name='schema'),
    
    # Swagger UI
    path('api/docs/', SpectacularSwaggerView.as_view(url_name='schema'), name='swagger-ui'),
    
    # ReDoc UI
    path('api/redoc/', SpectacularRedocView.as_view(url_name='schema'), name='redoc'),
    
]