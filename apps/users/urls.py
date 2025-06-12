from django.urls import path
from .views import UserRegistrationView,SendPasswordResetOTPView,ResetPasswordView,VerifyPasswordResetOTPView,SendOTPView,VerifyOTPView,AganceProfileView,TransactinBussnessView,ComercantProfileView,TransactinAganceView,TransactionHistoryView,AddBusinessOrAgencyAccountView,AllAccountsView,UserProfileView,CustomTokenObtainPairView,RegistrationAcounteAgancyBisenessView,MerchantCodeValidationView,PhoneValidationView,PasswordValidationView

urlpatterns = [
    path('register/', UserRegistrationView.as_view(), name='register'),
    path('send-otp/', SendOTPView.as_view(), name='send_otp'),
    path('verify-otp/', VerifyOTPView.as_view(), name='verify_otp'),

    path('send-reset-otp/', SendPasswordResetOTPView.as_view(), name='send_reset_otp'),
    path('verify-reset-otp/', VerifyPasswordResetOTPView.as_view(), name='verify_reset_otp'),
    path('reset-password/', ResetPasswordView.as_view(), name='reset_password'),

    
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
    path('comercant/profile/', ComercantProfileView.as_view(), name='profile'),
    path('agance/profile/', AganceProfileView.as_view(), name='profile'),
    path('transaction-history/', TransactionHistoryView.as_view(),name="transaction-history" ),
    path('transaction-agance/', TransactinAganceView.as_view(),name="transaction-history" ),
    path('transaction-comercant/', TransactinBussnessView.as_view(),name="transaction-history" )
]
