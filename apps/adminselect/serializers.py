# from rest_framework import serializers
# from apps.accounts.models import Account, DemandeChequiers
# from apps.transactions.models import Fee, FeeRule, PaymentRequest, PreTransaction, Transaction
# from apps.users.models import User

# from django.contrib.auth.password_validation import validate_password

# from django.db import IntegrityError
# from rest_framework.exceptions import ValidationError

# class MultiDatabaseSerializerMixin:
#     """Mixin pour gérer les bases de données multiples dans les serializers"""
    
#     def __init__(self, *args, **kwargs):
#         self.bank_db = kwargs.pop('bank_db', None)
#         super().__init__(*args, **kwargs)
    
#     def get_db_for_model(self, model_class):
#         """Retourne la base de données à utiliser pour un modèle donné"""
#         return self.bank_db or 'default'

# class LoginSerializer(serializers.Serializer):
#     phone_number = serializers.CharField()
#     password = serializers.CharField(write_only=True)
    
#     def validate(self, data):
#         phone_number = data.get('phone_number')
#         password = data.get('password')
        
#         if not phone_number or not password:
#             raise serializers.ValidationError("numero de telephone et password sont requis.")
        
#         # Récupérer la base de données du contexte
#         bank_db = self.context.get('bank_db', 'default')
        
#         # Chercher l'utilisateur dans la base de données spécifiée
#         try:
#             user = User.objects.using(bank_db).get(phone_number=phone_number)
#         except User.DoesNotExist:
#             raise serializers.ValidationError("Numero du telephone d'utilisateur ou mot de passe incorrect.")
        
#         # Vérifier le mot de passe
#         if not user.check_password(password):
#             raise serializers.ValidationError("Numero du telephone ou mot de passe incorrect.")
        
#         # Vérifier si l'utilisateur est actif
#         # if not user.is_active:
#         #     raise serializers.ValidationError("Ce compte est désactivé.")
        
#         data['user'] = user
#         return data

# class RegisterSerializer(serializers.ModelSerializer):
#     phone_number = serializers.CharField(required=False)
#     password = serializers.CharField(write_only=True, validators=[validate_password])
#     confirm_password = serializers.CharField(write_only=True)
    
#     class Meta:
#         model = User
#         fields = ['username', 'email', 'phone_number', 'password', 'confirm_password', 'date_of_birth']
    
#     def validate(self, data):
#         # Vérifier que les mots de passe correspondent
#         if data['password'] != data['confirm_password']:
#             raise serializers.ValidationError("Les mots de passe ne correspondent pas.")
        
#         # Récupérer la base de données du contexte
#         bank_db = self.context.get('bank_db', 'default')
        
#         # Vérifier l'unicité du username dans cette DB
#         if User.objects.using(bank_db).filter(username=data['username']).exists():
#             raise serializers.ValidationError({
#                 "username": "Un utilisateur avec ce nom d'utilisateur existe déjà."
#             })
        
#         # Vérifier l'unicité de l'email dans cette DB
#         if User.objects.using(bank_db).filter(email=data['email']).exists():
#             raise serializers.ValidationError({
#                 "email": "Un utilisateur avec cet email existe déjà."
#             })
        
#         # Vérifier l'unicité du téléphone dans cette DB
#         if User.objects.using(bank_db).filter(phone_number=data['phone_number']).exists():
#             raise serializers.ValidationError({
#                 "phone_number": "Un utilisateur avec ce numéro de téléphone existe déjà."
#             })
        
#         return data
    
#     def create(self, validated_data):
#         # Supprimer confirm_password des données
#         validated_data.pop('confirm_password', None)
        
#         # Récupérer la base de données
#         bank_db = self.context.get('bank_db', 'default')
        
#         # Créer l'utilisateur dans la bonne DB
#         user = User.objects.db_manager(bank_db).create_user(
#             username=validated_data['username'],
#             email=validated_data['email'],
#             phone_number=validated_data['phone_number'],
#             password=validated_data['password'],
#             date_of_birth=validated_data.get('date_of_birth')
#         )
        
#         return user

# class UserSerializer(MultiDatabaseSerializerMixin, serializers.ModelSerializer):
#     class Meta:
#         model = User
#         fields = ['id', 'username', 'email', 'phone_number', 'date_of_birth', 'is_active']
#         read_only_fields = ['id']


