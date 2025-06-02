from decimal import Decimal
from rest_framework import serializers
from apps.accounts.models import Account,DemandeChequiers
from .models import Transaction,Fee,PreTransaction
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from django.http import FileResponse
from reportlab.lib.units import inch
from apps.users.models import User
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
            source_user = User.objects.using(self.bank_db).get(phone_number=source_phone)
            destination_user = User.objects.using(self.bank_db).get(phone_number=destination_phone)
            
            source_account = Account.objects.using(self.bank_db).get(user=source_user, type_account='personnel')
            destination_account = Account.objects.using(self.bank_db).get(user=destination_user, type_account='personnel')
            
            
            try:
                commission_account = Account.objects.using(self.bank_db).get(type_account='intern', user=None,purpose='commission')
            except Account.DoesNotExist:
                raise serializers.ValidationError(f"Le compte Commission n'existe pas dans la base de données {self.bank_db}.")
            
            attrs['source_account'] = source_account
            attrs['destination_account'] = destination_account
            attrs['commission_account'] = commission_account
            
            
            fee_amount = self.fee_calculator.get_fee_from_db(self.bank_db, transaction_type, float(amount))
            
            if fee_amount is None:
                raise serializers.ValidationError(f"Ce type de transaction ({transaction_type}) est désactivé")
                
            attrs['fee_amount'] = Decimal(str(fee_amount))
            
            
            if source_account.balance < (amount + attrs['fee_amount']):
                raise serializers.ValidationError(
                    f"Solde insuffisant. Solde actuel : {source_account.balance}, "
                  
                )
            
            if source_account == destination_account:
                raise serializers.ValidationError("Le compte source et le compte de destination ne peuvent pas être identiques.")
            
            if source_account.status != 'ACTIVE':
                raise serializers.ValidationError("Le compte source n'est pas actif.")
                
            #if destination_account.status != 'ACTIVE':
                #raise serializers.ValidationError("Le compte de destination n'est pas actif.")
                
        except User.DoesNotExist:
            raise serializers.ValidationError(f"Un des numéros de téléphone n'existe pas dans la base de données {self.bank_db}.")
        except Account.DoesNotExist:
            raise serializers.ValidationError(f"Un des utilisateurs n'a pas de personnel wallet associé dans la base de données {self.bank_db}.")
        
        return attrs
    
    def validate_amount(self, value):
        try:
            amount = Decimal(value)
            if amount <= 0:
                raise serializers.ValidationError("Le montant doit être supérieur à zéro.")
            return amount
        except (TypeError, ValueError):
            raise serializers.ValidationError("Format de montant invalide. Doit être un nombre décimal valide.")
    
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
                
                transfer_transaction = Transaction.objects.using(self.bank_db).create(
                    type='transfer',
                    amount=amount,
                    source_account=source_account,
                    destination_account=destination_account,
                    status='pending'
                )
                
                
                if fee_amount > 0:
                    fee_transaction = Transaction.objects.using(self.bank_db).create(
                        type='paiement',
                        amount=fee_amount,
                        source_account=source_account,
                        destination_account=commission_account,
                        status='pending'
                    )
                    
                    
                    Fee.objects.using(self.bank_db).create(
                        transaction=transfer_transaction,
                        amount=fee_amount
                    )
                
              
                source_account.balance -= (amount + fee_amount)
                source_account.save(using=self.bank_db)
                
                
                destination_account.balance += amount
                destination_account.save(using=self.bank_db)
                
              
                if fee_amount > 0:
                    commission_account.balance += fee_amount
                    commission_account.save(using=self.bank_db)
                
              
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
    pre_transaction_code = serializers.CharField(required=True)  # Code de la pré-transaction

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
            client_user = User.objects.using(self.bank_db).get(phone_number=client_phone)
            agent_user = User.objects.using(self.bank_db).get(phone_number=agent_phone)

            client_account = Account.objects.using(self.bank_db).get(user=client_user, type_account='personnel')
            agent_account = Account.objects.using(self.bank_db).get(user=agent_user, type_account='agency')
            commission_account = Account.objects.using(self.bank_db).get(type_account='intern', purpose='commission', user=None)

            attrs['client_account'] = client_account
            attrs['agent_account'] = agent_account
            attrs['commission_account'] = commission_account

            fee_amount = self.fee_calculator.get_fee_from_db(self.bank_db, transaction_type, float(amount))

            if fee_amount is None:
                raise serializers.ValidationError(f"Ce type de transaction ({transaction_type}) est désactivé.")

            attrs['fee_amount'] = Decimal(str(fee_amount))

          

        except User.DoesNotExist:
            raise serializers.ValidationError(f"L'un des numéros de téléphone n'existe pas dans la base {self.bank_db}.")
        except Account.DoesNotExist:
            raise serializers.ValidationError(f"Un compte requis est introuvable dans la base {self.bank_db}.")

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
                # Marquer d'abord la pré-transaction comme utilisée
                pre_transaction.is_used = True
                pre_transaction.save(using=self.bank_db)
                
                retrait_transaction = Transaction.objects.using(self.bank_db).create(
                    type='withdrawal',
                    amount=amount,
                    source_account=client_account,
                    destination_account=agent_account,
                    status='pending'
                )

                commission_percentage = Decimal(agent_account.retrai_percentage or 0)
                agent_fee = (fee_amount * commission_percentage) / 100
                commission_fee = fee_amount - agent_fee

                agent_fee_transaction = Transaction.objects.using(self.bank_db).create(
                    type='paiement',
                    amount=agent_fee,
                    source_account=client_account,
                    destination_account=agent_account,
                    status='pending'
                )

                commission_fee_transaction = Transaction.objects.using(self.bank_db).create(
                    type='paiement',
                    amount=commission_fee,
                    source_account=client_account,
                    destination_account=commission_account,
                    status='pending'
                )

                Fee.objects.using(self.bank_db).create(
                    transaction=retrait_transaction,
                    amount=fee_amount
                )
                
                # Mettre à jour les soldes
                client_account.balance -= (amount + fee_amount)
                client_account.save(using=self.bank_db)

                agent_account.balance += (amount + agent_fee)
                agent_account.save(using=self.bank_db)

                commission_account.balance += commission_fee
                commission_account.save(using=self.bank_db)

                # Marquer les transactions comme réussies
                retrait_transaction.status = 'success'
                retrait_transaction.save(using=self.bank_db)

                if agent_fee_transaction:
                    agent_fee_transaction.status = 'success'
                    agent_fee_transaction.save(using=self.bank_db)

                commission_fee_transaction.status = 'success'
                commission_fee_transaction.save(using=self.bank_db)

                return retrait_transaction

        except Exception as e:
            if retrait_transaction:
                retrait_transaction.status = 'failure'
                retrait_transaction.save(using=self.bank_db)
            if agent_fee_transaction:
                agent_fee_transaction.status = 'failure'
                agent_fee_transaction.save(using=self.bank_db)
            if commission_fee_transaction:
                commission_fee_transaction.status = 'failure'
                commission_fee_transaction.save(using=self.bank_db)

            raise serializers.ValidationError(f"Échec de la transaction de retrait : {str(e)}")

