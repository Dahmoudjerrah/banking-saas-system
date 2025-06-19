from rest_framework import status,serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import PreTransaction
from .models import PaymentRequest
from apps.accounts.models import BusinessAccount
from apps.users.models import User
from decimal import Decimal
from rest_framework.permissions import IsAuthenticated

from datetime import timedelta
from django.utils import timezone
from .serializer import TransferTransactionSerializer,RechargeAgencySerializer,AllPreTransactionsSerializer,RetraitMarchantSerializer,MerchantPaymentSerializer,DepositTransactionSerializer,PreTransactionRetrieveSerializer,RetraitTransactionSerializer,PreTransactionSerializer
#from rest_framework.permissions import IsAuthenticated
#from apps.users.serializer import CustomJWTAuthentication


class TransferTransactionView(APIView):
    #authentication_classes = [CustomJWTAuthentication]
    #permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        serializer = TransferTransactionSerializer(data=request.data, context={'bank_db': request.source_bank_db})
        if serializer.is_valid():
            try:
                transaction = serializer.save()
                
                response_data = {
                    "message": "transfert réussie",
                    "transaction_id": transaction.id,
                    "date": transaction.date,
                    "amount": float(transaction.amount),
                    "destination_account": transaction.destination_account.user.phone_number
                }
                    
                return Response(response_data, status=status.HTTP_201_CREATED)
            except serializers.ValidationError as e:
                return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class DepositTransactionView(APIView):
    def post(self, request, *args, **kwargs):

        serializer = DepositTransactionSerializer(data=request.data, context={'bank_db': request.source_bank_db})
        if serializer.is_valid():
            transaction = serializer.save()
            destination_user = transaction.destination_account.user
            return Response({"message": "dépôt réussie",
                             "client  ": f"{destination_user.username}"
                             }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
  
class RetraiTransactionView(APIView):
      def post(self, request, *args, **kwargs):
        serializer = RetraitTransactionSerializer(data=request.data, context={'bank_db': request.source_bank_db})
        if serializer.is_valid():
            transaction = serializer.save()
            return Response({"message": "retrai réussie"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RetraiMarchantView(APIView):
      def post(self, request, *args, **kwargs):
        serializer = RetraitMarchantSerializer(data=request.data, context={'bank_db': request.source_bank_db})
        if serializer.is_valid():
            transaction = serializer.save()
            return Response({"message": "retrai réussie"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class MerchantPaymentView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = MerchantPaymentSerializer(data=request.data, context={'bank_db': request.source_bank_db})
        if serializer.is_valid():
            serializer.save()
            return Response({'message': 'Paiement marchand effectué avec succès'}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CreatePreTransactionView(APIView):
    # permission_classes = [IsAuthenticated]
    def post(self, request):
      #  purge_expired_pretransactions(request.source_bank_db)
        serializer = PreTransactionSerializer(data=request.data, context={'bank_db': request.source_bank_db})
        if serializer.is_valid():
            pre_transaction = serializer.save()  
            created_at_formatted = pre_transaction.created_at.strftime('%Y-%m-%d %H:%M:%S')
            return Response({
                "message": "Pré-transaction créée avec succès",
                "Trs_ID": pre_transaction.id,
                "code": pre_transaction.code,
                "montent": pre_transaction.amount,
                "Date_et_heure": created_at_formatted
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class RetrievePreTransactionView(APIView):
    def post(self, request):
        bank_db = request.source_bank_db
        serializer = PreTransactionRetrieveSerializer(data=request.data)
        
        if serializer.is_valid():
            client_phone = serializer.validated_data['client_phone']
            code = serializer.validated_data['code']
            
            
            try:
                pre_transaction = PreTransaction.objects.using(bank_db).get(
                    client_phone=client_phone,
                    code=code,
                
                )
                created_at_formatted = pre_transaction.created_at.strftime('%Y-%m-%d %H:%M:%S')
                response_data = {
                    "Trs_ID": pre_transaction.id,
                    "code": pre_transaction.code,
                    "telephone": pre_transaction.client_phone,
                    "montent": pre_transaction.amount,
                    "Date_et_heure": created_at_formatted
                }
                return Response(response_data, status=status.HTTP_200_OK)
            except PreTransaction.DoesNotExist:
                return Response({"error": "Pré-transaction introuvable."}, status=status.HTTP_404_NOT_FOUND)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST) 
    

class CancelPreTransactionView(APIView):
    def delete(self, request,code):
        bank_db = request.source_bank_db
        try:
            pre_transaction = PreTransaction.objects.using(bank_db).get(code=code)
            pre_transaction.delete(using=bank_db)
            return Response({"message": "Pré-transaction annulée avec succès."}, status=status.HTTP_200_OK)
        except PreTransaction.DoesNotExist:
            return Response({"error": "Pré-transaction introuvable."}, status=status.HTTP_404_NOT_FOUND) 
        
# def purge_expired_pretransactions(bank_db):
#     expiry_time = timezone.now() - timedelta(minutes=1)
    
#     expired_items = PreTransaction.objects.using(bank_db).filter(created_at__lt=expiry_time)
    
#     for item in expired_items:
#         item.delete(using=bank_db)
              
class CreatePaymentRequestView(APIView):
    def post(self, request):
        bank_db = request.source_bank_db 
        try:
            # Récupération des données
            montant = request.data.get("montant") 
            client_phone = request.data.get("client_phone")
            
            # Validation de l'utilisateur
            try:
                user = User.objects.using(bank_db).get(phone_number=client_phone)
            except User.DoesNotExist:
                return Response({
                    "error": f"Utilisateur client avec le numéro {client_phone} introuvable."
                }, status=400)

            # Validation du montant
            if not montant:
                return Response({"error": "Le montant est requis."}, status=400)

            try:
                montant = Decimal(montant)
                if montant <= 0:
                    return Response({"error": "Le montant doit être positif."}, status=400)
            except:
                return Response({"error": "Montant invalide."}, status=400)

            # Récupération du compte business avec le nouveau modèle
            try:
                merchant_account = BusinessAccount.objects.using(bank_db).get(user=user)
            except BusinessAccount.DoesNotExist:
                return Response({"error": "Compte commerçant introuvable."}, status=400)

            # Création de la demande de paiement
            payment_request = PaymentRequest.objects.using(bank_db).create(
                merchant=merchant_account,
                amount=montant
            )

            return Response({
                "message": "Demande de paiement créée.",
                "code": str(payment_request.code),
                "amount": float(payment_request.amount),
                "status": payment_request.status
            }, status=201)

        except Exception as e:
            return Response({"error": str(e)}, status=500)

class RetrievePaymentRequestView(APIView):
    def get(self, request, code):
        try:
            bank_db = request.source_bank_db
            payment_request = PaymentRequest.objects.using(bank_db).filter(code=code).first()

            if not payment_request:
                return Response({"error": "Demande introuvable."}, status=404)

            return Response({
                "amount": float(payment_request.amount),
                "merchant": {
                    "name": payment_request.merchant.user.username,
                    "phone": payment_request.merchant.user.phone_number,
                    "comersasnt_code":payment_request.merchant.code
                },
                "status": payment_request.status,
                "code": str(payment_request.code)
            })

        except Exception as e:
            return Response({"error": str(e)}, status=500)        


class RetrieveAllPreTransactionsView(APIView):
    def post(self, request):
      
        bank_db = request.source_bank_db
        serializer = AllPreTransactionsSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
              
                pre_transactions = PreTransaction.objects.using(bank_db).all()
                if not pre_transactions.exists():
                    return Response({"message": "Aucune pré-transaction trouvée dans la base de données."},
                                  status=status.HTTP_404_NOT_FOUND)
                
              
                response_data = []
                for transaction in pre_transactions:
                    created_at_formatted = transaction.created_at.strftime('%Y-%m-%d %H:%M:%S')
                    transaction_data = {
                        "Trs_ID": transaction.id,
                        "code": transaction.code,
                        "telephone": transaction.client_phone,
                        "montant": transaction.amount,
                        "Date_et_heure": created_at_formatted
                    }
                    response_data.append(transaction_data)
                
                return Response(response_data, status=status.HTTP_200_OK)
                
            except Exception as e:
                return Response({"error": f"Une erreur s'est produite: {str(e)}"},
                              status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class RechargeAgancyView(APIView):
      def post(self, request, *args, **kwargs):
        serializer = RechargeAgencySerializer(data=request.data, context={'bank_db': request.source_bank_db})
        if serializer.is_valid():
            transaction = serializer.save()
            return Response({"message": "recharge succes"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)    