# class RegistrationAcounteAgancyBisenessSerializer(serializers.ModelSerializer):
#     password = serializers.CharField(write_only=True)
#     type_account = serializers.ChoiceField(choices=[('business', 'Business'), ('agency', 'Agency')], required=True)
#     registration_number = serializers.CharField(required=True)
#     tax_id = serializers.CharField(required=True)

#     class Meta:
#         model = User
#         fields = ['username', 'email', 'password', 'phone_number', 'date_of_birth', 'type_account', 'registration_number', 'tax_id']

#     def validate(self, data):
#         type_account = data.get('type_account')

        
#         if type_account not in ['business', 'agency']:
#             raise serializers.ValidationError({"type_account": "Seuls les comptes de type 'business' ou 'agency' sont autorisés."})

#         return data
    
#     def create(self, validated_data):
#         bank_db = self.context.get('bank_db')

#         try:
#             user = User.objects.db_manager(bank_db).create_user(
#                 username=validated_data['username'],
#                 email=validated_data['email'],
#                 password=validated_data['password'],
#                 phone_number=validated_data.get('phone_number', ''),
#                 date_of_birth=validated_data.get('date_of_birth', None),
#             )

#             account_number = Account.generate_account_number()
#             unique_code = Account.objects.generate_unique_code(bank_db)
#             Account.objects.db_manager(bank_db).create(
#                 user=user,
#                 account_number=account_number,
#                 type_account=validated_data['type_account'],
#                 balance=0,
#                 code=unique_code,
#                 status='ACTIVE',
#                 registration_number=validated_data['registration_number'],
#                 tax_id=validated_data['tax_id'],
#             )

#             return user

#         except IntegrityError:
#             raise ValidationError("Un utilisateur avec ce numéro de téléphone ou cet email existe déjà.")
        
# class RegistrationAcounteAgancySerializer(serializers.ModelSerializer):
#     password = serializers.CharField(write_only=True)
#     type_account = serializers.ChoiceField(choices=[('agency', 'Agency')], required=True)
#     registration_number = serializers.CharField(required=True)
#     tax_id = serializers.CharField(required=True)

#     class Meta:
#         model = User
#         fields = ['username', 'email', 'password', 'phone_number', 'date_of_birth', 'type_account', 'registration_number', 'tax_id']

#     def validate(self, data):
#         type_account = data.get('type_account')

        
#         if type_account not in ['agency']:
#             raise serializers.ValidationError({"type_account": "Seuls les comptes de type'agency' sont autorisés."})

#         return data
    
#     def create(self, validated_data):
#         bank_db = self.context.get('bank_db')

#         try:
#             user = User.objects.db_manager(bank_db).create_user(
#                 username=validated_data['username'],
#                 email=validated_data['email'],
#                 password=validated_data['password'],
#                 phone_number=validated_data.get('phone_number', ''),
#                 date_of_birth=validated_data.get('date_of_birth', None),
#             )

#             account_number = Account.generate_account_number()
#             unique_code = Account.objects.generate_unique_code(bank_db)
#             Account.objects.db_manager(bank_db).create(
#                 user=user,
#                 account_number=account_number,
#                 type_account=validated_data['type_account'],
#                 balance=0,
#                 code=unique_code,
#                 status='ACTIVE',
#                 registration_number=validated_data['registration_number'],
#                 tax_id=validated_data['tax_id'],
#             )

#             return user

#         except IntegrityError:
#             raise ValidationError("Un utilisateur avec ce numéro de téléphone ou cet email existe déjà.")
    
# class RegistrationAcounteBisenessSerializer(serializers.ModelSerializer):
#     password = serializers.CharField(write_only=True)
#     type_account = serializers.ChoiceField(choices=[('business', 'Business')], required=True)
#     registration_number = serializers.CharField(required=True)
#     tax_id = serializers.CharField(required=True)

#     class Meta:
#         model = User
#         fields = ['username', 'email', 'password', 'phone_number', 'date_of_birth', 'type_account', 'registration_number', 'tax_id']

#     def validate(self, data):
#         type_account = data.get('type_account')

        
#         if type_account not in ['business']:
#             raise serializers.ValidationError({"type_account": "Seuls les comptes de type 'business' sont autorisés."})

#         return data
    
#     def create(self, validated_data):
#         bank_db = self.context.get('bank_db')

