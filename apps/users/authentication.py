from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework import serializers
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import check_password as django_check_password
from django.contrib.auth import authenticate

from decimal import Decimal



from apps.accounts.models import PersonalAccount, BusinessAccount, AgencyAccount


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    account_type = serializers.CharField(required=True)
    
    def validate(self, attrs):
        bank_db = self.context['request'].source_bank_db
        account_type = attrs.get('account_type')
        
        user = authenticate(
            request=self.context['request'],
            phone_number=attrs['phone_number'],
            password=attrs['password'],
        )

        if not user:
            raise serializers.ValidationError(
                {'non_field_errors': ["No active account found with the given credentials"]}
            )

        # Rechercher le compte selon le type demandé avec les nouveaux modèles
        account = None
        if account_type == 'personnel':
            try:
                account = PersonalAccount.objects.using(bank_db).get(
                    user=user, 
                    status='ACTIVE'
                )
            except PersonalAccount.DoesNotExist:
                pass
                
        elif account_type == 'business':
            try:
                account = BusinessAccount.objects.using(bank_db).get(
                    user=user, 
                    status='ACTIVE'
                )
            except BusinessAccount.DoesNotExist:
                pass
                
        elif account_type == 'agency':
            try:
                account = AgencyAccount.objects.using(bank_db).get(
                    user=user, 
                    status='ACTIVE'
                )
            except AgencyAccount.DoesNotExist:
                pass
        
        if not account:
            # Si le compte du type demandé n'existe pas, chercher les types disponibles
            available_types = []
            
            # Vérifier les comptes personnel actifs
            if PersonalAccount.objects.using(bank_db).filter(user=user, status='ACTIVE').exists():
                available_types.append('personnel')
                
            # Vérifier les comptes business actifs
            if BusinessAccount.objects.using(bank_db).filter(user=user, status='ACTIVE').exists():
                available_types.append('business')
                
            # Vérifier les comptes agence actifs
            if AgencyAccount.objects.using(bank_db).filter(user=user, status='ACTIVE').exists():
                available_types.append('agency')
            
            if available_types:
                # Conversion des types en noms d'affichage
                available_types_display = []
                type_mapping = {
                    'personnel': 'Personnel',
                    'business': 'Business', 
                    'agency': 'Agency'
                }
                
                for acc_type in available_types:
                    available_types_display.append(type_mapping.get(acc_type, acc_type))
                
                raise serializers.ValidationError({
                    'account_type': [
                        f"Vous n'avez pas de compte {account_type} actif. "
                        f"Types disponibles: {', '.join(available_types_display)}"
                    ]
                })
            else:
                raise serializers.ValidationError({
                    'non_field_errors': ["Aucun compte actif trouvé pour cet utilisateur"]
                })

        # Génération des tokens
        refresh = RefreshToken.for_user(user)
        
        balance = float(account.balance) if account and account.balance else None
        refresh['username'] = user.username
        refresh['phone_number'] = user.phone_number
        refresh['solde'] = balance
        refresh['bank_db'] = bank_db
        refresh['account_type'] = account_type
        refresh['account_number'] = account.account_number

        access = refresh.access_token
        access['username'] = user.username
        access['phone_number'] = user.phone_number
        access['solde'] = balance
        access['bank_db'] = bank_db
        access['account_type'] = account_type
        access['account_number'] = account.account_number
        
        data = {
            'refresh': str(refresh),
            'access': str(access),
        }

        return data

    def to_representation(self, instance):
        data = super().to_representation(instance)
        for key, value in data.items():
            if isinstance(value, Decimal):
                data[key] = float(value)
        return data
# class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
#     account_type = serializers.CharField(required=True)
    
#     def validate(self, attrs):
#         bank_db = self.context['request'].source_bank_db
#         account_type = attrs.get('account_type')
        
#         user = authenticate(
#             request=self.context['request'],
#             phone_number=attrs['phone_number'],
#             password=attrs['password'],
#         )

#         if not user:
#             raise serializers.ValidationError(
#                 {'non_field_errors': ["No active account found with the given credentials"]}
#             )

