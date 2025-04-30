import os
import django

# Configurez l'environnement Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saas.settings')
django.setup()

from apps.banks.models import Bank, BankFeature

def init_banks():
    # Créer les banques
    sedad, _ = Bank.objects.get_or_create(name='SEDAD', code='SDD')
    bimbanque, _ = Bank.objects.get_or_create(name='BIMBANQUE', code='BIM')

    # Définir les fonctionnalités
    features = ['transfer', 'withdrawal', 'deposit', 'account_statement', 'card_request', 'cheque_request']

    # Activer toutes les fonctionnalités pour SEDAD
    for feature in features:
        BankFeature.objects.get_or_create(bank=sedad, feature_name=feature, is_active=True)

    # Activer certaines fonctionnalités pour BIMBANQUE
    active_features_bim = ['transfer', 'withdrawal', 'deposit', 'account_statement']
    for feature in features:
        BankFeature.objects.get_or_create(bank=bimbanque, feature_name=feature, is_active=feature in active_features_bim)

    print("Banques et fonctionnalités initialisées avec succès.")

if __name__ == '__main__':
    init_banks()