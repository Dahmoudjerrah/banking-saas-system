from decimal import Decimal, InvalidOperation
from rest_framework import serializers
from apps.accounts.models import PersonalAccount,InternAccount,AgencyAccount,BusinessAccount
from .models import Transaction,Fee,PreTransaction
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from django.http import FileResponse
from reportlab.lib.units import inch
from apps.users.models import User
from django.contrib.contenttypes.models import ContentType
import io
from ..accounts.views import FeeCalculatorAPI
from django.db import transaction

class TransferTransactionSerializer(serializers.ModelSerializer):
    source_phone = serializers.CharField()
    destination_phone = serializers.CharField()
    
    class Meta:
        model = Transaction
        fields = ['type', 'amount', 'source_phone', 'destination_phone']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bank_db = self.context.get('bank_db')
        self.fee_calculator = FeeCalculatorAPI()
    
    def validate(self, attrs):
        source_phone = attrs.get('source_phone')
        destination_phone = attrs.get('destination_phone')
        amount = attrs.get('amount')
        transaction_type = attrs.get('type')
        
        try:
            # Récupération des utilisateurs
            source_user = User.objects.using(self.bank_db).get(phone_number=source_phone)
            destination_user = User.objects.using(self.bank_db).get(phone_number=destination_phone)
            
            # Récupération des comptes personnels
            source_account = PersonalAccount.objects.using(self.bank_db).get(user=source_user)
            destination_account = PersonalAccount.objects.using(self.bank_db).get(user=destination_user)
            
            # Récupération du compte de commission
            commission_account = InternAccount.objects.using(self.bank_db).get(
                purpose='commission', 
                user=None
            )
            
            attrs['source_account'] = source_account
            attrs['destination_account'] = destination_account
            attrs['commission_account'] = commission_account
            
            # Calcul des frais
            fee_amount = self.fee_calculator.get_fee_from_db(
                self.bank_db, transaction_type, float(amount)
            )
            
            if fee_amount is None:
                raise serializers.ValidationError(
                    f"Ce type de transaction ({transaction_type}) est désactivé"
                )
                
            attrs['fee_amount'] = Decimal(str(fee_amount))
            
            # Vérifications
            if source_account.balance < (amount + attrs['fee_amount']):
                raise serializers.ValidationError(
                    f"Solde insuffisant. Solde actuel : {source_account.balance}"
                )
            
            if source_account.id == destination_account.id:
                raise serializers.ValidationError(
                    "Le compte source et le compte de destination ne peuvent pas être identiques."
                )
            
            if source_account.status != 'ACTIVE':
                raise serializers.ValidationError("Le compte source n'est pas actif.")
                
        except User.DoesNotExist:
            raise serializers.ValidationError(
                f"Un des numéros de téléphone n'existe pas dans la base de données {self.bank_db}."
            )
        except PersonalAccount.DoesNotExist:
            raise serializers.ValidationError(
                f"Un des utilisateurs n'a pas de compte personnel dans la base de données {self.bank_db}."
            )
        except InternAccount.DoesNotExist:
            raise serializers.ValidationError(
                f"Le compte Commission n'existe pas dans la base de données {self.bank_db}."
            )
        
        return attrs
    
    def validate_amount(self, value):
        try:
            amount = Decimal(value)
            if amount <= 0:
                raise serializers.ValidationError("Le montant doit être supérieur à zéro.")
            return amount
        except (TypeError, ValueError):
            raise serializers.ValidationError(
                "Format de montant invalide. Doit être un nombre décimal valide."
            )
    
    def create(self, validated_data):
        source_account = validated_data['source_account']
        destination_account = validated_data['destination_account']
        commission_account = validated_data['commission_account']
        amount = validated_data['amount']
        fee_amount = validated_data['fee_amount']
        
        transfer_transaction = None
        fee_transaction = None
        
        try:
            with transaction.atomic(using=self.bank_db):
                # ContentTypes pour les comptes
                personal_account_ct = ContentType.objects.get_for_model(PersonalAccount)
                intern_account_ct = ContentType.objects.get_for_model(InternAccount)
                
                # Transaction de transfert
                transfer_transaction = Transaction.objects.using(self.bank_db).create(
                    type='transfer',
                    amount=amount,
                    source_account_type=personal_account_ct,
                    source_account_id=source_account.id,
                    destination_account_type=personal_account_ct,
                    destination_account_id=destination_account.id,
                    status='pending'
                )
                
                # Transaction de frais
                if fee_amount > 0:
                    fee_transaction = Transaction.objects.using(self.bank_db).create(
                        type='paiement',
                        amount=fee_amount,
                        source_account_type=personal_account_ct,
                        source_account_id=source_account.id,
                        destination_account_type=intern_account_ct,
                        destination_account_id=commission_account.id,
                        status='pending'
                    )
                    
                    Fee.objects.using(self.bank_db).create(
                        transaction=transfer_transaction,
                        amount=fee_amount
                    )
                
                # Mise à jour des soldes
                source_account.balance -= (amount + fee_amount)
                source_account.save(using=self.bank_db)
                
                destination_account.balance += amount
                destination_account.save(using=self.bank_db)
                
                if fee_amount > 0:
                    commission_account.balance += fee_amount
                    commission_account.save(using=self.bank_db)
                
                # Statut success
                transfer_transaction.status = 'success'
                transfer_transaction.save(using=self.bank_db)
                
                if fee_transaction:
                    fee_transaction.status = 'success'
                    fee_transaction.save(using=self.bank_db)
                
                return transfer_transaction
                
        except Exception as e:
            if transfer_transaction:
                transfer_transaction.status = 'failure'
                transfer_transaction.save(using=self.bank_db)
            
            if fee_transaction:
                fee_transaction.status = 'failure'
                fee_transaction.save(using=self.bank_db)
                
            raise serializers.ValidationError(f"Échec de la transaction de transfert : {str(e)}")

