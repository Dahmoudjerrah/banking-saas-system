from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
# router.register(r'transactions', views.TransactionViewSet)
# router.register(r'accounts', views.AccountViewSet)
router.register(r'fee-rules', views.FeeRuleViewSet)
# router.register(r'fees', views.FeeViewSet)
# router.register(r'payment-requests', views.PaymentRequestViewSet)
# router.register(r'pre-transactions', views.PreTransactionViewSet)
# router.register(r'demande-chequiers', views.DemandeChequiersViewSet)
router.register(r'dashboard', views.DashboardViewSet, basename='dashboard')
router.register(r'user-management', views.UserManagementViewSet, basename='user-management')
urlpatterns = [
    path('api/auth/login/', views.LoginView.as_view(), name='login'),
    path("api/accounts/intern/", views.InternAccountListView.as_view(), name='list-internal-accounts'),
    path("api/accounts/personal/", views.ClientAccountListView.as_view(), name='list-client-accounts'),
    path("api/accounts/personal/non-valide/", views.ClientAccountNonValiderListView.as_view(), name='list-client-accounts'),
    path('api/accounts/personal/<int:id>/block/', views.BlockUnblockClientAccountView.as_view(), name='block-client-account'),
    path('api/accounts/personal/<int:id>/validate/', views.ValidateClientAccountView.as_view(), name='valider-client-account'),
    path("api/accounts/agency/", views.AgencyAccountListCreateView.as_view(), name='list-agency-accounts'),
    path("api/accounts/business/", views.BusinessAccountListCreateView.as_view(), name='list-busniss-accounts'),
    path("api/accounts/agency/register/with-user/", views.RegisterAgencyWithUserView.as_view(), name='create-agency-with-user-accounts'),
    path("api/accounts/agency/", views.RegistrationAcounteAgencyView.as_view(), name='create-agency-with-user-accounts'),
    path("api/accounts/busniss/register/with-user/", views.RegisterBusnissWithUserView.as_view(), name='create-busniss-with-user-accounts'),
    path("api/accounts/busniss/", views.RegistrationAcounteBusnissView.as_view(), name='create-busniss-with-user-accounts'),  
    path("api/internalaccounts/create/", views.InternAccountCreateView.as_view(), name='create-internal-accounts'),
    path("api/transactions/", views.TransactionListView.as_view(), name='list-transactions'),
    # path('api/transactions/statistics/', views.TransactionListView.as_view({'get': 'statistics'}), name='transaction-statistics'),
    path('api/', include(router.urls)),
    path('api/users/<int:pk>/update-phone/', views.UpdatePhoneNumberView.as_view(), name='update-phone'),
    path('api/accounts/<int:account_id>/statement/',views.AccountStatementView.as_view(),name='account-statement'),
]