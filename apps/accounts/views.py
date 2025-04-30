from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework import  status
from .serializer import InternalAccountSerializer
from apps.transactions.models import FeeRule

class CreateCommissionAccountView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = InternalAccountSerializer(data=request.data, context={'bank_db': request.source_bank_db})
        if serializer.is_valid():
            commission_account = serializer.save()
            return Response({"message": "Compte intern créé avec succès", "account_number": commission_account.account_number}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class FeeCalculatorAPI(APIView):
    def get_fee_from_db(self,bank_db, transaction_type, amount):
      rules = FeeRule.objects.using(bank_db).filter(
        transaction_type=transaction_type
       ).order_by('max_amount')

      for rule in rules:
        if amount <= rule.max_amount:
            return float(rule.fee_amount)

      return None 
    def post(self, request):
        #bank_db = getattr(request, 'bank_db')  
        bank_db = request.source_bank_db
        transaction_type = request.data.get('type')
        amount = request.data.get('montant')

        if not all([bank_db, transaction_type, amount]):
            return Response({'error': 'Paramètres manquants.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            amount = float(amount)
        except ValueError:
            return Response({'error': 'Format du montant invalide.'}, status=status.HTTP_400_BAD_REQUEST)

        fee = self.get_fee_from_db(bank_db, transaction_type, amount)

        if fee is not None:
            return Response({'fee': fee}, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Aucune règle de frais trouvée.'}, status=status.HTTP_404_NOT_FOUND)
    