class RetraitTransactionSerializer(serializers.ModelSerializer):
    client_phone = serializers.CharField()
    agent_phone = serializers.CharField()
    pre_transaction_code = serializers.CharField(required=True)

    class Meta:
        model = Transaction
        fields = ['type', 'amount', 'client_phone', 'agent_phone', 'pre_transaction_code']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bank_db = self.context.get('bank_db')
        self.fee_calculator = FeeCalculatorAPI()

    def validate(self, attrs):
        client_phone = attrs.get('client_phone')
        agent_phone = attrs.get('agent_phone')
        amount = attrs.get('amount')
        transaction_type = attrs.get('type')
        pre_transaction_code = attrs.get('pre_transaction_code')

        # Validation de la pré-transaction
        try:
            pre_transaction = PreTransaction.objects.using(self.bank_db).get(
                code=pre_transaction_code,
                client_phone=client_phone,
                is_used=False
            )
            
            if not pre_transaction.is_active():
                raise serializers.ValidationError("La pré-transaction a expiré. Veuillez en créer une nouvelle.")
                
            if pre_transaction.amount != amount:
                raise serializers.ValidationError(
                    f"Le montant du retrait ({amount}) ne correspond pas à celui de la pré-transaction ({pre_transaction.code})."
                )
                
            attrs['pre_transaction'] = pre_transaction
            
        except PreTransaction.DoesNotExist:
            raise serializers.ValidationError("Pré-transaction invalide, déjà utilisée ou expirée.")

        try:
            # Récupération des utilisateurs
            client_user = User.objects.using(self.bank_db).get(phone_number=client_phone)
            agent_user = User.objects.using(self.bank_db).get(phone_number=agent_phone)

            # Récupération des comptes avec les nouveaux modèles
            client_account = PersonalAccount.objects.using(self.bank_db).get(user=client_user)
            agent_account = AgencyAccount.objects.using(self.bank_db).get(user=agent_user)
            commission_account = InternAccount.objects.using(self.bank_db).get(
                purpose='commission', 
                user=None
            )

            attrs['client_account'] = client_account
            attrs['agent_account'] = agent_account
            attrs['commission_account'] = commission_account

            # Calcul des frais
            fee_amount = self.fee_calculator.get_fee_from_db(
                self.bank_db, transaction_type, float(amount)
            )

            if fee_amount is None:
                raise serializers.ValidationError(
                    f"Ce type de transaction ({transaction_type}) est désactivé."
                )

            attrs['fee_amount'] = Decimal(str(fee_amount))

        except User.DoesNotExist:
            raise serializers.ValidationError(
                f"L'un des numéros de téléphone n'existe pas dans la base {self.bank_db}."
            )
        except PersonalAccount.DoesNotExist:
            raise serializers.ValidationError(
                f"Le client n'a pas de compte personnel dans la base {self.bank_db}."
            )
        except AgencyAccount.DoesNotExist:
            raise serializers.ValidationError(
                f"L'agent n'a pas de compte d'agence dans la base {self.bank_db}."
            )
        except InternAccount.DoesNotExist:
            raise serializers.ValidationError(
                f"Le compte Commission n'existe pas dans la base {self.bank_db}."
            )

        return attrs

    def validate_amount(self, value):
        try:
            amount = Decimal(value)
            if amount <= 0:
                raise serializers.ValidationError("Le montant doit être supérieur à zéro.")
            return amount
        except (TypeError, ValueError):
            raise serializers.ValidationError("Montant invalide. Utilisez un nombre décimal.")

    def create(self, validated_data):
        client_account = validated_data['client_account']
        agent_account = validated_data['agent_account']
        commission_account = validated_data['commission_account']
        amount = validated_data['amount']
        fee_amount = validated_data['fee_amount']
        pre_transaction = validated_data['pre_transaction']

        retrait_transaction = None
        agent_fee_transaction = None
        commission_fee_transaction = None

        try:
            with transaction.atomic(using=self.bank_db):
                # ContentTypes pour les comptes - récupération depuis la bonne base
                try:
                    personal_account_ct = ContentType.objects.using(self.bank_db).get(
                        app_label='accounts', model='personalaccount'
                    )
                    agency_account_ct = ContentType.objects.using(self.bank_db).get(
                        app_label='accounts', model='agencyaccount'
                    )
                    intern_account_ct = ContentType.objects.using(self.bank_db).get(
                        app_label='accounts', model='internaccount'
                    )
                except ContentType.DoesNotExist:
                    # Fallback vers la base principale si pas trouvé
                    personal_account_ct = ContentType.objects.get_for_model(PersonalAccount)
                    agency_account_ct = ContentType.objects.get_for_model(AgencyAccount)
                    intern_account_ct = ContentType.objects.get_for_model(InternAccount)

                # Calcul de la répartition des frais
                commission_percentage = Decimal(agent_account.retrai_percentage or 0)
                agent_fee = (fee_amount * commission_percentage) / 100
                commission_fee = fee_amount - agent_fee

                # Vérification du solde client avant toute opération
                total_debit = amount + fee_amount
                if client_account.balance < total_debit:
                    raise serializers.ValidationError(
                        f"Solde insuffisant. Solde disponible: {client_account.balance}, "
                        f"Montant requis: {total_debit} (retrait: {amount} + frais: {fee_amount})"
                    )

                # Marquer la pré-transaction comme utilisée
                pre_transaction.is_used = True
                pre_transaction.save(using=self.bank_db)
                
                # Mettre à jour les soldes
                client_account.balance -= total_debit
                client_account.save(using=self.bank_db)

                agent_account.balance += (amount + agent_fee)
                agent_account.save(using=self.bank_db)

                if commission_fee > 0:
                    commission_account.balance += commission_fee
                    commission_account.save(using=self.bank_db)

                # Transaction de retrait principal
                retrait_transaction = Transaction.objects.using(self.bank_db).create(
                    type='withdrawal',
                    amount=amount,
                    source_account_type=personal_account_ct,
                    source_account_id=client_account.id,
                    destination_account_type=agency_account_ct,
                    destination_account_id=agent_account.id,
                    status='success'
                )

                # Transaction des frais agent
                if agent_fee > 0:
                    agent_fee_transaction = Transaction.objects.using(self.bank_db).create(
                        type='paiement',
                        amount=agent_fee,
                        source_account_type=personal_account_ct,
                        source_account_id=client_account.id,
                        destination_account_type=agency_account_ct,
                        destination_account_id=agent_account.id,
                        status='success'
                    )

                # Transaction des frais commission
                if commission_fee > 0:
                    commission_fee_transaction = Transaction.objects.using(self.bank_db).create(
                        type='paiement',
                        amount=commission_fee,
                        source_account_type=personal_account_ct,
                        source_account_id=client_account.id,
                        destination_account_type=intern_account_ct,
                        destination_account_id=commission_account.id,
                        status='success'
                    )

                # Créer l'enregistrement des frais
                Fee.objects.using(self.bank_db).create(
                    transaction=retrait_transaction,
                    amount=fee_amount
                )

                return retrait_transaction

        except Exception as e:
            # Les transactions seront automatiquement rollback grâce à transaction.atomic()
            raise serializers.ValidationError(f"Échec de la transaction de retrait : {str(e)}")
        
