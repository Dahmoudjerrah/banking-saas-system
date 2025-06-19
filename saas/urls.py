
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path,include
from rest_framework_simplejwt.views import TokenObtainPairView,TokenRefreshView

urlpatterns = [
    path('admin/', admin.site.urls),
    # path('api/transactions/', include('apps.transactions.urls')),
    path('api/', include('apps.users.urls')),
    path('api/', include('apps.accounts.urls')),
    path('api/', include('apps.transactions.urls')),
    #path('api/token/',TokenObtainPairView.as_view()),
    path('api/token/refresh/',TokenRefreshView.as_view()),
    #path('',include('apps.adminselect.urls'))
    # path('phonenumber/', CheckPhoneNumberView.as_view(), name='check-phone-number'),
]

if settings.DEBUG is False:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)