# class RetraitTransactionSerializer(serializers.ModelSerializer):
#     client_phone = serializers.CharField()
#     agent_phone = serializers.CharField()

#     class Meta:
#         model = Transaction
#         fields = ['type', 'amount', 'client_phone', 'agent_phone']

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.bank_db = self.context.get('bank_db')
#         self.fee_calculator = FeeCalculatorAPI()

#     def validate(self, attrs):
#         client_phone = attrs.get('client_phone')
#         agent_phone = attrs.get('agent_phone')
#         amount = attrs.get('amount')
#         transaction_type = attrs.get('type')

#         try:
#             client_user = User.objects.using(self.bank_db).get(phone_number=client_phone)
#             agent_user = User.objects.using(self.bank_db).get(phone_number=agent_phone)

#             client_account = Account.objects.using(self.bank_db).get(user=client_user, type_account='personnel')
#             agent_account = Account.objects.using(self.bank_db).get(user=agent_user, type_account='agency')
#             commission_account = Account.objects.using(self.bank_db).get(type_account='intern', purpose='commission', user=None)

#             attrs['client_account'] = client_account
#             attrs['agent_account'] = agent_account
#             attrs['commission_account'] = commission_account

#             fee_amount = self.fee_calculator.get_fee_from_db(self.bank_db, transaction_type, float(amount))

#             if fee_amount is None:
#                 raise serializers.ValidationError(f"Ce type de transaction ({transaction_type}) est désactivé.")

#             attrs['fee_amount'] = Decimal(str(fee_amount))

