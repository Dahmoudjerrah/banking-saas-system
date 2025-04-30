from rest_framework import serializers
from apps.users.models import User

from django.db.models import Q
from django.contrib.auth.hashers import check_password
from apps.accounts.models import Account
from apps.transactions.models import Transaction

import uuid
import logging
# from rest_framework import serializers
# from keycloak import KeycloakOpenID
# from django.conf import settings
import random
from django.db import IntegrityError
from rest_framework.exceptions import ValidationError

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'phone_number', 'date_of_birth']

    def create(self, validated_data):
        bank_db = self.context.get('bank_db', 'default')

        try:
            
            user = User.objects.db_manager(bank_db).create_user(
                username=validated_data['username'],
                email=validated_data['email'],
                password=validated_data['password'],
                phone_number=validated_data.get('phone_number', ''),
                date_of_birth=validated_data.get('date_of_birth', None),
            )

            
            account_number = Account.generate_account_number()
            Account.objects.db_manager(bank_db).create(
                user=user,
                account_number=account_number,
                type_account='personnel',
                balance=0, 
                status='ACTIVE'
            )

            return user

        except IntegrityError:
            raise ValidationError("Un utilisateur avec ce numéro de téléphone ou cet email existe déjà.")
        
class RegistrationAcounteAgancyBisenessSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    type_account = serializers.ChoiceField(choices=[('business', 'Business'), ('agency', 'Agency')], required=True)
    registration_number = serializers.CharField(required=True)
    tax_id = serializers.CharField(required=True)

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'phone_number', 'date_of_birth', 'type_account', 'registration_number', 'tax_id']

    def validate(self, data):
        type_account = data.get('type_account')

        
        if type_account not in ['business', 'agency']:
            raise serializers.ValidationError({"type_account": "Seuls les comptes de type 'business' ou 'agency' sont autorisés."})

        return data

    def create(self, validated_data):
        bank_db = self.context.get('bank_db')

        try:
            user = User.objects.db_manager(bank_db).create_user(
                username=validated_data['username'],
                email=validated_data['email'],
                password=validated_data['password'],
                phone_number=validated_data.get('phone_number', ''),
                date_of_birth=validated_data.get('date_of_birth', None),
            )

            
            account_number = Account.generate_account_number()
            unique_code = Account.objects.generate_unique_code(bank_db)
            Account.objects.db_manager(bank_db).create(
                user=user,
                account_number=account_number,
                type_account=validated_data['type_account'],
                balance=0,
                code=unique_code,
                status='ACTIVE',
                registration_number=validated_data['registration_number'],
                tax_id=validated_data['tax_id'],
            )

            return user

        except IntegrityError:
            raise ValidationError("Un utilisateur avec ce numéro de téléphone ou cet email existe déjà.")


#////////////////////////////////
# class CompteValidationSerializer(serializers.Serializer):
#     account_number = serializers.CharField()

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.bank_db = self.context.get('bank_db')
#     def validate(self, attrs):
#         account_number = attrs.get('account_number')

#         try:
          
#             Account.objects.using(self.bank_db).get(account_number=account_number)
#         except Account.DoesNotExist:
#             raise serializers.ValidationError(f"Aucun compte trouvé avec le numéro {account_number} dans la base de données {self.bank_db}.")

        
#         return attrs
class PhoneValidationSerializer(serializers.Serializer):
    phone_number = serializers.CharField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bank_db = self.context.get('bank_db')

    def validate(self, attrs):
        phone_number = attrs.get('phone_number')

        try:
            user = User.objects.using(self.bank_db).get(phone_number=phone_number)
            attrs['user'] = user
        except User.DoesNotExist:
            raise serializers.ValidationError(f"Aucun utilisateur trouvé avec le numéro de téléphone {phone_number} dans la base de données {self.bank_db}.")

        return attrs

class MerchantCodeValidationSerializer(serializers.Serializer):
    merchant_code = serializers.CharField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bank_db = self.context.get('bank_db')

    def validate(self, attrs):
        merchant_code = attrs.get('merchant_code')

        try:
            user = Account.objects.using(self.bank_db).get(code=merchant_code)
            attrs['user'] = user
        except User.DoesNotExist:
            raise serializers.ValidationError(f"Aucun utilisateur trouvé avec le code  {merchant_code} dans la base de données {self.bank_db}.")

        return attrs