class MerchantPaymentSerializer(serializers.Serializer):
    client_phone = serializers.CharField()
    destination_phone = serializers.CharField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bank_db = self.context.get('bank_db')
        
    def validate(self, attrs):
        client_phone = attrs.get('client_phone')
        destination_phone = attrs.get('destination_phone')
        amount = attrs.get('amount')
        
        try:
            # Récupération des utilisateurs
            client_user = User.objects.using(self.bank_db).get(phone_number=client_phone)
            business_user = User.objects.using(self.bank_db).get(phone_number=destination_phone)
            
            # Récupération des comptes avec les nouveaux modèles
            client_account = PersonalAccount.objects.using(self.bank_db).get(user=client_user)
            merchant_account = BusinessAccount.objects.using(self.bank_db).get(user=business_user)
            
            # Vérification du solde
            if client_account.balance < amount:
                raise serializers.ValidationError("Solde insuffisant pour effectuer le paiement.")
            
            # Ajout des comptes aux données validées
            attrs.update({
                'client_account': client_account,
                'merchant_account': merchant_account,
            })
            
        except User.DoesNotExist:
            raise serializers.ValidationError("Client ou marchand introuvable.")
        except PersonalAccount.DoesNotExist:
            raise serializers.ValidationError("Compte personnel du client introuvable.")
        except BusinessAccount.DoesNotExist:
            raise serializers.ValidationError("Compte business du marchand introuvable.")
        
        return attrs

    def create(self, validated_data):
        client_account = validated_data['client_account']
        merchant_account = validated_data['merchant_account']
        amount = validated_data['amount']
        
        try:
            with transaction.atomic(using=self.bank_db):
                # ContentTypes pour les comptes - récupération depuis la bonne base
                try:
                    personal_account_ct = ContentType.objects.using(self.bank_db).get(
                        app_label='accounts', model='personalaccount'
                    )
                    business_account_ct = ContentType.objects.using(self.bank_db).get(
                        app_label='accounts', model='businessaccount'
                    )
                except ContentType.DoesNotExist:
                    # Fallback vers la base principale si pas trouvé
                    personal_account_ct = ContentType.objects.get_for_model(PersonalAccount)
                    business_account_ct = ContentType.objects.get_for_model(BusinessAccount)
                
                # Mettre à jour les soldes
                client_account.balance -= amount
                client_account.save(using=self.bank_db)
                
                merchant_account.balance += amount
                merchant_account.save(using=self.bank_db)
                
                # Créer la transaction de paiement
                payment_tx = Transaction.objects.using(self.bank_db).create(
                    type='paiement',
                    amount=amount,
                    source_account_type=personal_account_ct,
                    source_account_id=client_account.id,
                    destination_account_type=business_account_ct,
                    destination_account_id=merchant_account.id,
                    status='success'
                )
                
                # Créer l'enregistrement des frais (ici le montant du paiement)
                Fee.objects.using(self.bank_db).create(
                    transaction=payment_tx,
                    amount=amount
                )
                
                return payment_tx
                
        except Exception as e:
            raise serializers.ValidationError(f"Erreur de paiement : {str(e)}")


class PreTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreTransaction
        fields = ['client_phone', 'amount']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bank_db = self.context.get('bank_db')
        self.fee_calculator = FeeCalculatorAPI()
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Le montant doit être supérieur à zéro.")
        return value

    def validate(self, data):
        phone = data.get('client_phone')
        amount = data.get('amount')

        try:
            user = User.objects.using(self.bank_db).get(phone_number=phone)
            account = PersonalAccount.objects.using(self.bank_db).get(user=user)
            
            fee = self.fee_calculator.get_fee_from_db(self.bank_db, "withdrawal", float(amount))
            if fee is None:
                raise serializers.ValidationError("Ce type de transaction est désactivé pour cette banque.")

            total_required = Decimal(str(amount)) + Decimal(str(fee))
            
            available_balance, reserved_amount = calculate_available_balance(
                self.bank_db, phone, account.balance, self.fee_calculator
            )
            
            if available_balance < total_required:
                raise serializers.ValidationError(
                    f"Solde insuffisant en tenant compte des pré-transactions actives : "
                    f"{account.balance} MRU solde total, "
                    f"{reserved_amount} MRU déjà réservés, "
                    f"{available_balance} MRU disponibles, "
                    f"{total_required} MRU nécessaires."
                )

            # Ajouter l'utilisateur aux données validées
            data['user'] = user

        except User.DoesNotExist:
            raise serializers.ValidationError("Utilisateur introuvable.")
        except PersonalAccount.DoesNotExist:
            raise serializers.ValidationError("Compte introuvable.")
        except ValueError as e:
            raise serializers.ValidationError(str(e))

        return data

    def create(self, validated_data):
        bank_db = self.bank_db
        
        # Créer l'instance avec l'utilisateur
        instance = PreTransaction(**validated_data)
        instance.is_used = False
        instance.save(using=bank_db)
        return instance



