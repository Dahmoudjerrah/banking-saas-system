from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'transactions', views.TransactionViewSet)
router.register(r'accounts', views.AccountViewSet)
router.register(r'fee-rules', views.FeeRuleViewSet)
router.register(r'fees', views.FeeViewSet)
router.register(r'payment-requests', views.PaymentRequestViewSet)
router.register(r'pre-transactions', views.PreTransactionViewSet)
router.register(r'demande-chequiers', views.DemandeChequiersViewSet)
router.register(r'dashboard', views.DashboardViewSet, basename='dashboard')

urlpatterns = [
    path('api/', include(router.urls)),
     path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    
    path('api/a/create_buseness_agancy_accounte/', views.RegistrationAcounteAgancyBisenessView.as_view(), name='buseness_agancy_accounte'),
]