#         try:
#             user = User.objects.db_manager(bank_db).create_user(
#                 username=validated_data['username'],
#                 email=validated_data['email'],
#                 password=validated_data['password'],
#                 phone_number=validated_data.get('phone_number', ''),
#                 date_of_birth=validated_data.get('date_of_birth', None),
#             )

#             account_number = Account.generate_account_number()
#             unique_code = Account.objects.generate_unique_code(bank_db)
#             Account.objects.db_manager(bank_db).create(
#                 user=user,
#                 account_number=account_number,
#                 type_account=validated_data['type_account'],
#                 balance=0,
#                 code=unique_code,
#                 status='ACTIVE',
#                 registration_number=validated_data['registration_number'],
#                 tax_id=validated_data['tax_id'],
#             )

#             return user

#         except IntegrityError:
#             raise ValidationError("Un utilisateur avec ce numéro de téléphone ou cet email existe déjà.")

# class AddBusinessOrAgencyAccountSerializer(serializers.Serializer):
#     phone_number = serializers.CharField()
#     type_account = serializers.ChoiceField(choices=[('business', 'Business'), ('agency', 'Agency')], required=True)
#     registration_number = serializers.CharField(required=True)
#     tax_id = serializers.CharField(required=True)

#     def validate(self, data):
#         phone_number = data['phone_number']
#         type_account = data['type_account']
#         bank_db = self.context.get('bank_db')

#         try:
#             user = User.objects.using(bank_db).get(phone_number=phone_number)
#         except User.DoesNotExist:
#             raise serializers.ValidationError({"phone_number": "Aucun utilisateur trouvé avec ce numéro de téléphone."})

#         if Account.objects.using(bank_db).filter(user=user, type_account=type_account).exists():
#             raise serializers.ValidationError(f"L'utilisateur a déjà un compte de type {type_account}.")

        
#         self.user = user
#         return data

#     def create(self, validated_data):
#         bank_db = self.context.get('bank_db')
#         unique_code = Account.objects.generate_unique_code(bank_db)
#         account = Account.objects.db_manager(bank_db).create(
#             user=self.user,
#             account_number=Account.generate_account_number(),
#             type_account=validated_data['type_account'],
#             balance=0,
#             status='ACTIVE',
#             registration_number=validated_data['registration_number'],
#             tax_id=validated_data['tax_id'],
#             code=unique_code,
#         )
#         return account

# class AddBusinessAccountSerializer(serializers.Serializer):
#     phone_number = serializers.CharField()
#     type_account = serializers.ChoiceField(choices=[('business', 'Business')], required=True)
#     registration_number = serializers.CharField(required=True)
#     tax_id = serializers.CharField(required=True)

#     def validate(self, data):
#         phone_number = data['phone_number']
#         type_account = data['type_account']
#         bank_db = self.context.get('bank_db')

#         try:
#             user = User.objects.using(bank_db).get(phone_number=phone_number)
#         except User.DoesNotExist:
#             raise serializers.ValidationError({"phone_number": "Aucun utilisateur trouvé avec ce numéro de téléphone."})

#         if Account.objects.using(bank_db).filter(user=user, type_account=type_account).exists():
#             raise serializers.ValidationError(f"L'utilisateur a déjà un compte de type {type_account}.")

        
#         self.user = user
#         return data

#     def create(self, validated_data):
#         bank_db = self.context.get('bank_db')
#         unique_code = Account.objects.generate_unique_code(bank_db)
#         account = Account.objects.db_manager(bank_db).create(
#             user=self.user,
#             account_number=Account.generate_account_number(),
#             type_account=validated_data['type_account'],
#             balance=0,
#             status='ACTIVE',
#             registration_number=validated_data['registration_number'],
#             tax_id=validated_data['tax_id'],
#             code=unique_code,
#         )
#         return account
    
# class AddAgencyAccountSerializer(serializers.Serializer):
#     phone_number = serializers.CharField()
#     type_account = serializers.ChoiceField(choices=[('agency', 'Agency')], required=True)
#     registration_number = serializers.CharField(required=True)
#     tax_id = serializers.CharField(required=True)

#     def validate(self, data):
#         phone_number = data['phone_number']
#         type_account = data['type_account']
#         bank_db = self.context.get('bank_db')

#         try:
#             user = User.objects.using(bank_db).get(phone_number=phone_number)
#         except User.DoesNotExist:
#             raise serializers.ValidationError({"phone_number": "Aucun utilisateur trouvé avec ce numéro de téléphone."})