class PreTransactionRetrieveSerializer(serializers.Serializer):
    client_phone = serializers.CharField(max_length=8)
    code = serializers.CharField(max_length=4)
        
class AllPreTransactionsSerializer(serializers.Serializer):
    
    pass



class DepositTransactionSerializer(serializers.ModelSerializer):
    client_phone = serializers.CharField()
    agency_phone = serializers.CharField()

    class Meta:
        model = Transaction
        fields = ['type', 'amount', 'client_phone', 'agency_phone']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bank_db = self.context.get('bank_db')
        self.fee_calculator = FeeCalculatorAPI()

    def validate(self, attrs):
        client_phone = attrs.get('client_phone')
        agency_phone = attrs.get('agency_phone')

        try:
            client_user = User.objects.using(self.bank_db).get(phone_number=client_phone)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"client_phone": f"Utilisateur client avec le numéro {client_phone} introuvable."}
            )

        try:
            agency_user = User.objects.using(self.bank_db).get(phone_number=agency_phone)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"agency_phone": f"Utilisateur agence avec le numéro {agency_phone} introuvable."}
            )

        try:
            client_account = PersonalAccount.objects.using(self.bank_db).get(user=client_user)
        except PersonalAccount.DoesNotExist:
            raise serializers.ValidationError(
                {"client_phone": "Aucun compte personnel associé à ce client."}
            )

        try:
            agency_account = AgencyAccount.objects.using(self.bank_db).get(user=agency_user)
        except AgencyAccount.DoesNotExist:
            raise serializers.ValidationError(
                {"agency_phone": "Aucun compte d'agence associé à cette agence."}
            )

        attrs['destination_account'] = client_account
        attrs['agency_account'] = agency_account
        return attrs

    def validate_amount(self, value):
        try:
            amount = Decimal(value)
            if amount <= 0:
                raise serializers.ValidationError("Le montant doit être supérieur à zéro.")
            return amount
        except (TypeError, ValueError):
            raise serializers.ValidationError("Montant invalide. Doit être un nombre décimal.")

    def create(self, validated_data):
        destination_account = validated_data['destination_account']  # Client account
        agency_account = validated_data['agency_account']
        amount = validated_data['amount']
        type_transaction = validated_data['type']

        deposit_percentage = agency_account.deposit_porcentage
        fee = Decimal('0.00')
        agency_commission = Decimal('0.00')
        commission_account = None

        if deposit_percentage is not None:
            # Calcul des frais
            fee = Decimal(str(self.fee_calculator.get_fee_from_db(self.bank_db, "deposit", amount)))

            # Calcul de la commission agence
            agency_commission = (deposit_percentage * fee) / Decimal('100.0')

            # Récupération du compte de commission
            try:
                commission_account = InternAccount.objects.using(self.bank_db).get(
                    user=None,
                    purpose='commission'
                )
            except InternAccount.DoesNotExist:
                raise serializers.ValidationError(
                    {"commission_account": "Compte de commission introuvable pour cette banque."}
                )

            if commission_account.balance < agency_commission:
                raise serializers.ValidationError(
                    {"fee": "Solde insuffisant sur le compte de commission pour couvrir la part de commission."}
                )

        if agency_account.balance < amount:
            raise serializers.ValidationError(
                {"amount": "Solde insuffisant sur le compte de l'agence."}
            )

        with transaction.atomic(using=self.bank_db):
            # ContentTypes pour les comptes - récupération depuis la bonne base
            try:
                personal_account_ct = ContentType.objects.using(self.bank_db).get(
                    app_label='accounts', model='personalaccount'
                )
                agency_account_ct = ContentType.objects.using(self.bank_db).get(
                    app_label='accounts', model='agencyaccount'
                )
                intern_account_ct = ContentType.objects.using(self.bank_db).get(
                    app_label='accounts', model='internaccount'
                )
            except ContentType.DoesNotExist:
                # Fallback vers la base principale si pas trouvé
                personal_account_ct = ContentType.objects.get_for_model(PersonalAccount)
                agency_account_ct = ContentType.objects.get_for_model(AgencyAccount)
                intern_account_ct = ContentType.objects.get_for_model(InternAccount)

            # Débiter le compte agence
            agency_account.balance -= amount
            agency_account.save(using=self.bank_db)

            # Créditer le compte client
            destination_account.balance += amount
            destination_account.save(using=self.bank_db)

            # Gestion de la commission agence si applicable
            if deposit_percentage is not None and agency_commission > 0:
                # Débiter le compte commission
                commission_account.balance -= agency_commission
                commission_account.save(using=self.bank_db)

                # Créditer l'agence avec sa commission
                agency_account.balance += agency_commission
                agency_account.save(using=self.bank_db)

                # Créer la transaction de commission
                Transaction.objects.using(self.bank_db).create(
                    type='paiement',
                    amount=agency_commission,
                    source_account_type=intern_account_ct,
                    source_account_id=commission_account.id,
                    destination_account_type=agency_account_ct,
                    destination_account_id=agency_account.id,
                    status='success'
                )

            # Créer la transaction principale de dépôt
            transaction_obj = Transaction.objects.using(self.bank_db).create(
                type=type_transaction,
                amount=amount,
                source_account_type=agency_account_ct,
                source_account_id=agency_account.id,
                destination_account_type=personal_account_ct,
                destination_account_id=destination_account.id,
                status='success'
            )

        return transaction_obj

