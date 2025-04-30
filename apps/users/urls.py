from django.urls import path
from .views import UserRegistrationView,TransactionHistoryView,AddBusinessOrAgencyAccountView,AllAccountsView,UserProfileView,CustomTokenObtainPairView,RegistrationAcounteAgancyBisenessView,MerchantCodeValidationView,PhoneValidationView,PasswordValidationView

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('create_buseness_agancy_accounte/', RegistrationAcounteAgancyBisenessView.as_view(), name='buseness_agancy_accounte'),
    path('add_buseness_agancy_accounte/', AddBusinessOrAgencyAccountView.as_view(), name='add_buseness_agancy_accounte'),
    path('acounts/', AllAccountsView.as_view(), name='acounts'),
    path('token/', CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    #path('token/keycloak/', KeycloakTokenView.as_view(), name='token_keycloak'),
    path('test_tel/', PhoneValidationView.as_view(), name='tel'),

    #path('chek_wallet/', WalletValidationView.as_view(), name='chek_wallet'),
    path('chek_pass/', PasswordValidationView.as_view(), name='chek_pass'),
    path('paiement_code/', MerchantCodeValidationView.as_view(), name='paiement_code'),
    path('profile/', UserProfileView.as_view(), name='profile'),
    path('transaction-history/', TransactionHistoryView.as_view(),name="transaction-history" ),
]
