from django.urls import path
from .views import CreateCommissionAccountView,FeeCalculatorAPI

urlpatterns = [
    path('create-commission/', CreateCommissionAccountView.as_view(), name='create-commission-account'),
    path('calculate_fee/', FeeCalculatorAPI.as_view(), name='calculate_fee'),
]