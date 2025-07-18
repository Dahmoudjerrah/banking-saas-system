from rest_framework import status
from rest_framework.response import Response 
from rest_framework.views import APIView
from .authentication import CustomTokenObtainPairSerializer
from .serializer import UserRegistrationSerializer,AganceAccountSerializer,TransactionBusinessSerialiser,ComercantAccountSerializer,TransactionAganceSerialiser,AddBusinessOrAgencyAccountSerializer,TransactionSerializer,UserAccountSerializer,RegistrationAcounteAgancyBisenessSerializer,PhoneValidationSerializer,MerchantCodeValidationSerializer,PasswordValidationSerializer
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView
from .authentication import CustomJWTAuthentication
from apps.transactions.services.otp_service import OTPService
from django.db import IntegrityError
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from apps.transactions.services.password_reset_otp_service import PasswordResetOTPService
import logging
from apps.transactions.permissions import BusinessAccountPermission,AgencyOrBusinessPermission,AgencyAccountPermission,PersonnelAccountPermission,AllAccountTypesPermission
from django.utils import timezone
from apps.transactions.models import PasswordResetOTP
from apps.users.models import User

logger = logging.getLogger(__name__)

@method_decorator(csrf_exempt, name='dispatch')
class SendPasswordResetOTPView(APIView):
    """
    Envoie un OTP pour la réinitialisation de mot de passe
    Adapté pour la nouvelle conception avec relation User
    """
    
    def post(self, request, *args, **kwargs):
        logger.info(f"SendPasswordResetOTPView - Données reçues: {request.data}")
        logger.info(f"Headers: X-Source-Bank-Code={request.META.get('HTTP_X_SOURCE_BANK_CODE')}")
        
        phone_number = request.data.get('phone_number')
        lang = request.data.get('lang', 'fr')
        
        if not phone_number:
            logger.error("Numéro de téléphone manquant")
            return Response(
                {'error': 'Le numéro de téléphone est requis'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Récupérer la base de données depuis l'en-tête - OBLIGATOIRE
        bank_db = getattr(request, 'source_bank_db', None)
        
        if not bank_db:
            logger.error("En-tête X-Source-Bank-Code manquant ou invalide")
            return Response(
                {'error': 'En-tête X-Source-Bank-Code requis'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        logger.info(f"Utilisation de la base de données: {bank_db}")
        
        try:
            # Initialiser le service OTP avec la nouvelle conception
            otp_service = PasswordResetOTPService()
            result = otp_service.send_reset_otp(phone_number, lang, bank_db)
            
            logger.info(f"Résultat envoi OTP reset: {result}")
            
            if result['success']:
                # Réponse enrichie avec informations utilisateur si disponible
                response_data = {
                    'message': result['message']
                }
                
                # Ajouter des informations supplémentaires en mode dev
                if result.get('dev_mode'):
                    response_data['dev_mode'] = True
                    response_data['balance'] = result.get('balance', 0)
                
                return Response(response_data, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'error': result['error']}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi OTP reset: {str(e)}")
            return Response(
                {'error': f'Erreur serveur: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

@method_decorator(csrf_exempt, name='dispatch')
class VerifyPasswordResetOTPView(APIView):
    """
    Vérifie l'OTP de réinitialisation et génère un token de reset
    Adapté pour la nouvelle conception avec relation User
    """
    
    def post(self, request, *args, **kwargs):
        logger.info(f"VerifyPasswordResetOTPView - Données reçues: {request.data}")
        logger.info(f"Headers: X-Source-Bank-Code={request.META.get('HTTP_X_SOURCE_BANK_CODE')}")
        
        phone_number = request.data.get('phone_number')
        otp_code = request.data.get('otp_code')
        
        if not phone_number or not otp_code:
            logger.error("Numéro de téléphone ou code OTP manquant")
            return Response(
                {'error': 'Le numéro de téléphone et le code OTP sont requis'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Récupérer la base de données depuis l'en-tête - OBLIGATOIRE
        bank_db = getattr(request, 'source_bank_db', None)
        
        if not bank_db:
            logger.error("En-tête X-Source-Bank-Code manquant ou invalide")
            return Response(
                {'error': 'En-tête X-Source-Bank-Code requis'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        logger.info(f"Utilisation de la base de données: {bank_db}")
        
        try:
            # Initialiser le service OTP avec la nouvelle conception
            otp_service = PasswordResetOTPService()
            result = otp_service.verify_reset_otp(phone_number, otp_code, bank_db)
            
            logger.info(f"Résultat vérification OTP reset: {result}")
            
            if result['success']:
                response_data = {
                    'message': result['message'],
                    'verified': result['verified'],
                    'reset_token': result['reset_token']
                }
                
                # Ajouter l'ID utilisateur si disponible (utile pour le frontend)
                if 'user_id' in result:
                    response_data['user_id'] = result['user_id']
                
                return Response(response_data, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'error': result['error'], 'verified': result['verified']}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Erreur lors de la vérification OTP reset: {str(e)}")
            return Response(
                {'error': f'Erreur serveur: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

@method_decorator(csrf_exempt, name='dispatch')
class ResetPasswordView(APIView):
  
    
    def post(self, request, *args, **kwargs):
        logger.info(f"ResetPasswordView - Données reçues: {request.data}")
        logger.info(f"Headers: X-Source-Bank-Code={request.META.get('HTTP_X_SOURCE_BANK_CODE')}")
        
        phone_number = request.data.get('phone_number')
        new_password = request.data.get('new_password')
        reset_token = request.data.get('reset_token')
        
        if not all([phone_number, new_password, reset_token]):
            logger.error("Données manquantes pour la réinitialisation")
            return Response(
                {'error': 'Numéro de téléphone, nouveau mot de passe et token requis'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validation du mot de passe (5 chiffres)
        if not new_password.isdigit() or len(new_password) != 5:
            return Response(
                {'error': 'Le mot de passe doit contenir exactement 5 chiffres'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Récupérer la base de données depuis l'en-tête - OBLIGATOIRE
        bank_db = getattr(request, 'source_bank_db', None)
        
        if not bank_db:
            logger.error("En-tête X-Source-Bank-Code manquant ou invalide")
            return Response(
                {'error': 'En-tête X-Source-Bank-Code requis'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        logger.info(f"Utilisation de la base de données: {bank_db}")
        
        try:
            # Initialiser le service OTP avec la nouvelle conception
            otp_service = PasswordResetOTPService()
            result = otp_service.reset_password(phone_number, new_password, reset_token, bank_db)
            
            logger.info(f"Résultat réinitialisation password: {result}")
            
            if result['success']:
                response_data = {
                    'message': result['message']
                }
                
                # Ajouter des informations supplémentaires si disponibles
                if 'user_id' in result:
                    response_data['user_id'] = result['user_id']
                if 'reset_timestamp' in result:
                    response_data['reset_timestamp'] = result['reset_timestamp']
                
                return Response(response_data, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'error': result['error']}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
                
        except Exception as e:
            logger.error(f"Erreur lors de la réinitialisation: {str(e)}")
            return Response(
                {'error': f'Erreur serveur: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

# Vue utilitaire pour nettoyer les anciens OTP - Adaptée à la nouvelle conception
@method_decorator(csrf_exempt, name='dispatch')
class CleanupExpiredOTPView(APIView):
    """
    Nettoie les OTP expirés de la base spécifiée
    Adapté pour la nouvelle conception avec relation User
    """
    
    def post(self, request, *args, **kwargs):
        logger.info(f"CleanupExpiredOTPView - Nettoyage demandé")
        logger.info(f"Headers: X-Source-Bank-Code={request.META.get('HTTP_X_SOURCE_BANK_CODE')}")
        
        # Récupérer la base de données depuis l'en-tête
        bank_db = getattr(request, 'source_bank_db', None)
        
        if not bank_db:
            logger.error("En-tête X-Source-Bank-Code manquant pour le nettoyage")
            return Response(
                {'error': 'En-tête X-Source-Bank-Code requis'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        logger.info(f"Nettoyage de la base de données: {bank_db}")
        
        try:
            
            
            # Compter d'abord les OTP expirés
            expired_count = PasswordResetOTP.objects.using(bank_db).filter(
                expires_at__lt=timezone.now()
            ).count()
            
            logger.info(f"Trouvé {expired_count} OTP expirés dans la base {bank_db}")
            
            # Supprimer tous les OTP expirés de la base spécifiée
            deleted_count = PasswordResetOTP.objects.using(bank_db).filter(
                expires_at__lt=timezone.now()
            ).delete()[0]
            
            logger.info(f" Supprimé {deleted_count} OTP expirés de la base {bank_db}")
            
            # Optionnel: nettoyer aussi les OTP utilisés plus anciens que 24h
            old_used_count = PasswordResetOTP.objects.using(bank_db).filter(
                is_used=True,
                created_at__lt=timezone.now() - timezone.timedelta(hours=24)
            ).delete()[0]
            
            if old_used_count > 0:
                logger.info(f"Supprimé {old_used_count} anciens OTP utilisés de la base {bank_db}")
            
            total_cleaned = deleted_count + old_used_count
            
            return Response({
                'message': f'Nettoyage terminé: {deleted_count} OTP expirés et {old_used_count} anciens OTP utilisés supprimés',
                'expired_deleted': deleted_count,
                'old_used_deleted': old_used_count,
                'total_cleaned': total_cleaned,
                'database': bank_db
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f" Erreur lors du nettoyage de la base {bank_db}: {str(e)}")
            return Response(
                {'error': f'Erreur serveur lors du nettoyage: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def get(self, request, *args, **kwargs):
        """
        Méthode GET pour obtenir des statistiques sur les OTP sans les supprimer
        Adaptée à la nouvelle conception avec relation User
        """
        logger.info(f"CleanupExpiredOTPView - Statistiques demandées")
        
        # Récupérer la base de données depuis l'en-tête
        bank_db = getattr(request, 'source_bank_db', None)
        
        if not bank_db:
            return Response(
                {'error': 'En-tête X-Source-Bank-Code requis'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            
            
            # Statistiques des OTP avec informations utilisateur
            total_otps = PasswordResetOTP.objects.using(bank_db).count()
            expired_otps = PasswordResetOTP.objects.using(bank_db).filter(
                expires_at__lt=timezone.now()
            ).count()
            verified_otps = PasswordResetOTP.objects.using(bank_db).filter(
                is_verified=True
            ).count()
            used_otps = PasswordResetOTP.objects.using(bank_db).filter(
                is_used=True
            ).count()
            pending_otps = PasswordResetOTP.objects.using(bank_db).filter(
                is_verified=False,
                is_used=False,
                expires_at__gte=timezone.now()
            ).count()
            
            # Statistiques utilisateur avec OTP actifs
            users_with_active_otps = PasswordResetOTP.objects.using(bank_db).filter(
                is_verified=False,
                is_used=False,
                expires_at__gte=timezone.now()
            ).values_list('user_id', flat=True).distinct().count()
            
            # Statistiques sur les tentatives
            high_attempts_otps = PasswordResetOTP.objects.using(bank_db).filter(
                attempts__gte=2
            ).count()
            
            return Response({
                'database': bank_db,
                'statistics': {
                    'total_otps': total_otps,
                    'expired_otps': expired_otps,
                    'verified_otps': verified_otps,
                    'used_otps': used_otps,
                    'pending_otps': pending_otps,
                    'users_with_active_otps': users_with_active_otps,
                    'high_attempts_otps': high_attempts_otps
                },
                'message': f'Statistiques pour la base {bank_db} (nouvelle conception avec User)'
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des statistiques {bank_db}: {str(e)}")
            return Response(
                {'error': f'Erreur serveur: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

#//////////////////////////////////////////////

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer

logger = logging.getLogger(__name__)

class SendOTPView(APIView):
    def post(self, request, *args, **kwargs):
        phone_number = request.data.get('phone_number')
        lang = request.data.get('lang', 'fr')  # Par défaut français
        
        if not phone_number:
            return Response(
                {'error': 'Le numéro de téléphone est requis'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Valider le format du numéro
        if len(phone_number) != 8 or not phone_number.isdigit() or phone_number[0] not in ['2', '3', '4']:
            return Response(
                {'error': 'Format de numéro invalide. Le numéro doit commencer par 2, 3 ou 4 et contenir 8 chiffres.'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        otp_service = OTPService()
        result = otp_service.send_otp(phone_number, lang, request.source_bank_db)
        
        if result['success']:
            return Response({
                'message': result['message'],
                'balance': result.get('balance')
            }, status=status.HTTP_200_OK)
        else:
            return Response(
                {'error': result['error']}, 
                status=status.HTTP_400_BAD_REQUEST
            )

class VerifyOTPView(APIView):
    def post(self, request, *args, **kwargs):
      #  logger.info(f"VerifyOTPView - Données reçues: {request.data}")
        
        phone_number = request.data.get('phone_number')
        otp_code = request.data.get('otp_code')
        
        logger.info(f"Vérification OTP pour téléphone: {phone_number}, code: {otp_code}")
        
        if not phone_number or not otp_code:
          #  logger.error("Numéro de téléphone ou code OTP manquant")
            return Response(
                {'error': 'Le numéro de téléphone et le code OTP sont requis'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            otp_service = OTPService()
            result = otp_service.verify_otp(phone_number, otp_code, request.source_bank_db)
            
            #logger.info(f"Résultat vérification OTP: {result}")
            
            if result['success']:
                return Response({
                    'message': result['message'],
                    'verified': True
                }, status=status.HTTP_200_OK)
            else:
                return Response(
                    {'error': result['error'], 'verified': False}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
        except Exception as e:
          #  logger.error(f"Erreur lors de la vérification OTP: {str(e)}")
            return Response(
                {'error': f'Erreur serveur: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class UserRegistrationView(APIView):
    def post(self, request, *args, **kwargs):
        logger.info(f"UserRegistrationView - Données reçues: {request.data}")
        logger.info(f"bank_db: {request.source_bank_db}")
        
        phone_number = request.data.get('phone_number')
        
        if not phone_number:
            return Response(
                {'error': 'Le numéro de téléphone est requis'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Vérifier si le numéro a été vérifié
        otp_service = OTPService()
        if not otp_service.is_phone_verified(phone_number, request.source_bank_db):
            logger.error(f"Numéro {phone_number} non vérifié")
            return Response(
                {'error': 'Veuillez d\'abord vérifier votre numéro de téléphone avec le code OTP'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        logger.info(f"Numéro {phone_number} vérifié, procédure d'enregistrement...")
        
        # Procéder à l'enregistrement
        serializer = UserRegistrationSerializer(
            data=request.data, 
            context={'bank_db': request.source_bank_db}
        )
        
        if serializer.is_valid():
            try:
                user = serializer.save()
              #  logger.info(f"Utilisateur {user.username} créé avec succès")
                return Response(
                    {"message": "Utilisateur enregistré avec succès"}, 
                    status=status.HTTP_201_CREATED
                )
            except Exception as e:
              #  logger.error(f"Erreur lors de la création utilisateur: {str(e)}")
                return Response(
                    {'error': f'Erreur lors de l\'enregistrement: {str(e)}'}, 
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        #logger.error(f"Erreurs de validation: {serializer.errors}")
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
    permission_classes = [IsAuthenticated,PersonnelAccountPermission]
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
    
class ComercantProfileView(APIView):
    #permission_classes = [IsAuthenticated]
    permission_classes = [IsAuthenticated,BusinessAccountPermission]
    def post(self, request):
        serializer = ComercantAccountSerializer(data=request.data, context={'bank_db': request.source_bank_db})
        if serializer.is_valid():
            user_data = serializer.data
            return Response({
                "username": user_data['username'],
                "phone_number": user_data['phone_number'],
                "email": user_data['email'],
                "status": user_data['status'],
                "solde": user_data['solde'],
                "code":user_data['code'],
                "tax":user_data['tax'],
                "registration":user_data['registration']
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST) 

class AganceProfileView(APIView):
    #permission_classes = [IsAuthenticated]
    permission_classes = [IsAuthenticated,AgencyAccountPermission]
    def post(self, request):
        serializer = AganceAccountSerializer(data=request.data, context={'bank_db': request.source_bank_db})
        if serializer.is_valid():
            user_data = serializer.data
            return Response({
                "username": user_data['username'],
                "phone_number": user_data['phone_number'],
                "email": user_data['email'],
                "status": user_data['status'],
                "solde": user_data['solde'],
                "code":user_data['code'],
                "tax":user_data['tax'],
                "registration":user_data['registration']
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)       


class TransactionHistoryView(APIView):
    permission_classes = [IsAuthenticated,PersonnelAccountPermission]
    def post(self, request):
        serializer = TransactionSerializer(data=request.data, context={'bank_db': request.source_bank_db})
        if serializer.is_valid():

            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# class AllAccountsView(APIView):
#     def get(self, request):
#         serializer = AllAccountsSerializer( context={'bank_db': request.source_bank_db})
#         return Response(serializer.to_representation(None), status=status.HTTP_200_OK)

class TransactinAganceView(APIView):
    permission_classes = [IsAuthenticated,AgencyAccountPermission]
    def post(self, request):
        serializer = TransactionAganceSerialiser(data=request.data, context={'bank_db': request.source_bank_db})
        if serializer.is_valid():

            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST) 

class TransactinBussnessView(APIView):
    permission_classes = [IsAuthenticated,BusinessAccountPermission]
    def post(self, request):
        serializer = TransactionBusinessSerialiser(data=request.data, context={'bank_db': request.source_bank_db})
        if serializer.is_valid():

            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)           