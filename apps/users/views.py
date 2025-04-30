from rest_framework import status
from rest_framework.response import Response 
from rest_framework.views import APIView
from .authentication import CustomTokenObtainPairSerializer
from .serializer import UserRegistrationSerializer,AddBusinessOrAgencyAccountSerializer,TransactionSerializer,AllAccountsSerializer,UserAccountSerializer,RegistrationAcounteAgancyBisenessSerializer,PhoneValidationSerializer,MerchantCodeValidationSerializer,PasswordValidationSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from .authentication import CustomJWTAuthentication

from rest_framework_simplejwt.views import TokenObtainPairView



class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer



class UserRegistrationView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = UserRegistrationSerializer(data=request.data, context={'bank_db': request.source_bank_db})
        if serializer.is_valid():
            user = serializer.save()
            return Response({"message": "Utilisateur enregistré avec succès"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class RegistrationAcounteAgancyBisenessView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = RegistrationAcounteAgancyBisenessSerializer(data=request.data, context={'bank_db': request.source_bank_db})
        if serializer.is_valid():
            user = serializer.save()
            return Response({"message": "Utilisateur enregistré avec succès"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AddBusinessOrAgencyAccountView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = AddBusinessOrAgencyAccountSerializer(
            data=request.data,
            context={'bank_db': request.source_bank_db}
        )
        if serializer.is_valid():
            account = serializer.save()
            return Response({
                "message": "Compte ajouté avec succès.",
              
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)    
# class CompteValidationView(APIView):
#     # permission_classes = [IsAuthenticated]
#     def post(self, request):
#         # Passer la base de données dans le contexte du sérialiseur
#         serializer = CompteValidationSerializer(data=request.data, context={'bank_db': request.destination_bank_db})
        
#         if serializer.is_valid():
#             # Si le compte est validé avec succès, renvoyer un message simple
#             return Response({
#                 "message": "Numéro de compte valide",
#             }, status=status.HTTP_200_OK)
        
      
#         return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class PhoneValidationView(APIView):
    #permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = PhoneValidationSerializer(data=request.data, context={'bank_db': request.source_bank_db})
        if serializer.is_valid():
            user = serializer.validated_data['user']
            return Response({
                "message": "Numéro de téléphone valide",
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class MerchantCodeValidationView(APIView):
    #permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = MerchantCodeValidationSerializer(data=request.data, context={'bank_db': request.source_bank_db})
        if serializer.is_valid():
            acounte = serializer.validated_data['user']
            return Response({
                "message": "code paiement valide",
                "phone_number": acounte.user.phone_number,
                "usernamme": acounte.user.username
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)    


class PasswordValidationView(APIView):
    authentication_classes = [CustomJWTAuthentication]  
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user  
      

        serializer = PasswordValidationSerializer(
            data=request.data, 
            context={'bank_db': request.source_bank_db, 'user': user}  
        )

        if serializer.is_valid():
            return Response({
                "message": "Mot de passe valide"
            }, status=status.HTTP_200_OK)

        return Response({
            "message": "Mot de passe invalide"
            
        }, status=status.HTTP_400_BAD_REQUEST)

class UserProfileView(APIView):
    #permission_classes = [IsAuthenticated]
    def post(self, request):
        serializer = UserAccountSerializer(data=request.data, context={'bank_db': request.source_bank_db})
        if serializer.is_valid():
            user_data = serializer.data
            return Response({
                "username": user_data['username'],
                "phone_number": user_data['phone_number'],
                "email": user_data['email'],
                "status": user_data['status'],
                "solde": user_data['solde'],
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)    


class TransactionHistoryView(APIView):
    def post(self, request):
        serializer = TransactionSerializer(data=request.data, context={'bank_db': request.source_bank_db})
        if serializer.is_valid():

            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class AllAccountsView(APIView):
    def get(self, request):
        serializer = AllAccountsSerializer( context={'bank_db': request.source_bank_db})
        return Response(serializer.to_representation(None), status=status.HTTP_200_OK)