class RetraitMarchantSerializer(serializers.ModelSerializer):
    client_phone = serializers.CharField()
    agency_phone = serializers.CharField()

    class Meta:
        model = Transaction
        fields = ['type', 'amount', 'client_phone', 'agency_phone']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bank_db = self.context.get('bank_db')
        self.fee_calculator = FeeCalculatorAPI()

    def validate(self, attrs):
        client_phone = attrs.get('client_phone')
        agency_phone = attrs.get('agency_phone')
        amount = attrs.get('amount')

        try:
            client_user = User.objects.using(self.bank_db).get(phone_number=client_phone)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"client_phone": f"Utilisateur client avec le numéro {client_phone} introuvable."}
            )

        try:
            agency_user = User.objects.using(self.bank_db).get(phone_number=agency_phone)
        except User.DoesNotExist:
            raise serializers.ValidationError(
                {"agency_phone": f"Utilisateur agence avec le numéro {agency_phone} introuvable."}
            )

        try:
            client_account = BusinessAccount.objects.using(self.bank_db).get(user=client_user)
        except BusinessAccount.DoesNotExist:
            raise serializers.ValidationError(
                {"client_phone": "Aucun compte business associé à ce client."}
            )

        try:
            agency_account = AgencyAccount.objects.using(self.bank_db).get(user=agency_user)
        except AgencyAccount.DoesNotExist:
            raise serializers.ValidationError(
                {"agency_phone": "Aucun compte d'agence associé à cette agence."}
            )
        
        if client_account.balance < amount:
            raise serializers.ValidationError(
                f"Solde insuffisant. Solde actuel : {client_account.balance}"
            )
            
        attrs['destination_account'] = client_account  # Le compte business (marchand)
        attrs['agency_account'] = agency_account
        return attrs
       
    def validate_amount(self, value):
        try:
            amount = Decimal(value)
            if amount <= 0:
                raise serializers.ValidationError("Le montant doit être supérieur à zéro.")
            return amount
        except (TypeError, ValueError):
            raise serializers.ValidationError("Montant invalide. Doit être un nombre décimal.")

    def create(self, validated_data):
        destination_account = validated_data['destination_account']  # Business account (marchand)
        agency_account = validated_data['agency_account']
        amount = validated_data['amount']
        type_transaction = validated_data['type']

        retrai_percentage = agency_account.retrai_percentage
        fee = Decimal('0.00')
        agency_commission = Decimal('0.00')
        commission_account = None

        if retrai_percentage is not None:
            fee = Decimal(str(self.fee_calculator.get_fee_from_db(self.bank_db, "withdrawal", amount)))
            agency_commission = (retrai_percentage * fee) / Decimal('100.0')
            
            try:
                commission_account = InternAccount.objects.using(self.bank_db).get(
                    user=None,
                    purpose='commission'
                )
            except InternAccount.DoesNotExist:
                raise serializers.ValidationError(
                    {"commission_account": "Compte de commission introuvable pour cette banque."}
                )

            if commission_account.balance < agency_commission:
                raise serializers.ValidationError(
                    {"fee": "Solde insuffisant sur le compte de commission pour couvrir la part de commission."}
                )

        if agency_account.balance < amount:
            raise serializers.ValidationError(
                {"amount": "Solde insuffisant sur le compte de l'agence."}
            )

        with transaction.atomic(using=self.bank_db):
            # ContentTypes pour les comptes
            business_account_ct = ContentType.objects.get_for_model(BusinessAccount)
            agency_account_ct = ContentType.objects.get_for_model(AgencyAccount)
            intern_account_ct = ContentType.objects.get_for_model(InternAccount)

            # Débiter le compte business (marchand)
            destination_account.balance -= amount
            destination_account.save(using=self.bank_db)

            # Créditer le compte agence
            agency_account.balance += amount
            agency_account.save(using=self.bank_db)

            # Gestion de la commission agence si applicable
            if retrai_percentage is not None and agency_commission > 0:
                # Débiter le compte commission
                commission_account.balance -= agency_commission
                commission_account.save(using=self.bank_db)

                # Créditer l'agence avec sa commission
                agency_account.balance += agency_commission
                agency_account.save(using=self.bank_db)

                # Créer la transaction de commission
                Transaction.objects.using(self.bank_db).create(
                    type='paiement',
                    amount=agency_commission,
                    source_account_type=intern_account_ct,
                    source_account_id=commission_account.id,
                    destination_account_type=agency_account_ct,
                    destination_account_id=agency_account.id,
                    status='success'
                )

            # Créer la transaction principale de retrait marchand
            transaction_obj = Transaction.objects.using(self.bank_db).create(
                type=type_transaction,
                amount=amount,
                source_account_type=business_account_ct,
                source_account_id=destination_account.id,
                destination_account_type=agency_account_ct,
                destination_account_id=agency_account.id,
                status='success'
            )

        return transaction_obj