#         if Account.objects.using(bank_db).filter(user=user, type_account=type_account).exists():
#             raise serializers.ValidationError(f"L'utilisateur a déjà un compte de type {type_account}.")

        
#         self.user = user
#         return data

#     def create(self, validated_data):
#         bank_db = self.context.get('bank_db')
#         unique_code = Account.objects.generate_unique_code(bank_db)
#         account = Account.objects.db_manager(bank_db).create(
#             user=self.user,
#             account_number=Account.generate_account_number(),
#             type_account=validated_data['type_account'],
#             balance=0,
#             status='ACTIVE',
#             registration_number=validated_data['registration_number'],
#             tax_id=validated_data['tax_id'],
#             code=unique_code,
#         )
#         return account

# class AccountSerializer(MultiDatabaseSerializerMixin, serializers.ModelSerializer):
#     user = UserSerializer(read_only=True)
    
#     class Meta:
#         model = Account
#         fields = '__all__'
#         read_only_fields = ['id', 'account_number', 'created_at']
    
#     def to_representation(self, instance):
#         """Personnaliser la représentation avec la bonne DB"""
#         if self.bank_db and hasattr(instance, 'user'):
#             # S'assurer que les relations utilisent la bonne DB
#             self.fields['user'].bank_db = self.bank_db
#         return super().to_representation(instance)

# class TransactionSerializer(MultiDatabaseSerializerMixin, serializers.ModelSerializer):
#     source_account = AccountSerializer(read_only=True)
#     destination_account = AccountSerializer(read_only=True)
    
#     class Meta:
#         model = Transaction
#         fields = '__all__'
#         read_only_fields = ['id', 'date']
    
#     def to_representation(self, instance):
#         if self.bank_db:
#             self.fields['source_account'].bank_db = self.bank_db
#             self.fields['destination_account'].bank_db = self.bank_db
#         return super().to_representation(instance)

# class FeeRuleSerializer(MultiDatabaseSerializerMixin, serializers.ModelSerializer):
#     class Meta:
#         model = FeeRule
#         fields = '__all__'

#     def create(self, validated_data):
#         db = self.context.get('bank_db', 'default')
        
#         # On enlève l'éventuel champ 'using' si jamais il est là par erreur
#         validated_data.pop('using', None)

#         return FeeRule.objects.using(db).create(**validated_data)


#     def update(self, instance, validated_data):
#         db = self.bank_db or 'default'
#         for attr, value in validated_data.items():
#             setattr(instance, attr, value)
#         instance.save(using=db)
#         return instance


# class FeeSerializer(MultiDatabaseSerializerMixin, serializers.ModelSerializer):
#     transaction = TransactionSerializer(read_only=True)
    
#     class Meta:
#         model = Fee
#         fields = '__all__'
#         read_only_fields = ['created_at']
    
#     def to_representation(self, instance):
#         if self.bank_db:
#             self.fields['transaction'].bank_db = self.bank_db
#         return super().to_representation(instance)

# class PaymentRequestSerializer(MultiDatabaseSerializerMixin, serializers.ModelSerializer):
#     merchant = AccountSerializer(read_only=True)
    
#     class Meta:
#         model = PaymentRequest
#         fields = '__all__'
#         read_only_fields = ['code', 'created_at']
    
#     def to_representation(self, instance):
#         if self.bank_db:
#             self.fields['merchant'].bank_db = self.bank_db
#         return super().to_representation(instance)

# class PreTransactionSerializer(MultiDatabaseSerializerMixin, serializers.ModelSerializer):
#     is_active_status = serializers.SerializerMethodField()
    
#     class Meta:
#         model = PreTransaction
#         fields = '__all__'
#         read_only_fields = ['id', 'code', 'created_at']
    
#     def get_is_active_status(self, obj):
#         return obj.is_active()

# class DemandeChequiersSerializer(MultiDatabaseSerializerMixin, serializers.ModelSerializer):
#     compte = AccountSerializer(read_only=True)
    
#     class Meta:
#         model = DemandeChequiers
#         fields = '__all__'
#         read_only_fields = ['demande_le']
    
#     def to_representation(self, instance):
#         if self.bank_db:
#             self.fields['compte'].bank_db = self.bank_db
#         return super().to_representation(instance)