from django.urls import path

from .views import TransferTransactionView,RetraiMarchantView,RetrievePaymentRequestView,CreatePaymentRequestView,MerchantPaymentView,CancelPreTransactionView,DepositTransactionView,RetraiTransactionView,CreatePreTransactionView,RetrievePreTransactionView
urlpatterns = [
    path('transactions/depose/', DepositTransactionView.as_view(), name='transaction-create'),
    path('transactions/retrai/', RetraiTransactionView.as_view(), name='transaction-retrai'),
    path('transactions/retrai/marchant', RetraiMarchantView.as_view(), name='retrai-marchant'),
    path('pre-transaction/', CreatePreTransactionView.as_view(), name='pre-transaction'),
    path('cancel-pretransaction/<str:code>/', CancelPreTransactionView.as_view(), name='cancel-pretransaction'),
    path('pretransaction/retrieve/', RetrievePreTransactionView.as_view(), name='retrieve-pretransaction'),
    path('transactions/transfair/', TransferTransactionView.as_view(), name='transaction-transfair'),
    path('transactions/paiement/merchant', MerchantPaymentView.as_view(), name='paiement'),
    path("payment-request/create/", CreatePaymentRequestView.as_view(), name="create-payment-request"),
    path("payment-request/<uuid:code>/", RetrievePaymentRequestView.as_view(), name="retrieve-payment-request"),
    #path('transfer_enter_bank/', TransferEnterBankView.as_view(), name='transfer_enter_bank'),
    
]
