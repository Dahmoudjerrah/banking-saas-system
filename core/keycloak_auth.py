# from django.conf import settings
# from keycloak import KeycloakOpenID
# from rest_framework.authentication import BaseAuthentication
# from rest_framework.exceptions import AuthenticationFailed
# from django.contrib.auth import get_user_model
# from apps.banks.models import Bank

# class KeycloakAuthentication(BaseAuthentication):
#     def __init__(self):
#         self.keycloak_openid = KeycloakOpenID(
#             server_url="http://localhost:8180/",
#             client_id="sedad",
#             realm_name="next-realm",
#             client_secret_key="c7fnLz03oqMLhU4mRyg9e56yUoFvzPPx"
#         )

#     def authenticate(self, request):
#         auth_header = request.headers.get('Authorization')
#         if not auth_header or not auth_header.startswith('Bearer '):
#             return None

#         token = auth_header.split(' ')[1]
        
#         try:
#             # Vérifier le token avec Keycloak
#             token_info = self.keycloak_openid.introspect(token)
#             if not token_info.get('active'):
#                 raise AuthenticationFailed('Token inactif')

#             # Récupérer le bank_code depuis les custom claims du token
#             bank_code = token_info.get('bank_code')
#             if not bank_code:
#                 raise AuthenticationFailed('Bank code manquant dans le token')

#             try:
#                 bank = Bank.objects.get(code=bank_code)
#                 request.source_bank = bank
#                 request.source_bank_db = bank.code
#             except Bank.DoesNotExist:
#                 raise AuthenticationFailed('Banque non trouvée')

#             # Récupérer ou créer l'utilisateur
#             UserModel = get_user_model()
#             username = token_info.get('preferred_username')
#             user, created = UserModel.objects.using(bank.code).get_or_create(
#                 username=username,
#                 defaults={
#                     'email': token_info.get('email', ''),
#                     'phone_number': token_info.get('phone_number', '')
#                 }
#             )

#             return user, token_info
#         except Exception as e:
#             raise AuthenticationFailed(str(e))

#     def authenticate_header(self, request):
#         return 'Bearer'