#         # Vérifier si l'utilisateur a un compte du type demandé et actif
#         account = Account.objects.using(bank_db).filter(
#             user=user, 
#             type_account=account_type,
#             status='ACTIVE'  # Vérifier que le compte est actif
#         ).first()
        
#         if not account:
#             # Si le compte du type demandé n'existe pas, chercher les types disponibles
#             available_accounts = Account.objects.using(bank_db).filter(
#                 user=user, 
#                 status='ACTIVE'  # Seulement les comptes actifs
#             )
#             available_types = [acc.type_account for acc in available_accounts]
            
#             if available_types:
#                 available_types_display = []
#                 for acc_type in available_types:
#                     for choice in Account.ACCOUNT_TYPES:
#                         if choice[0] == acc_type:
#                             available_types_display.append(choice[1])
#                             break
                
#                 raise serializers.ValidationError({
#                     'account_type': [
#                         f"Vous n'avez pas de compte {account_type} actif. "
#                         f"Types disponibles: {', '.join(available_types_display)}"
#                     ]
#                 })
#             else:
#                 raise serializers.ValidationError({
#                     'non_field_errors': ["Aucun compte actif trouvé pour cet utilisateur"]
#                 })

#         refresh = RefreshToken.for_user(user)
        
#         balance = float(account.balance) if account and account.balance else None
#         refresh['username'] = user.username
#         refresh['phone_number'] = user.phone_number
#         refresh['solde'] = balance
#         refresh['bank_db'] = bank_db
#         refresh['account_type'] = account_type  # Ajouter le type de compte au token
#         refresh['account_number'] = account.account_number

#         access = refresh.access_token
#         access['username'] = user.username
#         access['phone_number'] = user.phone_number
#         access['solde'] = balance
#         access['bank_db'] = bank_db
#         access['account_type'] = account_type  # ← CECI EST LA SOLUTION !
#         access['account_number'] = account.account_number
        
#         data = {
#             'refresh': str(refresh),
#             'access': str(access),
#         }

#         return data

#     def to_representation(self, instance):
#         data = super().to_representation(instance)
#         for key, value in data.items():
#             if isinstance(value, Decimal):
#                 data[key] = float(value)
#         return data


class CustomJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        auth_result = super().authenticate(request)
        if auth_result is not None:
            user, token = auth_result
            request.source_bank_db = token.get('bank_db')
            request.user_account_type = token.get('account_type') 
            
        return auth_result

    def get_user(self, validated_token):
        User = get_user_model()
        try:
            user_id = validated_token['user_id']
            phone_number = validated_token.get('phone_number')
            bank_db = validated_token.get('bank_db')

            if not bank_db:
                raise AuthenticationFailed('Bank DB not set in token')

            user = User.objects.using(bank_db).get(id=user_id, phone_number=phone_number)
            return user
        except User.DoesNotExist:
            raise AuthenticationFailed('User not found')
        except Exception as e:
            raise AuthenticationFailed(str(e))



class BankSpecificAuthenticationBackend(ModelBackend):
    def authenticate(self, request, phone_number=None, password=None, **kwargs):
        bank_db = getattr(request, 'source_bank_db', 'default')
        UserModel = get_user_model()
        
        try:
            user = UserModel.objects.using(bank_db).get(phone_number=phone_number)
            if django_check_password(password, user.password):
                return user
                
        except UserModel.DoesNotExist:
            return None
        
class CustomJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        auth_result = super().authenticate(request)
        if auth_result is not None:
            user, token = auth_result
            request.source_bank_db = token.get('bank_db')
            request.user_account_type = token.get('account_type') 
        return auth_result

    def get_user(self, validated_token):
        User = get_user_model()
        try:
            user_id = validated_token['user_id']
            phone_number = validated_token.get('phone_number')
            bank_db = validated_token.get('bank_db')

            if not bank_db:
                raise AuthenticationFailed('Bank DB not set in token')

            user = User.objects.using(bank_db).get(id=user_id, phone_number=phone_number)
            return user
        except User.DoesNotExist:
            raise AuthenticationFailed('User not found')
        except Exception as e:
            raise AuthenticationFailed(str(e))
        
