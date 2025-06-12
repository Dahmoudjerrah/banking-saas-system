import requests
from django.conf import settings
from ..models import OTPVerification
import logging

logger = logging.getLogger(__name__)

class OTPService:
    def __init__(self):
        self.validation_key = settings.CHINGUISOFT_VALIDATION_KEY
        self.validation_token = settings.CHINGUISOFT_VALIDATION_TOKEN
        self.base_url = "https://chinguisoft.com/api/sms/validation"
    
    def send_otp(self, phone_number, lang='fr', db_alias='default'):
        """
        Envoie un OTP au numéro de téléphone
        """
        try:
            # Valider le format du numéro
            if not self._validate_phone_number(phone_number):
                return {'success': False, 'error': 'Format de numéro invalide'}
            
            # Supprimer les anciens OTP pour ce numéro
            OTPVerification.objects.using(db_alias).filter(
                phone_number=phone_number
            ).delete()
            
            # Générer un nouveau code OTP
            otp_code = OTPVerification.generate_otp()
            
            # Préparer la requête vers Chinguisoft
            url = f"{self.base_url}/{self.validation_key}"
            headers = {
                'Validation-token': self.validation_token,
                'Content-Type': 'application/json'
            }
            data = {
                'phone': phone_number,
                'lang': lang,
                'code': otp_code
            }
            
            # Envoyer la requête
            response = requests.post(url, headers=headers, json=data, timeout=10)
            
            if response.status_code == 200:
                # Sauvegarder l'OTP dans la base de données
                otp_verification = OTPVerification.objects.using(db_alias).create(
                    phone_number=phone_number,
                    otp_code=otp_code
                )
                
                response_data = response.json()
                logger.info(f"OTP envoyé avec succès pour {phone_number}")
                
                return {
                    'success': True,
                    'message': 'OTP envoyé avec succès',
                    'balance': response_data.get('balance', 0)
                }
            else:
                error_data = response.json()
                logger.error(f"Erreur lors de l'envoi OTP: {error_data}")
                return {
                    'success': False,
                    'error': self._handle_api_error(response.status_code, error_data)
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Erreur réseau lors de l'envoi OTP: {str(e)}")
            return {
                'success': False,
                'error': 'Erreur de connexion au service SMS'
            }
        except Exception as e:
            logger.error(f"Erreur inattendue lors de l'envoi OTP: {str(e)}")
            return {
                'success': False,
                'error': 'Erreur interne du serveur'
            }
    
    def verify_otp(self, phone_number, otp_code, db_alias='default'):
        """
        Vérifie le code OTP
        """
        try:
            # Nettoyer les OTP expirés
            OTPVerification.cleanup_expired(db_alias)
            
            # Récupérer l'OTP le plus récent pour ce numéro
            otp_verification = OTPVerification.objects.using(db_alias).filter(
                phone_number=phone_number,
                is_verified=False
            ).order_by('-created_at').first()
            
            if not otp_verification:
                return {
                    'success': False,
                    'error': 'Aucun OTP trouvé pour ce numéro'
                }
            
            if otp_verification.is_expired():
                return {
                    'success': False,
                    'error': 'Le code OTP a expiré'
                }
            
            if otp_verification.attempts >= 3:
                return {
                    'success': False,
                    'error': 'Trop de tentatives. Demandez un nouveau code.'
                }
            
            # Incrémenter le compteur de tentatives
            otp_verification.attempts += 1
            otp_verification.save(using=db_alias)
            
            if otp_verification.otp_code == otp_code:
                # Marquer comme vérifié
                otp_verification.is_verified = True
                otp_verification.save(using=db_alias)
                
                logger.info(f"OTP vérifié avec succès pour {phone_number}")
                return {
                    'success': True,
                    'message': 'Code OTP vérifié avec succès'
                }
            else:
                remaining_attempts = 3 - otp_verification.attempts
                return {
                    'success': False,
                    'error': f'Code OTP incorrect. {remaining_attempts} tentatives restantes.'
                }
                
        except Exception as e:
            logger.error(f"Erreur lors de la vérification OTP: {str(e)}")
            return {
                'success': False,
                'error': 'Erreur lors de la vérification'
            }
    
    def is_phone_verified(self, phone_number, db_alias='default'):
        """
        Vérifie si un numéro de téléphone a été vérifié récemment (dans les 10 dernières minutes)
        """
        from datetime import timedelta
        from django.utils import timezone
        
        recent_time = timezone.now() - timedelta(minutes=10)
        
        return OTPVerification.objects.using(db_alias).filter(
            phone_number=phone_number,
            is_verified=True,
            created_at__gte=recent_time
        ).exists()
    
    def _validate_phone_number(self, phone_number):
        """
        Valide le format du numéro de téléphone (doit commencer par 2, 3, ou 4 et contenir 8 chiffres)
        """
        if len(phone_number) != 8:
            return False
        
        if not phone_number.isdigit():
            return False
        
        if not phone_number[0] in ['2', '3', '4']:
            return False
        
        return True
    
    def _handle_api_error(self, status_code, error_data):
        """
        Gère les erreurs de l'API Chinguisoft
        """
        error_messages = {
            401: "Clés d'authentification invalides",
            402: "Solde insuffisant pour envoyer le SMS",
            422: "Données invalides",
            429: "Trop de requêtes, veuillez ralentir",
            503: "Service temporairement indisponible"
        }
        
        return error_messages.get(status_code, f"Erreur inconnue: {error_data}")
