# serializers.py
from rest_framework import serializers

from apps.transactions.models import Transaction
from ..accounts.models import PersonalAccount, BusinessAccount, AgencyAccount, InternAccount
from apps.users.models import User
from django.contrib.contenttypes.models import ContentType

class UserBasicSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = User
        fields = ['id', 'username', 'phone_number','email', 'date_of_birth']
        read_only_fields = ['id',]

class BaseAccountSerializer(serializers.ModelSerializer):
    """Serializer de base pour tous les types de comptes"""
    user = UserBasicSerializer(read_only=True, help_text="Utilisateur associé au compte")
    phone_number = serializers.CharField(write_only=True, required=False, help_text="Numéro de téléphone de l'utilisateur")
    balance = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    account_number = serializers.CharField(read_only=True)
    
    class Meta:
        fields = [
            'id', 'user', 'phone_number', 'account_number', 'balance', 
            'status', 'created_at'
        ]
        read_only_fields = ['id', 'account_number', 'balance', 'created_at']
    
    def validate(self, attrs):
        # Validation : soit user_id soit phone_number doit être fourni
        if not attrs.get('phone_number'):
            raise serializers.ValidationError("Fournissez phone_number pour creer un compte")
        
        return attrs
    
    def create(self, validated_data):
        # Utiliser la base de données depuis le contexte
        bank_db = self.context.get('bank_db', 'default')

        account_number = self.Meta.model.generate_account_number()
        validated_data['account_number'] = account_number
        print(f"validate data \n{validated_data}")
        # Chercher l'utilisateur via phone_number
        phone_number = validated_data.pop('phone_number', None)
        if phone_number:
            print(f"Using database: {bank_db} for phone number: {phone_number}")
            try:
                user = User.objects.db_manager(bank_db).get(phone_number=phone_number)
                validated_data['user'] = user
                
                if user:
                # Vérifier s'il existe déjà un compte agence pour cet utilisateur
                    exists = self.Meta.model.objects.db_manager(bank_db).filter(user=user).exists()
                    if exists:
                        raise serializers.ValidationError("Cet utilisateur a déjà un compte de ce type.")
            except User.DoesNotExist:
                raise serializers.ValidationError(f"Aucun utilisateur trouvé avec le numéro {phone_number}")
        
        # ✅ Crée l'objet dans la base via db_manager
        return self.Meta.model.objects.db_manager(bank_db).create(**validated_data)

# class PersonalAccountSerializer(BaseAccountSerializer):
#     """Serializer pour les comptes personnels"""
    
#     class Meta(BaseAccountSerializer.Meta):
#         model = PersonalAccount
#         fields = BaseAccountSerializer.Meta.fields

class BusinessAccountSerializer(BaseAccountSerializer):
    """Serializer pour les comptes business"""
    
    class Meta(BaseAccountSerializer.Meta):
        model = BusinessAccount
        fields = BaseAccountSerializer.Meta.fields + [
            'registration_number', 'tax_id', 'code'
        ]
        read_only_fields = BaseAccountSerializer.Meta.read_only_fields + ['code']
    
    def create(self, validated_data):
        
        bank_db = self.context.get('bank_db', 'default')
        # Générer automatiquement le code pour business
        if not validated_data.get('code'):
            validated_data['code'] = AgencyAccount.objects.db_manager(bank_db).generate_unique_code()
        return super().create(validated_data)

class AgencyAccountSerializer(BaseAccountSerializer):
    """Serializer pour les comptes agence"""
    
    class Meta(BaseAccountSerializer.Meta):
        model = AgencyAccount
        fields = BaseAccountSerializer.Meta.fields + [
            'registration_number', 'tax_id', 'code', 
            'deposit_porcentage', 'retrai_percentage'
        ]
        read_only_fields = BaseAccountSerializer.Meta.read_only_fields + ['code']
    
    def validate_deposit_porcentage(self, value):
        if value is not None and (value < 0 or value > 100):
            raise serializers.ValidationError("Le pourcentage de dépôt doit être entre 0 et 100")
        return value
    
    def validate_retrai_percentage(self, value):
        if value is not None and (value < 0 or value > 100):
            raise serializers.ValidationError("Le pourcentage de retrait doit être entre 0 et 100")
        return value
    
    def create(self, validated_data):
        bank_db = self.context.get('bank_db', 'default')
        print(f"validate data agency \n{validated_data}")
        # Générer automatiquement le code si absent
        if not validated_data.get('code'):
            validated_data['code'] = AgencyAccount.objects.db_manager(bank_db).generate_unique_code()

        return super().create(validated_data)


class InternAccountSerializer(serializers.ModelSerializer):
    """Serializer pour les comptes internes - pas d'utilisateur associé"""
    
    class Meta:
        model = InternAccount
        fields = [ 'purpose']
    
    def create(self, validated_data):
        
        bank_db = self.context.get('bank_db', 'default')
        print("bank db " + bank_db)
        # Générer automatiquement le numéro de compte
        account_number = InternAccount.generate_account_number()
        validated_data['account_number'] = account_number
        # Pas d'utilisateur pour les comptes internes
        validated_data['user'] = None
        return InternAccount.objects.db_manager(bank_db).create(**validated_data)

