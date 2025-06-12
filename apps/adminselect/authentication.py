from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken
from django.contrib.auth import get_user_model

User = get_user_model()

class MultiDatabaseJWTAuthentication(JWTAuthentication):
    """
    Authentification JWT personnalisée pour multi-database
    """
    
    def get_user(self, validated_token):
        """
        Récupère l'utilisateur depuis la bonne base de données
        """
        try:
            user_id = validated_token.get('user_id')
            bank_db = validated_token.get('bank_db', 'default')
            print(user_id)
            print("jwt : " + bank_db)
            if not user_id:
                raise InvalidToken('Token ne contient pas user_id')
            
            # Récupérer l'utilisateur depuis la bonne DB
            user = User.objects.using(bank_db).get(id=user_id)
            
            # if not user.is_active:
            #     raise InvalidToken('Utilisateur inactif')
            
            # Ajouter la base de données à l'utilisateur pour référence
            user._database = bank_db
            
            return user
            
        except User.DoesNotExist:
            raise InvalidToken('Utilisateur non trouvé')
        except Exception as e:
            raise InvalidToken(f'Erreur d\'authentification: {str(e)}')