class AddBusinessOrAgencyAccountSerializer(serializers.Serializer):
    phone_number = serializers.CharField()
    type_account = serializers.ChoiceField(choices=[('business', 'Business'), ('agency', 'Agency')], required=True)
    registration_number = serializers.CharField(required=True)
    tax_id = serializers.CharField(required=True)

    def validate(self, data):
        phone_number = data['phone_number']
        type_account = data['type_account']
        bank_db = self.context.get('bank_db')

        try:
            user = User.objects.using(bank_db).get(phone_number=phone_number)
        except User.DoesNotExist:
            raise serializers.ValidationError({"phone_number": "Aucun utilisateur trouvé avec ce numéro de téléphone."})

        if Account.objects.using(bank_db).filter(user=user, type_account=type_account).exists():
            raise serializers.ValidationError(f"L'utilisateur a déjà un compte de type {type_account}.")

        
        self.user = user
        return data

    def create(self, validated_data):
        bank_db = self.context.get('bank_db')
        unique_code = Account.objects.generate_unique_code(bank_db)
        account = Account.objects.db_manager(bank_db).create(
            user=self.user,
            account_number=Account.generate_account_number(),
            type_account=validated_data['type_account'],
            balance=0,
            status='ACTIVE',
            registration_number=validated_data['registration_number'],
            tax_id=validated_data['tax_id'],
            code=unique_code,
        )
        return account

class PasswordValidationSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bank_db = self.context.get('bank_db')
        

    def validate(self, attrs):
        password = attrs.get('password')
        user = self.context.get('user') 
        #print(password) 

        if not user:
            raise serializers.ValidationError("Utilisateur introuvable ou non authentifié.")

        if not check_password(password, user.password):
            raise serializers.ValidationError("Mot de passe incorrect.")

        return attrs

class UserAccountSerializer(serializers.Serializer):
    phone_number = serializers.CharField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bank_db = self.context.get('bank_db', 'default')

    def validate(self, attrs):
        phone_number = attrs.get('phone_number')

        try:
            user = User.objects.using(self.bank_db).get(phone_number=phone_number)
            attrs['user'] = user
        except User.DoesNotExist:
            raise serializers.ValidationError(
                f"Aucun utilisateur trouvé avec le numéro de téléphone {phone_number} dans la base de données {self.bank_db}."
            )
        try:
            account = Account.objects.using(self.bank_db).get(user=user,type_account='personnel')
            attrs['account'] = account
        except Account.DoesNotExist:
            raise serializers.ValidationError(
                f"Aucun compte trouvé pour l'utilisateur {user.username}."
            )

        return attrs

    def to_representation(self, instance):
        user = self.validated_data['user']
        account = self.validated_data['account']

        return {
            'username': user.username,
            'phone_number': user.phone_number,
            'email': user.email,
            'status': account.status,
            'solde': account.balance
            
        }    

class TransactionSerializer(serializers.Serializer):
    phone_number = serializers.CharField()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bank_db = self.context.get('bank_db')

    def validate(self, attrs):
        phone_number = attrs.get('phone_number')

        try:
            user = User.objects.using(self.bank_db).get(phone_number=phone_number)
            attrs['user'] = user
        except User.DoesNotExist:
            raise serializers.ValidationError(
                f"Aucun utilisateur trouvé avec le numéro de téléphone {phone_number} dans la base de données {self.bank_db}."
            )

        try:
            account = Account.objects.using(self.bank_db).get(user=user,type_account='personnel')
            attrs['account'] = account
        except Account.DoesNotExist:
            raise serializers.ValidationError(
                f"Aucun compte trouvé pour l'utilisateur {user.phone_number}."
            )

        return attrs

    def to_representation(self, instance):
        account = self.validated_data['account']

        account_transactions = Transaction.objects.using(self.bank_db).filter(
            Q(source_account=account) | Q(destination_account=account)
        ).exclude(destination_account__type_account="commission").order_by('-date')

        return {
            'transactions': [
                {
                    'type': transaction.type,
                    'date': transaction.date,
                    'amount': str(transaction.amount),
                    'source': self.determine_source(transaction, account),
                }
                for transaction in account_transactions
            ]
        }

    def determine_source(self, transaction, account):
        if transaction.source_account == account:
            return 'sent'
        elif transaction.destination_account == account:
            return 'received'
        else:
            return 'unknown'



class AllAccountsSerializer(serializers.Serializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bank_db = self.context.get('bank_db', 'default')
        

    def to_representation(self, instance):
        accounts = Account.objects.using(self.bank_db).all()
        return {
            'accounts': [
                {
                    'account_number':account.account_number,
                    'balance': str(account.balance),
                    'created_at': account.created_at,
                    'type': account.type_account,
                }
                for account in accounts
            ]
        }        