# Serializers pour les listes et détails
class ClientAccountListSerializer(serializers.ModelSerializer):
    """Serializer simplifié pour la liste des comptes personnels"""
    user = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = PersonalAccount
        fields = [
            'id', 'user', 'account_number', 'balance', 
            'status', 'created_at'
        ]

class BusinessAccountListSerializer(serializers.ModelSerializer):
    """Serializer simplifié pour la liste des comptes business"""
    user = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = BusinessAccount
        fields = ['id', 'account_number', 'balance', 'status','user', 'code', 'registration_number','tax_id', 'created_at']
    
    

class AgencyAccountListSerializer(serializers.ModelSerializer):
    """Serializer simplifié pour la liste des comptes agence"""
    user = UserBasicSerializer(read_only=True)
    
    class Meta:
        model = AgencyAccount
        fields = ['id', 'account_number', 'balance', 'status','user', 'code', 'registration_number','tax_id','deposit_porcentage','retrai_percentage','created_at']
    
    

class InternAccountListSerializer(serializers.ModelSerializer):
    """Serializer simplifié pour la liste des comptes internes - pas d'utilisateur"""
    purpose_label = serializers.CharField(source='get_purpose_display', read_only=True)
    
    class Meta:
        model = InternAccount
        fields = ['id', 'account_number', 'balance', 'status', 'purpose', 'purpose_label', 'created_at']
        
class SimpleAccountSerializer(serializers.Serializer):
    """Serializer simplifié pour les comptes dans les transactions"""
    account_number = serializers.CharField(read_only=True)
    username = serializers.CharField(read_only=True, allow_null=True)
    phone_number = serializers.CharField(read_only=True, allow_null=True)


class TransactionListSerializer(serializers.ModelSerializer):
    """Serializer pour la liste des transactions avec infos essentielles des comptes"""
    source_account = serializers.SerializerMethodField(read_only=True)
    destination_account = serializers.SerializerMethodField(read_only=True)
    type = serializers.CharField(source='get_type_display', read_only=True)
    status = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Transaction
        fields = [
            'id', 'type', 'date', 'status', 'amount',
            'source_account', 'destination_account'
        ]

    def get_account_details(self, content_type_id_mod, account_id):
        """Méthode pour récupérer les détails d’un compte à partir des IDs"""
        if not content_type_id_mod or not account_id:
            return {
                'account_number': 'DONNEES MANQUANTES',
                'username': None,
                'phone_number': None,
                'error': f'ContentType ID: {content_type_id_mod}, Account ID: {account_id}'
            }

        try:
            bank_db = self.context.get('bank_db', 'default')
            content_type_mod = ContentType.objects.using(bank_db).get(id=content_type_id_mod)
             # Import des modèles
            from apps.accounts.models import PersonalAccount, InternAccount, BusinessAccount, AgencyAccount

            model_mapping = {
                'personalaccount': PersonalAccount,
                'internaccount': InternAccount,
                'businessaccount': BusinessAccount,
                'agencyaccount': AgencyAccount,
            }

            model_name = content_type_mod.model.lower()
            model_class = model_mapping.get(model_name)

            if not model_class:
                return {
                    'account_number': 'MODELE INTROUVABLE',
                    'username': None,
                    'phone_number': None,
                    'error': f'Model: {content_type_mod.model} non supporté'
                }

            account_obj = model_class.objects.using(bank_db).get(id=account_id)

            if model_name == 'internaccount':
                return {
                    'account_number': account_obj.account_number,
                    'username': None,
                    'phone_number': None
                }

            account_obj = model_class.objects.using(bank_db).select_related('user').get(id=account_id)

            account_data = {
                'account_number': account_obj.account_number,
                'username': account_obj.user.username if account_obj.user else None,
                'phone_number': account_obj.user.phone_number if account_obj.user else None
            }

            serializer = SimpleAccountSerializer(account_data)
            return serializer.data

        except ContentType.DoesNotExist:
            return {
                'account_number': 'CONTENTTYPE INTROUVABLE',
                'username': None,
                'phone_number': None,
                'error': f'ContentType ID {content_type_id_mod} introuvable'
            }
        except Exception as e:
            return {
                'account_number': 'ERREUR',
                'username': None,
                'phone_number': None,
                'error': f'ContentType ID: {content_type_id_mod}, Account ID: {account_id}, Erreur: {str(e)}'
            }

    def get_source_account(self, obj):
        return self.get_account_details(obj.source_account_type_id, obj.source_account_id)

    def get_destination_account(self, obj):
        return self.get_account_details(obj.destination_account_type_id, obj.destination_account_id)
