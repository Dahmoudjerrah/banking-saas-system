from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed
from rest_framework import serializers
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth.hashers import check_password as django_check_password
from django.contrib.auth import authenticate
from apps.accounts.models import Account
from decimal import Decimal
class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):

     def validate(self, attrs):
        bank_db = self.context['request'].source_bank_db
        
        user = authenticate(
            request=self.context['request'],
            phone_number=attrs['phone_number'],
            password=attrs['password'],
            
        )

        if not user:
            raise serializers.ValidationError(
                {'non_field_errors': ["No active account found with the given credentials"]}
            )
        
        #data = super().validate(attrs)

        
        account = Account.objects.using(bank_db).filter(user=user).first()
        refresh = RefreshToken.for_user(user)

      
        balance = float(account.balance) if account and account.balance else None
        refresh['username'] = user.username
        refresh['phone_number'] = user.phone_number
        refresh['solde'] = balance
        refresh['bank_db'] = bank_db
        
        
        data = {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }

        # if account:
        #     data['account_number'] = account.account_number
            # data['refresh'] = str(refresh)
            # data['access'] = str(refresh.access_token)

        return data
     def to_representation(self, instance):
        data = super().to_representation(instance)
        for key, value in data.items():
            if isinstance(value, Decimal):
                data[key] = float(value)
        return data




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
        
