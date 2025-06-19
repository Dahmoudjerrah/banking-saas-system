from rest_framework import serializers
from apps.users.models import User

from django.db.models import Q
from django.contrib.auth.hashers import check_password
from apps.accounts.models import PersonalAccount,BusinessAccount,InternAccount,AgencyAccount
from apps.transactions.models import Transaction
from django.contrib.contenttypes.models import ContentType

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
    username = serializers.CharField()
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'phone_number', 'date_of_birth']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bank_db = self.context.get('bank_db')
    def create(self, validated_data):
        bank_db = self.context.get('bank_db', 'default')
        print(bank_db)

        try:
            
            user = User.objects.db_manager(bank_db).create_user(
                username=validated_data['username'],
                email=validated_data['email'],
                password=validated_data['password'],
                phone_number=validated_data.get('phone_number', ''),
                date_of_birth=validated_data.get('date_of_birth', None),
            )

            
            account_number = PersonalAccount.generate_account_number()
            PersonalAccount.objects.db_manager(bank_db).create(
                user=user,
                account_number=account_number,
              
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
            raise serializers.ValidationError(
                {"type_account": "Seuls les comptes de type 'business' ou 'agency' sont autorisés."}
            )

        return data
    
    def create(self, validated_data):
        bank_db = self.context.get('bank_db')
        type_account = validated_data.pop('type_account')
        registration_number = validated_data.pop('registration_number')
        tax_id = validated_data.pop('tax_id')

        try:
            # Création de l'utilisateur
            user = User.objects.db_manager(bank_db).create_user(
                username=validated_data['username'],
                email=validated_data['email'],
                password=validated_data['password'],
                phone_number=validated_data.get('phone_number', ''),
                date_of_birth=validated_data.get('date_of_birth', None),
            )

            # Création du compte selon le type
            if type_account == 'business':
                # Génération du code unique pour BusinessAccount
                unique_code = BusinessAccount.objects.generate_unique_code(bank_db)
                
                BusinessAccount.objects.db_manager(bank_db).create(
                    user=user,
                    balance=0,
                    code=unique_code,
                    status='ACTIVE',
                    registration_number=registration_number,
                    tax_id=tax_id,
                )
                
            elif type_account == 'agency':
                # Génération du code unique pour AgencyAccount
                unique_code = AgencyAccount.objects.generate_unique_code(bank_db)
                
                AgencyAccount.objects.db_manager(bank_db).create(
                    user=user,
                    balance=0,
                    code=unique_code,
                    status='ACTIVE',
                    registration_number=registration_number,
                    tax_id=tax_id,
                )

            return user

        except IntegrityError:
            raise ValidationError("Un utilisateur avec ce numéro de téléphone ou cet email existe déjà.")


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
            user = BusinessAccount.objects.using(self.bank_db).get(code=merchant_code)
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

        # Vérifier l'existence selon le type de compte avec les nouveaux modèles
        if type_account == 'business':
            if BusinessAccount.objects.using(bank_db).filter(user=user).exists():
                raise serializers.ValidationError(f"L'utilisateur a déjà un compte de type {type_account}.")
        elif type_account == 'agency':
            if AgencyAccount.objects.using(bank_db).filter(user=user).exists():
                raise serializers.ValidationError(f"L'utilisateur a déjà un compte de type {type_account}.")

        self.user = user
        return data

    def create(self, validated_data):
        bank_db = self.context.get('bank_db')
        type_account = validated_data['type_account']
        
        # Création selon le type de compte
        if type_account == 'business':
            # Génération du code unique pour BusinessAccount
            unique_code = BusinessAccount.objects.generate_unique_code(bank_db)
            
            account = BusinessAccount.objects.db_manager(bank_db).create(
                user=self.user,
                balance=0,
                account_number = BusinessAccount.generate_account_number(),
                status='ACTIVE',
                registration_number=validated_data['registration_number'],
                tax_id=validated_data['tax_id'],
                code=unique_code,
                # account_number sera généré automatiquement par le modèle
            )
            
        elif type_account == 'agency':
            # Génération du code unique pour AgencyAccount
            unique_code = AgencyAccount.objects.generate_unique_code(bank_db)
            
            account = AgencyAccount.objects.db_manager(bank_db).create(
                user=self.user,
                balance=0,
                account_number = AgencyAccount.generate_account_number(),
                status='ACTIVE',
                registration_number=validated_data['registration_number'],
                tax_id=validated_data['tax_id'],
                code=unique_code,
                # account_number sera généré automatiquement par le modèle
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
            account = PersonalAccount.objects.using(self.bank_db).get(user=user)
            attrs['account'] = account
        except PersonalAccount.DoesNotExist:
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
            account = PersonalAccount.objects.using(self.bank_db).get(user=user)
            attrs['account'] = account
        except PersonalAccount.DoesNotExist:
            raise serializers.ValidationError(
                f"Aucun compte personnel trouvé pour l'utilisateur {user.phone_number}."
            )

        return attrs

    def to_representation(self, instance):
        account = self.validated_data['account']
        
        # ContentTypes pour filtrer les transactions
        personal_account_ct = ContentType.objects.get_for_model(PersonalAccount)
        intern_account_ct = ContentType.objects.get_for_model(InternAccount)

        # Récupérer les IDs des comptes de commission pour les exclure
        commission_account_ids = list(
            InternAccount.objects.using(self.bank_db)
            .filter(purpose='commission')
            .values_list('id', flat=True)
        )

        # Construire la requête avec exclusion des comptes de commission
        exclude_condition = Q()
        if commission_account_ids:
            exclude_condition = Q(
                destination_account_type=intern_account_ct,
                destination_account_id__in=commission_account_ids
            )

        # Filtrer les transactions liées au compte personnel
        account_transactions = Transaction.objects.using(self.bank_db).filter(
            Q(
                source_account_type=personal_account_ct,
                source_account_id=account.id
            ) | Q(
                destination_account_type=personal_account_ct,
                destination_account_id=account.id
            )
        ).exclude(exclude_condition).order_by('-date')

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
        # ContentType pour le compte personnel
        personal_account_ct = ContentType.objects.get_for_model(PersonalAccount)
        
        # Vérifier si le compte est la source de la transaction
        if (transaction.source_account_type == personal_account_ct and 
            transaction.source_account_id == account.id):
            return 'sent'
        # Vérifier si le compte est la destination de la transaction
        elif (transaction.destination_account_type == personal_account_ct and 
              transaction.destination_account_id == account.id):
            return 'received'
        else:
            return 'unknown'


# class AllAccountsSerializer(serializers.Serializer):
#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.bank_db = self.context.get('bank_db')
        
#     def to_representation(self, instance):
#         accounts = Account.objects.using(self.bank_db).all()
#         return {
#             'accounts':[
#                 {
#                     'account_number':account.account_number,
#                     'balance': str(account.balance),
#                     'created_at': account.created_at,
#                     'type': account.type_account,
#                 }
#                 for account in accounts
#             ]
#         } 

class TransactionAganceSerialiser(serializers.Serializer):
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
            account = AgencyAccount.objects.using(self.bank_db).get(user=user)
            attrs['account'] = account
        except AgencyAccount.DoesNotExist:
            raise serializers.ValidationError(
                f"Aucun compte d'agence trouvé pour l'utilisateur {user.phone_number}."
            )

        return attrs

    def to_representation(self, instance):
        account = self.validated_data['account']
        
        # ContentTypes pour filtrer les transactions
        agency_account_ct = ContentType.objects.get_for_model(AgencyAccount)
        intern_account_ct = ContentType.objects.get_for_model(InternAccount)

        # Filtrer les transactions liées au compte d'agence
        account_transactions = Transaction.objects.using(self.bank_db).filter(
            Q(
                source_account_type=agency_account_ct,
                source_account_id=account.id
            ) | Q(
                destination_account_type=agency_account_ct,
                destination_account_id=account.id
            )
        ).order_by('-date')

        # CORRECTION : Filtrer les transactions de commission APRÈS la requête principale
        # car on ne peut pas utiliser GenericForeignKey dans exclude() directement
        filtered_transactions = []
        for transaction in account_transactions:
            # Vérifier si c'est une transaction vers un compte de commission
            if (transaction.destination_account_type == intern_account_ct):
                try:
                    # Récupérer le compte de destination pour vérifier le purpose
                    destination_account = InternAccount.objects.using(self.bank_db).get(
                        id=transaction.destination_account_id
                    )
                    # Exclure les transactions vers les comptes de commission
                    if destination_account.purpose == 'commission':
                        continue
                except InternAccount.DoesNotExist:
                    # Si le compte n'existe pas, ignorer cette vérification
                    pass
            
            # Ajouter la transaction si elle n'est pas exclue
            filtered_transactions.append(transaction)

        return {
            'transactions': [
                {
                    'type': transaction.type,
                    'date': transaction.date,
                    'amount': str(transaction.amount),
                    'source': self.determine_source(transaction, account),
                }
                for transaction in filtered_transactions
            ]
        }

    def determine_source(self, transaction, account):
        # ContentType pour le compte d'agence
        agency_account_ct = ContentType.objects.get_for_model(AgencyAccount)
        
        # Vérifier si le compte est la source de la transaction
        if (transaction.source_account_type == agency_account_ct and 
            transaction.source_account_id == account.id):
            return 'sent'
        # Vérifier si le compte est la destination de la transaction
        elif (transaction.destination_account_type == agency_account_ct and 
              transaction.destination_account_id == account.id):
            return 'received'
        else:
            return 'unknown'        
class TransactionBusinessSerialiser(serializers.Serializer):
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
            account = BusinessAccount.objects.using(self.bank_db).get(user=user)
            attrs['account'] = account
        except BusinessAccount.DoesNotExist:
            raise serializers.ValidationError(
                f"Aucun compte business trouvé pour l'utilisateur {user.phone_number}."
            )

        return attrs

    def to_representation(self, instance):
        account = self.validated_data['account']
        
        # ContentTypes pour filtrer les transactions
        business_account_ct = ContentType.objects.get_for_model(BusinessAccount)
        intern_account_ct = ContentType.objects.get_for_model(InternAccount)

        # Filtrer les transactions liées au compte business
        account_transactions = Transaction.objects.using(self.bank_db).filter(
            Q(
                source_account_type=business_account_ct,
                source_account_id=account.id
            ) | Q(
                destination_account_type=business_account_ct,
                destination_account_id=account.id
            )
        ).order_by('-date')

        # CORRECTION : Filtrer les transactions de commission APRÈS la requête principale
        # car on ne peut pas utiliser GenericForeignKey dans exclude() directement
        filtered_transactions = []
        for transaction in account_transactions:
            # Vérifier si c'est une transaction vers un compte de commission
            if (transaction.destination_account_type == intern_account_ct):
                try:
                    # Récupérer le compte de destination pour vérifier le purpose
                    destination_account = InternAccount.objects.using(self.bank_db).get(
                        id=transaction.destination_account_id
                    )
                    # Exclure les transactions vers les comptes de commission
                    if destination_account.purpose == 'commission':
                        continue
                except InternAccount.DoesNotExist:
                    # Si le compte n'existe pas, ignorer cette vérification
                    pass
            
            # Ajouter la transaction si elle n'est pas exclue
            filtered_transactions.append(transaction)

        return {
            'transactions': [
                {
                    'type': transaction.type,
                    'date': transaction.date,
                    'amount': str(transaction.amount),
                    'source': self.determine_source(transaction, account),
                }
                for transaction in filtered_transactions
            ]
        }

    def determine_source(self, transaction, account):
        # ContentType pour le compte business
        business_account_ct = ContentType.objects.get_for_model(BusinessAccount)
        
        # Vérifier si le compte est la source de la transaction
        if (transaction.source_account_type == business_account_ct and 
            transaction.source_account_id == account.id):
            return 'sent'
        # Vérifier si le compte est la destination de la transaction
        elif (transaction.destination_account_type == business_account_ct and 
              transaction.destination_account_id == account.id):
            return 'received'
        else:
            return 'unknown'
        



class ComercantAccountSerializer(serializers.Serializer):
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
            account = BusinessAccount.objects.using(self.bank_db).get(user=user)
            attrs['account'] = account
        except BusinessAccount.DoesNotExist:
            raise serializers.ValidationError(
                f"Aucun compte business trouvé pour l'utilisateur {user.username}."
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
            'solde': account.balance,
            'code': account.code,
            'registration': account.registration_number,
            'tax': account.tax_id
        }
class AganceAccountSerializer(serializers.Serializer):
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
            account = AgencyAccount.objects.using(self.bank_db).get(user=user)
            attrs['account'] = account
        except AgencyAccount.DoesNotExist:
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
            'solde': account.balance,
            'code':account.code,
            'registration':account.registration_number,
            'tax':account.tax_id
            
        }      