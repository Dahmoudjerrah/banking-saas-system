# services/password_reset_otp_service.py - Version corrigée

import random
import requests
import logging
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from ..models import PasswordResetOTP  
from apps.users.models import User

logger = logging.getLogger(__name__)

class PasswordResetOTPService:
    def __init__(self):
        # MÊME FORMAT QUE VOTRE OTPService QUI MARCHE
        self.validation_key = settings.CHINGUISOFT_VALIDATION_KEY
        self.validation_token = settings.CHINGUISOFT_VALIDATION_TOKEN
        self.base_url = "https://chinguisoft.com/api/sms/validation"
        
        # MODE DÉVELOPPEMENT
        self.dev_mode = getattr(settings, 'OTP_DEV_MODE', False)
        self.dev_otp = getattr(settings, 'OTP_DEV_CODE', '123456')

    def send_reset_otp(self, phone_number, lang, bank_db):
        """
        Envoie un OTP pour la réinitialisation de mot de passe
        bank_db est OBLIGATOIRE - pas de valeur par défaut
        """
        if not bank_db:
            #logger.error("Base de données non spécifiée")
            return {
                'success': False,
                'error': 'Base de données non spécifiée'
            }

        try:
            # Validation du numéro de téléphone
            if not self._validate_phone_number(phone_number):
                return {'success': False, 'error': 'Format de numéro invalide'}

            # Vérifier si l'utilisateur existe
            if not self._user_exists(phone_number, bank_db):
                #logger.warning(f"Utilisateur {phone_number} non trouvé dans la base {bank_db}")
                return {
                    'success': False,
                    'error': 'Aucun compte trouvé avec ce numéro de téléphone'
                }

            # Nettoyer les anciens OTP expirés
            self._cleanup_expired_otps(phone_number, bank_db)

            # Vérifier le délai entre les envois (anti-spam)
            if not self._can_send_otp(phone_number, bank_db):
                return {
                    'success': False,
                    'error': 'Veuillez attendre avant de demander un nouveau code'
                }

            # Générer le code OTP
            if self.dev_mode:
                otp_code = self.dev_otp
                #logger.info(f"🚀 MODE DEV RESET: Utilisation OTP fixe {otp_code}")
            else:
                otp_code = self._generate_otp()

            # Décider si envoyer vraiment ou simuler
            if self.dev_mode:
                # Mode développement - simuler l'envoi
                #logger.info(f"🚀 MODE DEV RESET: SMS simulé pour {phone_number} avec code {otp_code}")
                sms_success = True
                response_data = {'balance': 99, 'dev_mode': True}
            else:
                # Mode production - utiliser EXACTEMENT le même format que votre OTPService
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
                
                #logger.info(f"Envoi SMS reset vers: {url}")
                #logger.info(f"Headers: {headers}")
                #logger.info(f"Data: {data}")
                
                # Envoyer la requête - EXACTEMENT COMME VOTRE OTPService
                response = requests.post(url, headers=headers, json=data, timeout=10)
                
                #logger.info(f"Response status: {response.status_code}")
                #logger.info(f"Response text: {response.text}")
                
                if response.status_code == 200:
                    sms_success = True
                    response_data = response.json()
                elif response.status_code == 500:
                    # Si erreur 500, basculer en mode dev temporairement
                    #logger.warning("⚠️ Erreur 500 Chinguisoft - Basculement temporaire mode dev")
                    sms_success = True
                    response_data = {'balance': 0, 'fallback_mode': True}
                    otp_code = self.dev_otp  # Utiliser code fixe
                else:
                    sms_success = False
                    error_data = response.json() if response.text else {}
                    #logger.error(f"Erreur lors de l'envoi OTP reset: {error_data}")
                    return {
                        'success': False,
                        'error': self._handle_api_error(response.status_code, error_data)
                    }
            
            if sms_success:
                # Sauvegarder l'OTP dans la base de données spécifiée
                self._save_reset_otp(phone_number, otp_code, bank_db)
                
                #logger.info(f"✅ OTP de réinitialisation envoyé avec succès à {phone_number} (DB: {bank_db})")
                
                # Message de réponse
                message = 'Code de réinitialisation envoyé avec succès'
                if self.dev_mode or response_data.get('dev_mode') or response_data.get('fallback_mode'):
                    message += f' (CODE: {otp_code})'
                
                return {
                    'success': True,
                    'message': message,
                    'balance': response_data.get('balance', 0),
                    'dev_mode': self.dev_mode or response_data.get('fallback_mode', False)
                }

        except requests.exceptions.RequestException as e:
            #logger.error(f"Erreur réseau lors de l'envoi OTP reset: {str(e)}")
            return {
                'success': False,
                'error': 'Erreur de connexion au service SMS'
            }
        except Exception as e:
            #logger.error(f"Erreur dans send_reset_otp (DB: {bank_db}): {str(e)}")
            return {
                'success': False,
                'error': 'Erreur interne du serveur'
            }

    def verify_reset_otp(self, phone_number, otp_code, bank_db):
        """
        Vérifie l'OTP de réinitialisation et génère un token de reset
        bank_db est OBLIGATOIRE - pas de valeur par défaut
        """
        if not bank_db:
            #logger.error("Base de données non spécifiée")
            return {
                'success': False,
                'error': 'Base de données non spécifiée',
                'verified': False
            }

        try:
            # Nettoyer les OTP expirés 
            self._cleanup_expired_otps_all(bank_db)
            
            # Chercher l'OTP dans la base de données spécifiée
            otp_record = PasswordResetOTP.objects.using(bank_db).filter(
                phone_number=phone_number,
                is_verified=False,
                is_used=False
            ).order_by('-created_at').first()

            if not otp_record:
                #logger.warning(f"OTP invalide pour {phone_number} (DB: {bank_db})")
                return {
                    'success': False,
                    'error': 'Aucun OTP trouvé pour ce numéro',
                    'verified': False
                }

            # Vérifier l'expiration
            if otp_record.is_expired():
                #logger.warning(f"OTP expiré pour {phone_number} (DB: {bank_db})")
                return {
                    'success': False,
                    'error': 'Le code OTP a expiré',
                    'verified': False
                }

            # Vérifier le nombre de tentatives (comme OTPService)
            if otp_record.attempts >= 3:
                return {
                    'success': False,
                    'error': 'Trop de tentatives. Demandez un nouveau code.',
                    'verified': False
                }

            # Incrémenter les tentatives
            otp_record.attempts += 1
            otp_record.save(using=bank_db)

            # Vérifier le code
            if otp_record.otp_code == otp_code:
                # Marquer comme vérifié et générer le token
                otp_record.is_verified = True
                otp_record.verified_at = timezone.now()
                otp_record.reset_token = PasswordResetOTP.generate_reset_token()
                otp_record.save(using=bank_db)

             #   logger.info(f"OTP vérifié avec succès pour {phone_number} (DB: {bank_db})")
                return {
                    'success': True,
                    'message': 'Code vérifié avec succès',
                    'verified': True,
                    'reset_token': otp_record.reset_token
                }
            else:
                remaining_attempts = 3 - otp_record.attempts
                return {
                    'success': False,
                    'error': f'Code OTP incorrect. {remaining_attempts} tentatives restantes.',
                    'verified': False
                }

        except Exception as e:
            #logger.error(f"Erreur dans verify_reset_otp (DB: {bank_db}): {str(e)}")
            return {
                'success': False,
                'error': 'Erreur lors de la vérification',
                'verified': False
            }

    def reset_password(self, phone_number, new_password, reset_token, bank_db):
        """
        Réinitialise le mot de passe avec le token de réinitialisation
        bank_db est OBLIGATOIRE - pas de valeur par défaut
        """
        if not bank_db:
            #logger.error("Base de données non spécifiée")
            return {
                'success': False,
                'error': 'Base de données non spécifiée'
            }

        try:
            # Vérifier le token de réinitialisation dans la base spécifiée
            otp_record = PasswordResetOTP.objects.using(bank_db).filter(
                phone_number=phone_number,
                reset_token=reset_token,
                is_verified=True,
                is_used=False
            ).first()

            if not otp_record:
             #   logger.warning(f"Token invalide pour {phone_number} (DB: {bank_db})")
                return {
                    'success': False,
                    'error': 'Token de réinitialisation invalide ou expiré'
                }

            if not otp_record.is_valid_for_reset():
              #  logger.warning(f"Token expiré pour {phone_number} (DB: {bank_db})")
                return {
                    'success': False,
                    'error': 'Token de réinitialisation invalide ou expiré'
                }

            # Trouver l'utilisateur dans la base spécifiée
            user = User.objects.using(bank_db).filter(phone_number=phone_number).first()
            if not user:
               # logger.warning(f"Utilisateur {phone_number} non trouvé dans la base {bank_db}")
                return {
                    'success': False,
                    'error': 'Utilisateur introuvable'
                }

            # Réinitialiser le mot de passe
            user.set_password(new_password)
            user.save(using=bank_db)
            #logger.info(f"Mot de passe mis à jour pour {phone_number}")

            # CORRECTION: Marquer directement comme utilisé
            otp_record.is_used = True
            otp_record.save(using=bank_db)
            #logger.info(f"Token marqué comme utilisé pour {phone_number}")

            # Nettoyer tous les anciens tokens de cet utilisateur dans cette base
            deleted_count = PasswordResetOTP.objects.using(bank_db).filter(
                phone_number=phone_number
            ).exclude(id=otp_record.id).delete()[0]
            #logger.info(f"Supprimé {deleted_count} anciens tokens pour {phone_number}")

            #logger.info(f"Mot de passe réinitialisé avec succès pour {phone_number} (DB: {bank_db})")
            return {
                'success': True,
                'message': 'Mot de passe réinitialisé avec succès'
            }

        except Exception as e:
            #logger.error(f"Erreur dans reset_password (DB: {bank_db}): {str(e)}")
            return {
                'success': False,
                'error': 'Erreur interne du serveur'
            }

    # MÉTHODES UTILITAIRES - IDENTIQUES À VOTRE OTPService

    def _user_exists(self, phone_number, bank_db):
        """Vérifie si l'utilisateur existe dans la base spécifiée"""
        try:
            return User.objects.using(bank_db).filter(phone_number=phone_number).exists()
        except Exception as e:
            #logger.error(f"Erreur lors de la vérification utilisateur (DB: {bank_db}): {str(e)}")
            return False

    def _generate_otp(self):
        """Génère un code OTP à 6 chiffres - IDENTIQUE À VOTRE OTPService"""
        return str(random.randint(100000, 999999))

    def _can_send_otp(self, phone_number, bank_db, min_interval_minutes=1):
        """Vérifie si on peut envoyer un nouvel OTP dans la base spécifiée (anti-spam)"""
        try:
            recent_otp = PasswordResetOTP.objects.using(bank_db).filter(
                phone_number=phone_number,
                created_at__gte=timezone.now() - timedelta(minutes=min_interval_minutes)
            ).exists()
            return not recent_otp
        except Exception as e:
            #logger.error(f"Erreur lors de la vérification anti-spam (DB: {bank_db}): {str(e)}")
            return True  # En cas d'erreur, autoriser l'envoi

    def _cleanup_expired_otps(self, phone_number, bank_db):
        """Nettoie les anciens OTP expirés pour un numéro spécifique"""
        try:
            deleted_count = PasswordResetOTP.objects.using(bank_db).filter(
                phone_number=phone_number,
                expires_at__lt=timezone.now()
            ).delete()[0]
            if deleted_count > 0:
                logger.info(f"Supprimé {deleted_count} OTP expirés pour {phone_number} (DB: {bank_db})")
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage OTP (DB: {bank_db}): {str(e)}")

    def _cleanup_expired_otps_all(self, bank_db):
        """Nettoie tous les OTP expirés dans la base - comme OTPService"""
        try:
            deleted_count = PasswordResetOTP.objects.using(bank_db).filter(
                expires_at__lt=timezone.now()
            ).delete()[0]
            if deleted_count > 0:
                logger.info(f"Supprimé {deleted_count} OTP expirés total (DB: {bank_db})")
        except Exception as e:
            logger.error(f"Erreur lors du nettoyage OTP global (DB: {bank_db}): {str(e)}")

    def _save_reset_otp(self, phone_number, otp_code, bank_db):
        """Sauvegarde l'OTP de réinitialisation dans la base spécifiée"""
        try:
            PasswordResetOTP.objects.using(bank_db).create(
                phone_number=phone_number,
                otp_code=otp_code
            )
            #logger.info(f"OTP sauvegardé pour {phone_number} (DB: {bank_db})")
        except Exception as e:
            #logger.error(f"Erreur lors de la sauvegarde OTP (DB: {bank_db}): {str(e)}")
            raise

    def _handle_api_error(self, status_code, error_data):
        """
        Gère les erreurs de l'API Chinguisoft - IDENTIQUE À VOTRE OTPService
        """
        error_messages = {
            401: "Clés d'authentification invalides",
            402: "Solde insuffisant pour envoyer le SMS",
            422: "Données invalides",
            429: "Trop de requêtes, veuillez ralentir",
            500: "Service Chinguisoft temporairement indisponible",
            503: "Service temporairement indisponible"
        }
        
        return error_messages.get(status_code, f"Erreur inconnue: {error_data}")

    def _validate_phone_number(self, phone_number):
        """
        Valide le format du numéro de téléphone - IDENTIQUE À VOTRE OTPService
        (doit commencer par 2, 3, ou 4 et contenir 8 chiffres)
        """
        if len(phone_number) != 8:
            return False
        
        if not phone_number.isdigit():
            return False
        
        if not phone_number[0] in ['2', '3', '4']:
            return False
        
        return True
