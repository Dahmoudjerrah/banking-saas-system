from rest_framework import serializers, status

from django.db import IntegrityError
from .models import Account


class InternalAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = ['account_number', 'balance', 'status', 'purpose']
        read_only_fields = ['account_number', 'status']

    def create(self, validated_data):
        bank_db = self.context.get('bank_db')
        purpose = validated_data.get('purpose')

        if purpose not in dict(Account.PURPOSE_CHOICES):
            raise serializers.ValidationError({"purpose": "Type de finalité invalide pour un compte interne."})

        try:
            account_number = Account.generate_account_number()
            internal_account = Account.objects.db_manager(bank_db).create(
                user=None,
                account_number=account_number,
                type_account='intern',
                purpose=purpose,
                balance=validated_data.get('balance', 0),
                status='ACTIVE'
            )

            return internal_account

        except IntegrityError:
            raise serializers.ValidationError("Erreur lors de la création du compte interne.")