#             total_to_deduct = amount + attrs['fee_amount']
#             if client_account.balance < total_to_deduct:
#                 raise serializers.ValidationError(
#                     f"Solde insuffisant. Solde actuel : {client_account.balance}, "
#                     f"Total requis : {total_to_deduct}"
#                 )

#         except User.DoesNotExist:
#             raise serializers.ValidationError(f"L'un des numéros de téléphone n'existe pas dans la base {self.bank_db}.")
#         except Account.DoesNotExist:
#             raise serializers.ValidationError(f"Un compte requis est introuvable dans la base {self.bank_db}.")

#         return attrs

#     def validate_amount(self, value):
#         try:
#             amount = Decimal(value)
#             if amount <= 0:
#                 raise serializers.ValidationError("Le montant doit être supérieur à zéro.")
#             return amount
#         except (TypeError, ValueError):
#             raise serializers.ValidationError("Montant invalide. Utilisez un nombre décimal.")

#     def create(self, validated_data):
#         client_account = validated_data['client_account']
#         agent_account = validated_data['agent_account']
#         commission_account = validated_data['commission_account']
#         amount = validated_data['amount']
#         fee_amount = validated_data['fee_amount']

#         retrait_transaction = None
#         agent_fee_transaction = None
#         commission_fee_transaction = None

#         try:
#             with transaction.atomic(using=self.bank_db):
                
#                 retrait_transaction = Transaction.objects.using(self.bank_db).create(
#                     type='withdrawal',
#                     amount=amount,
#                     source_account=client_account,
#                     destination_account=agent_account,
#                     status='pending'
#                 )

#                 # if agent_account.parent_bank:
                    
#                     #commission_fee = fee_amount
#                     # agent_fee = Decimal('0.00')

#                     # commission_fee_transaction = Transaction.objects.using(self.bank_db).create(
#                     #     type='paiement',
#                     #     amount=commission_fee,
#                     #     source_account=client_account,
#                     #     destination_account=commission_account,
#                     #     status='pending'
#                     # )
#               #  else:
                  
#                 commission_percentage = Decimal(agent_account.retrai_percentage or 0)
#                 agent_fee = (fee_amount * commission_percentage) / 100
#                 commission_fee = fee_amount - agent_fee

#                 agent_fee_transaction = Transaction.objects.using(self.bank_db).create(
#                         type='paiement',
#                         amount=agent_fee,
#                         source_account=client_account,
#                         destination_account=agent_account,
#                         status='pending'
#                     )

#                 commission_fee_transaction = Transaction.objects.using(self.bank_db).create(
#                         type='paiement',
#                         amount=commission_fee,
#                         source_account=client_account,
#                         destination_account=commission_account,
#                         status='pending'
#                     )

                
#                 Fee.objects.using(self.bank_db).create(
#                     transaction=retrait_transaction,
#                     amount=fee_amount
#                 )

                
#                 client_account.balance -= (amount + fee_amount)
#                 client_account.save(using=self.bank_db)

#                 agent_account.balance += (amount + agent_fee)
#                 agent_account.save(using=self.bank_db)

#                 commission_account.balance += commission_fee
#                 commission_account.save(using=self.bank_db)

                
#                 retrait_transaction.status = 'success'
#                 retrait_transaction.save(using=self.bank_db)

#                 if agent_fee_transaction:
#                     agent_fee_transaction.status = 'success'
#                     agent_fee_transaction.save(using=self.bank_db)

#                 commission_fee_transaction.status = 'success'
#                 commission_fee_transaction.save(using=self.bank_db)

#                 return retrait_transaction

#         except Exception as e:
#             if retrait_transaction:
#                 retrait_transaction.status = 'failure'
#                 retrait_transaction.save(using=self.bank_db)
#             if agent_fee_transaction:
#                 agent_fee_transaction.status = 'failure'
#                 agent_fee_transaction.save(using=self.bank_db)
#             if commission_fee_transaction:
#                 commission_fee_transaction.status = 'failure'
#                 commission_fee_transaction.save(using=self.bank_db)

