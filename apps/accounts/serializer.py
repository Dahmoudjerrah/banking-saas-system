from rest_framework import serializers, status

from django.db import IntegrityError
from .models import InternAccount


class InternalAccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = InternAccount
        fields = ['account_number', 'balance', 'status', 'purpose']
        read_only_fields = ['account_number', 'status']

    def create(self, validated_data):
        bank_db = self.context.get('bank_db')
        purpose = validated_data.get('purpose')

        # Validation du purpose avec les choix du modèle InternAccount
        if purpose not in dict(InternAccount.PURPOSE_CHOICES):
            raise serializers.ValidationError(
                {"purpose": "Type de finalité invalide pour un compte interne."}
            )

        try:
            # Génération du numéro de compte
            account_number = InternAccount.generate_account_number()
            
            # Création du compte interne avec le nouveau modèle
            internal_account = InternAccount.objects.db_manager(bank_db).create(
                user=None,
                account_number=account_number,
                purpose=purpose,
                balance=validated_data.get('balance', 0),
                status='ACTIVE'
            )

            return internal_account

        except IntegrityError:
            raise serializers.ValidationError("Erreur lors de la création du compte interne.")