def calculate_available_balance(bank_db, client_phone, account_balance, fee_calculator):
    
    
    pending_pre_transactions = PreTransaction.objects.using(bank_db).filter(
        client_phone=client_phone,
        is_used=False
    )
    
    
    active_pre_transactions = [pt for pt in pending_pre_transactions if pt.is_active()]
    
    
    reserved_amount = Decimal('0.00')
    for pt in active_pre_transactions:
        amount = pt.amount
        fee = fee_calculator.get_fee_from_db(bank_db, "withdrawal", float(amount)) or 0
        reserved_amount += amount + Decimal(str(fee))
    
  
    available_balance = account_balance - reserved_amount
    
    return available_balance, reserved_amount


class RechargeAgencySerializer(serializers.ModelSerializer):
    phone_number = serializers.CharField(max_length=20)
    
    class Meta:
        model = Transaction
        fields = ['amount', 'phone_number']
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.bank_db = self.context.get('bank_db')
        if not self.bank_db:
            raise serializers.ValidationError("Base de données non spécifiée dans le contexte.")
    
    def validate_phone_number(self, value):
        if not value:
            raise serializers.ValidationError("Le numéro de téléphone est requis.")
        
        cleaned_phone = ''.join(filter(str.isdigit, value))
        
        if len(cleaned_phone) < 8:
            raise serializers.ValidationError("Numéro de téléphone invalide.")
        
        return value.strip()
    
    def validate_amount(self, value):
        try:
            amount = Decimal(str(value))
            if amount <= 0:
                raise serializers.ValidationError("Le montant doit être supérieur à zéro.")
          
            return amount
        except (TypeError, ValueError, InvalidOperation):
            raise serializers.ValidationError("Format de montant invalide. Doit être un nombre décimal valide.")
    
    def validate(self, attrs):
        phone_number = attrs.get('phone_number')
        amount = attrs.get('amount')
        
        try:
            # Récupération de l'utilisateur
            try:
                user = User.objects.using(self.bank_db).get(phone_number=phone_number)
            except User.DoesNotExist:
                raise serializers.ValidationError(
                    f"Aucun utilisateur trouvé avec le numéro {phone_number} dans la base de données {self.bank_db}."
                )
            
            # Récupération du compte d'agence avec le nouveau modèle
            try:
                agency_account = AgencyAccount.objects.using(self.bank_db).get(user=user)
            except AgencyAccount.DoesNotExist:
                raise serializers.ValidationError(
                    f"L'utilisateur {phone_number} n'a pas de compte d'agence dans la base de données {self.bank_db}."
                )
            
            # Vérification du statut du compte
            if agency_account.status != 'ACTIVE':
                raise serializers.ValidationError(
                    f"Le compte d'agence de l'utilisateur {phone_number} n'est pas actif. Statut actuel: {agency_account.status}"
                )
            
            # Ajout des données validées
            attrs['user'] = user
            attrs['agency_account'] = agency_account
            
            return attrs
            
        except Exception as e:
            if isinstance(e, serializers.ValidationError):
                raise e
            else:
                raise serializers.ValidationError(f"Erreur lors de la validation : {str(e)}")
    
    def create(self, validated_data):
        user = validated_data['user']
        agency_account = validated_data['agency_account']
        amount = validated_data['amount']
        phone_number = validated_data['phone_number']
        
        recharge_transaction = None
        
        try:
            with transaction.atomic(using=self.bank_db):
                # ContentType pour le compte d'agence
                agency_account_ct = ContentType.objects.get_for_model(AgencyAccount)
                
                # Créer la transaction de recharge
                recharge_transaction = Transaction.objects.using(self.bank_db).create(
                    type='deposit',
                    amount=amount,
                    source_account_type=None,  # Pas de compte source pour une recharge externe
                    source_account_id=None,
                    destination_account_type=agency_account_ct,
                    destination_account_id=agency_account.id,
                    status='pending'
                )
                
                # Mettre à jour le solde de l'agence
                agency_account.balance += amount
                agency_account.save(using=self.bank_db)
                
                # Marquer la transaction comme réussie
                recharge_transaction.status = 'success'
                recharge_transaction.save(using=self.bank_db)
                
                return recharge_transaction
                
        except Exception as e:
            # Gestion des erreurs
            if recharge_transaction:
                try:
                    recharge_transaction.status = 'failure'
                    recharge_transaction.save(using=self.bank_db)
                except Exception:
                    pass
            
            error_message = f"Échec de la recharge d'agence pour {phone_number}: {str(e)}"
            print(f"ERREUR: {error_message}")
            raise serializers.ValidationError(error_message)