#             raise serializers.ValidationError(f"Échec de la transaction de retrait : {str(e)}")


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
            
            client_user = User.objects.using(self.bank_db).get(phone_number=client_phone)
            client_account = Account.objects.using(self.bank_db).get(user=client_user, type_account='personnel')
            buness_user = User.objects.using(self.bank_db).get(phone_number=destination_phone)
            
            merchant_account = Account.objects.using(self.bank_db).get(user=buness_user, type_account='business')

            
            if client_account.balance < amount:
                raise serializers.ValidationError("Solde insuffisant pour effectuer le paiement.")

          
            attrs.update({
                'client_account': client_account,
                'merchant_account': merchant_account,
            
            })

        except User.DoesNotExist:
            raise serializers.ValidationError("Client introuvable.")
        except Account.DoesNotExist:
            raise serializers.ValidationError("Compte du client ou commerçant introuvable.")

        return attrs

    def create(self, validated_data):
        client_account = validated_data['client_account']
        merchant_account = validated_data['merchant_account']
        amount = validated_data['amount']
        

        try:
            with transaction.atomic(using=self.bank_db):
                
                payment_tx = Transaction.objects.using(self.bank_db).create(
                    type='paiement',
                    amount=amount,
                    source_account=client_account,
                    destination_account=merchant_account,
                    status='pending'
                )

                Fee.objects.using(self.bank_db).create(
                    transaction=payment_tx,
                    amount=amount
                )

                client_account.balance -= (amount)
                client_account.save(using=self.bank_db)

                merchant_account.balance += (amount)
                merchant_account.save(using=self.bank_db)

            
                for tx in [payment_tx]:
                    tx.status = 'success'
                    tx.save(using=self.bank_db)

                return payment_tx

        except Exception as e:
            raise serializers.ValidationError(f"Erreur de payment : {str(e)}")


# class PreTransactionSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = PreTransaction
#         fields = ['client_phone', 'amount']

#     def __init__(self, *args, **kwargs):
#         super().__init__(*args, **kwargs)
#         self.bank_db = self.context.get('bank_db')
#         self.fee_calculator = FeeCalculatorAPI()
#     def validate_amount(self, value):
#         if value <= 0:
#             raise serializers.ValidationError("Le montant doit être supérieur à zéro.")
#         return value

#     def validate(self, data):
#         phone = data.get('client_phone')
#         amount = data.get('amount')

#         try:
#             user = User.objects.using(self.bank_db).get(phone_number=phone)
#             account = Account.objects.using(self.bank_db).get(user=user, type_account='personnel')

            
#             fee = self.fee_calculator.get_fee_from_db(self.bank_db, "withdrawal", amount)
#             if fee is None:
#                 raise serializers.ValidationError("Ce type de transaction est désactivé pour cette banque.")

#             total_required = float(amount) + fee
            
#             if account.balance < total_required:
#                 raise serializers.ValidationError(
#                     f"Solde insuffisant : {account.balance} MRU disponible, {total_required} MRU requis (montant + frais)."
#                 )

#         except User.DoesNotExist:
#             raise serializers.ValidationError("Utilisateur introuvable.")
#         except Account.DoesNotExist:
#             raise serializers.ValidationError("Compte introuvable.")
#         except ValueError as e:
#             raise serializers.ValidationError(str(e))

#         return data

#     def create(self, validated_data):
#         bank_db = self.bank_db
#         instance = PreTransaction(**validated_data)
#         instance.save(using=bank_db)
#         return instance
class PreTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PreTransaction
        fields = [ 'client_phone', 'amount']
        
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
            account = Account.objects.using(self.bank_db).get(user=user, type_account='personnel')
            
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

        except User.DoesNotExist:
            raise serializers.ValidationError("Utilisateur introuvable.")
        except Account.DoesNotExist:
            raise serializers.ValidationError("Compte introuvable.")
        except ValueError as e:
            raise serializers.ValidationError(str(e))

        return data

    def create(self, validated_data):
        bank_db = self.bank_db
        
      
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
            raise serializers.ValidationError({"client_phone": f"Utilisateur client avec le numéro {client_phone} introuvable."})

        try:
            agency_user = User.objects.using(self.bank_db).get(phone_number=agency_phone)
        except User.DoesNotExist:
            raise serializers.ValidationError({"agency_phone": f"Utilisateur agence avec le numéro {agency_phone} introuvable."})

        try:
            client_account = Account.objects.using(self.bank_db).get(user=client_user, type_account='personnel')
        except Account.DoesNotExist:
            raise serializers.ValidationError({"client_phone": "Aucun compte 'personnel' associé à ce client."})

        try:
            agency_account = Account.objects.using(self.bank_db).get(user=agency_user, type_account='agency')
        except Account.DoesNotExist:
            raise serializers.ValidationError({"agency_phone": "Aucun compte 'agency' associé à cette agence."})

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
        destination_account = validated_data['destination_account']
        agency_account = validated_data['agency_account']
        amount = validated_data['amount']
        type_transaction = validated_data['type']

        retrai_percentage = agency_account.deposit_porcentage
        fee = Decimal('0.00')
        agency_commission = Decimal('0.00')
        commission_account = None

        if retrai_percentage is not None:
            
            fee = Decimal(str(self.fee_calculator.get_fee_from_db(self.bank_db, "deposit", amount)))

            
            agency_commission = (retrai_percentage * fee) / Decimal('100.0')

            
            try:
                commission_account = Account.objects.using(self.bank_db).get(
                    user=None,
                    type_account='intern',
                    purpose='commission'
                )
            except Account.DoesNotExist:
                raise serializers.ValidationError({"commission_account": "Compte de commission introuvable pour cette banque."})

            if commission_account.balance < agency_commission:
                raise serializers.ValidationError({"fee": "Solde insuffisant sur le compte de commission pour couvrir la part de commission."})

        if agency_account.balance < amount:
            raise serializers.ValidationError({"amount": "Solde insuffisant sur le compte de l'agence."})

        with transaction.atomic(using=self.bank_db):
            
            agency_account.balance -= amount
            agency_account.save(using=self.bank_db)

            
            destination_account.balance += amount
            destination_account.save(using=self.bank_db)

            
            if retrai_percentage is not None:
                
                commission_account.balance -= agency_commission
                commission_account.save(using=self.bank_db)

                
                agency_account.balance += agency_commission
                agency_account.save(using=self.bank_db)

                
                Transaction.objects.using(self.bank_db).create(
                    type='paiement',
                    amount=agency_commission,
                    source_account=commission_account,
                    destination_account=agency_account,
                    status='success'
                )

            
            transaction_obj = Transaction.objects.using(self.bank_db).create(
                type=type_transaction,
                amount=amount,
                source_account=agency_account,
                destination_account=destination_account,
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
            raise serializers.ValidationError({"client_phone": f"Utilisateur client avec le numéro {client_phone} introuvable."})

        try:
            agency_user = User.objects.using(self.bank_db).get(phone_number=agency_phone)
        except User.DoesNotExist:
            raise serializers.ValidationError({"agency_phone": f"Utilisateur agence avec le numéro {agency_phone} introuvable."})

        try:
            client_account = Account.objects.using(self.bank_db).get(user=client_user, type_account='business')
        except Account.DoesNotExist:
            raise serializers.ValidationError({"client_phone": "Aucun compte 'personnel' associé à ce client."})

        try:
            agency_account = Account.objects.using(self.bank_db).get(user=agency_user, type_account='agency')
        except Account.DoesNotExist:
            raise serializers.ValidationError({"agency_phone": "Aucun compte 'agency' associé à cette agence."})
        
        if client_account.balance <amount :
                raise serializers.ValidationError(
                    f"Solde insuffisant. Solde actuel : {client_account.balance}, "
                  #  f"Total requis : {total_to_deduct}"
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
        destination_account = validated_data['destination_account']
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
                commission_account = Account.objects.using(self.bank_db).get(
                    user=None,
                    type_account='intern',
                    purpose='commission'
                )
            except Account.DoesNotExist:
                raise serializers.ValidationError({"commission_account": "Compte de commission introuvable pour cette banque."})

            if commission_account.balance < agency_commission:
                raise serializers.ValidationError({"fee": "Solde insuffisant sur le compte de commission pour couvrir la part de commission."})

        if agency_account.balance < amount:
            raise serializers.ValidationError({"amount": "Solde insuffisant sur le compte de l'agence."})

        with transaction.atomic(using=self.bank_db):
            
            destination_account.balance -= amount
            destination_account.save(using=self.bank_db)

            agency_account.balance += amount
            agency_account.save(using=self.bank_db)

            
            if retrai_percentage is not None:
                
                commission_account.balance -= agency_commission
                commission_account.save(using=self.bank_db)

                
                agency_account.balance += agency_commission
                agency_account.save(using=self.bank_db)

                
                Transaction.objects.using(self.bank_db).create(
                    type='paiement',
                    amount=agency_commission,
                    source_account=commission_account,
                    destination_account=agency_account,
                    status='success'
                )

            
            transaction_obj = Transaction.objects.using(self.bank_db).create(
                type=type_transaction,
                amount=amount,
                source_account=destination_account,
                destination_account=agency_account,
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