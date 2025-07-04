import re
from rest_framework import viewsets, status, filters,generics
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.accounts.models import  InternAccount, PersonalAccount, BusinessAccount, AgencyAccount
from apps.adminselect.authentication import MultiDatabaseJWTAuthentication
from apps.adminselect.paginations import CustomPageNumberPagination
from apps.adminselect.permissions import ApiAccessPermission
from apps.adminselect.serializers import CustomRefreshToken, DashboardLoginSerializer, FeeRuleSerializer
from django.db import models
from .serializer import AgencyAccountListSerializer, AgencyAccountSerializer, BusinessAccountListSerializer, BusinessAccountSerializer, ClientAccountListSerializer, InternAccountListSerializer, InternAccountSerializer, TransactionListSerializer
from apps.transactions.models import Fee, FeeRule, PaymentRequest, PreTransaction, Transaction
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum, Count,Avg
from django.utils import timezone
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from django.contrib.contenttypes.models import ContentType
from django.db.models.functions import TruncMonth

from apps.users.models import User
from django.core.exceptions import ObjectDoesNotExist
# from .permissions import RoleBasedPermission
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth.models import Group

class MultiDatabaseViewSetMixin:
    """Mixin pour gérer les bases de données multiples dans les ViewSets"""
    
    def get_database(self):
        """Récupère la base de données à partir de la requête"""
        return getattr(self.request, 'source_bank_db', 'default')
    
    def get_queryset(self):
        """Override pour utiliser la bonne base de données"""
        db = self.get_database()
        if hasattr(self, 'queryset') and self.queryset is not None:
            return self.queryset._clone().using(db)
        return super().get_queryset().using(db)
    
    def get_serializer(self, *args, **kwargs):
        """Passer la base de données au serializer"""
        kwargs['bank_db'] = self.get_database()
        return super().get_serializer(*args, **kwargs)
    
    def perform_create(self, serializer):
        """Créer avec la bonne base de données"""
        db = self.get_database()
        serializer.save(using=db)
    
    def perform_update(self, serializer):
        """Mettre à jour avec la bonne base de données"""
        db = self.get_database()
        serializer.save(using=db)

class DashboardLoginView(APIView):
    """
    Vue de connexion dashboard avec vérifications staff et groupes
    Tokens: 30min access, 16h refresh
    """
    permission_classes = [AllowAny]
   
    def post(self, request, *args, **kwargs):
        # Récupérer la base de données
        bank_db = getattr(request, 'source_bank_db', 'default')
       
        if not bank_db:
            return Response({
                "error": "Base de données bancaire non spécifiée.",
                "code": "DB_NOT_SPECIFIED"
            }, status=status.HTTP_400_BAD_REQUEST)
       
        serializer = DashboardLoginSerializer(
            data=request.data,
            context={'bank_db': bank_db}
        )
       
        if serializer.is_valid():
            user = serializer.validated_data['user']
            user_groups = serializer.validated_data['user_groups']
           
            try:
                # Générer les tokens JWT avec durées personnalisées
                refresh = CustomRefreshToken.for_user(user)
                access = refresh.access_token
               
                # Ajouter des informations personnalisées au token
                access['bank_db'] = bank_db
                access['user_id'] = user.id
                access['username'] = user.username
                access['groups'] = list(user_groups)
                
                # Préparer la réponse avec informations détaillées
                response_data = {
                    "message": "Connexion réussie.",
                    "access": str(access),
                    "refresh": str(refresh),
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "phone_number": user.phone_number,
                        "groups": list(user_groups),
                    }
                }
                
                # Mettre à jour le last_login
                user.save(using=bank_db, update_fields=['last_login'])
                
                return Response(response_data, status=status.HTTP_200_OK)
               
            except Exception as e:
                return Response({
                    "error": f"Erreur lors de la génération du token: {str(e)}",
                    "code": "TOKEN_GENERATION_ERROR"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
       
        return Response({
            "error": "Données de connexion invalides",
            "details": serializer.errors,
            "code": "VALIDATION_ERROR"
        }, status=status.HTTP_400_BAD_REQUEST)

class DashboardRefreshTokenView(APIView):
    """
    Vue pour rafraîchir le token JWT du dashboard
    """
    permission_classes = [AllowAny]
   
    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get('refresh')
       
        if not refresh_token:
            return Response({
                "error": "Token de rafraîchissement requis.",
                "code": "REFRESH_TOKEN_REQUIRED"
            }, status=status.HTTP_400_BAD_REQUEST)
       
        try:
            refresh = CustomRefreshToken(refresh_token)
            
            # Vérifier si le token est encore valide
            # refresh.check_blacklist()
            
            # Générer un nouveau token d'accès
            access = refresh.access_token
           
            # Récupérer la base de données du token ou de la requête
            bank_db = getattr(request, 'source_bank_db', 'default')
           
            # Récupérer l'utilisateur pour vérifier les permissions actuelles
            user_id = refresh.payload.get('user_id')
            if user_id:
                try:
                    user = User.objects.using(bank_db).get(id=user_id)
                    
                    # RE-VÉRIFIER les permissions staff et groupes lors du refresh
                    
                    if not user.is_staff:
                        return Response({
                            "error": "Privilèges staff révoqués.",
                            "code": "STAFF_REVOKED"
                        }, status=status.HTTP_401_UNAUTHORIZED)
                    
                    user_groups = list(user.groups.using(bank_db).values_list('name', flat=True))
                    if not user_groups:
                        return Response({
                            "error": "Groupes utilisateur supprimés.",
                            "code": "GROUPS_REMOVED"
                        }, status=status.HTTP_401_UNAUTHORIZED)
                    
                    # Ajouter les informations au nouveau token
                    access['bank_db'] = bank_db
                    access['user_id'] = user.id
                    access['username'] = user.username
                 
                    
                except User.DoesNotExist:
                    return Response({
                        "error": "Utilisateur introuvable.",
                        "code": "USER_NOT_FOUND"
                    }, status=status.HTTP_401_UNAUTHORIZED)
           
            return Response({
                "access": str(access),
                "refresh": str(refresh),
                
            }, status=status.HTTP_200_OK)
           
        except TokenError as e:
            return Response({
                "error": f"Token invalide: {str(e)}",
                "code": "INVALID_TOKEN"
            }, status=status.HTTP_401_UNAUTHORIZED)
        except Exception as e:
            return Response({
                "error": f"Erreur lors du rafraîchissement: {str(e)}",
                "code": "REFRESH_ERROR"
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)



class BaseAccountListViewWithStats(generics.ListAPIView):
    """Classe de base pour les vues de comptes avec statistiques"""
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status']
    ordering_fields = ['created_at', 'balance']
    ordering = ['-created_at']
    pagination_class = CustomPageNumberPagination
    def get_queryset(self):
        bank_db = getattr(self.request, 'source_bank_db', 'default')
        return self.model.objects.using(bank_db).order_by('-created_at')
    
    def list(self, request, *args, **kwargs):
        """Override pour ajouter un endpoint statistics via query param"""
        # Si le paramètre 'action=statistics' est présent, retourner les stats
        if request.query_params.get('action') == 'statistics':
            return self.get_statistics(request)
        
        # Sinon, comportement normal
        return super().list(request, *args, **kwargs)
    
    def get_statistics(self, request):
        """Statistiques des comptes"""
        queryset = self.get_queryset()
        
        # Appliquer les mêmes filtres que pour la liste
        queryset = self.filter_queryset(queryset)
        
        # Par statut
        by_status = queryset.values('status').annotate(
            count=Count('id'),
            total_balance=Sum('balance')
        )
        
        # Comptes récents
        last_month = timezone.now() - timedelta(days=30)
        new_accounts = queryset.filter(created_at__gte=last_month).count()
        
        # Balance moyenne
        total_count = queryset.count()
        total_balance = queryset.aggregate(Sum('balance'))['balance__sum'] or 0
        average_balance = (total_balance / total_count) if total_count > 0 else 0
        
        response_data = {
            'account_type': self.model.__name__,
            'total_accounts': total_count,
            'total_balance': float(total_balance),
            'average_balance': float(average_balance),
            'by_status': list(by_status),
            'new_accounts_last_month': new_accounts
        }
        
        # Ajouter des stats spécifiques selon le type de compte
        response_data.update(self.get_specific_statistics(queryset))
        
        return Response(response_data)
    
    def get_specific_statistics(self, queryset):
        """Méthode à override pour des statistiques spécifiques par type de compte"""
        return {}


class InternAccountListView(BaseAccountListViewWithStats, generics.CreateAPIView):
    """Vue spéciale pour lister tous les comptes internes avec résumé"""
    # permission_classes = [ApiAccessPermission]
    permission_classes = [ApiAccessPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    model = InternAccount
    filterset_fields = ['status', 'purpose']
    search_fields = ['account_number']
    ordering_fields = ['created_at', 'balance', 'purpose']
    ordering = ['purpose', '-created_at']
    
    def get_serializer_class(self):
        if self.request.method == 'POST':
            return InternAccountSerializer
        return InternAccountListSerializer
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['bank_db'] = getattr(self.request, 'source_bank_db', 'default')
        return context
    
    def perform_create(self, serializer):
        serializer.save()
    
    def get_specific_statistics(self, queryset):
        """Statistiques spécifiques aux comptes internes"""
        # Par objectif/purpose
        by_purpose = queryset.values('purpose').annotate(
            count=Count('id'),
            total_balance=Sum('balance')
        )
        
        return {
            'by_purpose': list(by_purpose),
            'purposes_count': queryset.values('purpose').distinct().count()
        }


class ClientAccountListView(BaseAccountListViewWithStats):
    permission_classes = [ApiAccessPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    serializer_class = ClientAccountListSerializer
    model = PersonalAccount
    search_fields = ['account_number', 'user__email', 'user__phone_number']
    
    def get_specific_statistics(self, queryset):
        """Statistiques spécifiques aux comptes personnels"""
        # Comptes avec/sans utilisateur
        with_user = queryset.filter(user__isnull=False).count()
        without_user = queryset.filter(user__isnull=True).count()
        
        # Top balances
        top_balances = queryset.order_by('-balance')[:5].values(
            'account_number', 'balance', 'user__username'
        )
        
        return {
            'accounts_with_user': with_user,
            'accounts_without_user': without_user,
            'top_balances': list(top_balances)
        }
        
class BlockUnblockClientAccountView(APIView):
    permission_classes = [ApiAccessPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    # permission_classes = [ApiAccessPermission]

    def post(self, request, id):
        bank_db = getattr(request, 'source_bank_db', 'default')
        action = request.data.get('action')

        if action not in ['block', 'unblock']:
            return Response(
                {'detail': "L'action doit être 'block' ou 'unblock'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            account = PersonalAccount.objects.using(bank_db).get(id=id)

            if action == 'block':
                if account.status == 'BLOCKED':
                    print('Le compte est déjà bloqué.')
                    return Response({'detail': 'Le compte est déjà bloqué.'}, status=status.HTTP_200_OK)

                account.status = 'BLOCKED'
                message = f'Compte ID {id} bloqué avec succès.'

            else:  # unblock
                if account.status == 'ACTIVE':
                    return Response({'detail': 'Le compte est déjà actif.'}, status=status.HTTP_200_OK)

                account.status = 'ACTIVE'
                message = f'Compte ID {id} débloqué avec succès.'

            account.save(using=bank_db)
            return Response({'detail': message}, status=status.HTTP_200_OK)

        except PersonalAccount.DoesNotExist:
            return Response({'detail': 'Compte introuvable.'}, status=status.HTTP_404_NOT_FOUND)
        
class ClientAccountNonValiderListView(BaseAccountListViewWithStats):
    permission_classes = [ApiAccessPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    # permission_classes = [ApiAccessPermission]
    serializer_class = ClientAccountListSerializer
    model = PersonalAccount
    search_fields = ['account_number', 'user__email', 'user__phone_number']

    def get_queryset(self):
        bank_db = getattr(self.request, 'source_bank_db', 'default')
        return PersonalAccount.objects.using(bank_db).filter(status='PENDING')


class ValidateClientAccountView(APIView):
    permission_classes = [ApiAccessPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    # permission_classes = [ApiAccessPermission]

    def post(self, request, id):
        bank_db = getattr(request, 'source_bank_db', 'default')

        try:
            account = PersonalAccount.objects.using(bank_db).get(id=id)

            if account.status == 'ACTIVE':
                return Response({'detail': 'Le compte est déjà actif.'}, status=status.HTTP_200_OK)

            if account.status == 'BLOCKED':
                return Response({'detail': 'Le compte est bloqué. Impossible de le valider.'}, status=status.HTTP_403_FORBIDDEN)

            if account.status != 'PENDING':
                return Response({'detail': f"Le compte ne peut pas être validé depuis l'état '{account.status}'."}, status=status.HTTP_400_BAD_REQUEST)

            # Mise à jour
            account.status = 'ACTIVE'
            account.save(using=bank_db)

            return Response({'detail': f'Compte ID {id} validé avec succès.'}, status=status.HTTP_200_OK)

        except PersonalAccount.DoesNotExist:
            return Response({'detail': 'Compte introuvable.'}, status=status.HTTP_404_NOT_FOUND)


class AgencyAccountListCreateView(BaseAccountListViewWithStats, generics.CreateAPIView):
    permission_classes = [ApiAccessPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    """Vue combinée GET (liste + statistiques) & POST (création) pour les comptes d'agence"""

    model = AgencyAccount
    search_fields = ['account_number', 'user__email', 'user__phone_number']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return AgencyAccountSerializer
        return AgencyAccountListSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['bank_db'] = getattr(self.request, 'source_bank_db', 'default')
        return context

    def perform_create(self, serializer):
        serializer.save()

    def get_specific_statistics(self, queryset):
        """Statistiques spécifiques aux comptes d'agence"""
        avg_deposit = queryset.aggregate(avg_deposit=Avg('deposit_porcentage'))['avg_deposit'] or 0
        avg_retrait = queryset.aggregate(avg_retrait=Avg('retrai_percentage'))['avg_retrait'] or 0
        with_code = queryset.filter(code__isnull=False).count()
        without_code = queryset.filter(code__isnull=True).count()

        return {
            'average_deposit_percentage': float(avg_deposit),
            'average_retrait_percentage': float(avg_retrait),
            'accounts_with_code': with_code,
            'accounts_without_code': without_code,
        }

class BlockUnblockAgencyAccountView(APIView):
    permission_classes = [ApiAccessPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    # permission_classes = [ApiAccessPermission]

    def post(self, request, id):
        bank_db = getattr(request, 'source_bank_db', 'default')
        action = request.data.get('action')

        if action not in ['block', 'unblock']:
            return Response(
                {'detail': "L'action doit être 'block' ou 'unblock'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            account = AgencyAccount.objects.using(bank_db).get(id=id)

            if action == 'block':
                if account.status == 'BLOCKED':
                    print('Le compte est déjà bloqué.')
                    return Response({'detail': 'Le compte est déjà bloqué.'}, status=status.HTTP_200_OK)

                account.status = 'BLOCKED'
                message = f'Compte ID {id} bloqué avec succès.'

            else:  # unblock
                if account.status == 'ACTIVE':
                    return Response({'detail': 'Le compte est déjà actif.'}, status=status.HTTP_200_OK)

                account.status = 'ACTIVE'
                message = f'Compte ID {id} débloqué avec succès.'

            account.save(using=bank_db)
            return Response({'detail': message}, status=status.HTTP_200_OK)

        except AgencyAccount.DoesNotExist:
            return Response({'detail': 'Compte introuvable.'}, status=status.HTTP_404_NOT_FOUND)

class AgencyAccountRetrieveUpdateView(generics.RetrieveUpdateAPIView):
    permission_classes = [ApiAccessPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    """Vue pour récupérer ou modifier un compte d'agence"""
    lookup_field = 'id'

    def get_queryset(self):
        bank_db = getattr(self.request, 'source_bank_db', 'default')
        return AgencyAccount.objects.using(bank_db)

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return AgencyAccountListSerializer  # pour afficher (lecture seule ou enrichie)
        return AgencyAccountSerializer  # pour la modification

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['bank_db'] = getattr(self.request, 'source_bank_db', 'default')
        return context
    
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        instance = self.get_object()

        # Extraire uniquement les champs de pourcentage
        data = {}
        if 'deposit_porcentage' in request.data:
            data['deposit_porcentage'] = request.data['deposit_porcentage']
        if 'retrai_percentage' in request.data:
            data['retrai_percentage'] = request.data['retrai_percentage']

        serializer = self.get_serializer(instance, data=data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        return Response(serializer.data, status=status.HTTP_200_OK)


class BusinessAccountListCreateView(BaseAccountListViewWithStats, generics.CreateAPIView):
    permission_classes = [ApiAccessPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    """Vue combinée GET (liste + stats) & POST (création) pour les comptes business"""

    model = BusinessAccount
    search_fields = ['account_number', 'user__email', 'user__phone_number']

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return BusinessAccountSerializer  # pour la création
        return BusinessAccountListSerializer  # pour la liste (GET)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['bank_db'] = getattr(self.request, 'source_bank_db', 'default')
        return context

    def perform_create(self, serializer):
        serializer.save()

    def get_specific_statistics(self, queryset):
        """Statistiques spécifiques aux comptes business"""
        with_registration = queryset.filter(registration_number__isnull=False).count()
        with_tax_id = queryset.filter(tax_id__isnull=False).count()
        with_code = queryset.filter(code__isnull=False).count()

        complete_accounts = queryset.filter(
            registration_number__isnull=False,
            tax_id__isnull=False,
            code__isnull=False
        ).count()

        return {
            'accounts_with_registration': with_registration,
            'accounts_with_tax_id': with_tax_id,
            'accounts_with_code': with_code,
            'complete_accounts': complete_accounts,
            'completion_rate': round((complete_accounts / queryset.count() * 100), 2) if queryset.count() > 0 else 0
        }
class BlockUnblockBusinessAccountView(APIView):
    permission_classes = [ApiAccessPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    # permission_classes = [ApiAccessPermission]

    def post(self, request, id):
        bank_db = getattr(request, 'source_bank_db', 'default')
        action = request.data.get('action')

        if action not in ['block', 'unblock']:
            return Response(
                {'detail': "L'action doit être 'block' ou 'unblock'."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            account = BusinessAccount.objects.using(bank_db).get(id=id)

            if action == 'block':
                if account.status == 'BLOCKED':
                    print('Le compte est déjà bloqué.')
                    return Response({'detail': 'Le compte est déjà bloqué.'}, status=status.HTTP_200_OK)

                account.status = 'BLOCKED'
                message = f'Compte ID {id} bloqué avec succès.'

            else:  # unblock
                if account.status == 'ACTIVE':
                    return Response({'detail': 'Le compte est déjà actif.'}, status=status.HTTP_200_OK)

                account.status = 'ACTIVE'
                message = f'Compte ID {id} débloqué avec succès.'

            account.save(using=bank_db)
            return Response({'detail': message}, status=status.HTTP_200_OK)

        except BusinessAccount.DoesNotExist:
            return Response({'detail': 'Compte introuvable.'}, status=status.HTTP_404_NOT_FOUND)


class InternAccountCreateView(generics.CreateAPIView):
    permission_classes = [ApiAccessPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    queryset = InternAccount.objects.all()
    serializer_class = InternAccountSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['bank_db'] = getattr(self.request, 'source_bank_db', 'default')
        return context


# Si vous préférez des ViewSets avec des actions dédiées, voici une alternative:

class InternAccountViewSet(viewsets.ModelViewSet):
    permission_classes = [ApiAccessPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    """ViewSet alternatif avec action statistics dédiée"""
    serializer_class = InternAccountListSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['status', 'purpose']
    search_fields = ['account_number']
    ordering_fields = ['created_at', 'balance', 'purpose']
    ordering = ['purpose', '-created_at']
    
    def get_queryset(self):
        bank_db = getattr(self.request, 'source_bank_db', 'default')
        return InternAccount.objects.using(bank_db).order_by('-created_at')
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Statistiques des comptes internes"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # Statistiques de base
        by_status = queryset.values('status').annotate(
            count=Count('id'),
            total_balance=Sum('balance')
        )
        
        # Par objectif/purpose
        by_purpose = queryset.values('purpose').annotate(
            count=Count('id'),
            total_balance=Sum('balance')
        )
        
        # Comptes récents
        last_month = timezone.now() - timedelta(days=30)
        new_accounts = queryset.filter(created_at__gte=last_month).count()
        
        return Response({
            'account_type': 'InternAccount',
            'total_accounts': queryset.count(),
            'total_balance': queryset.aggregate(Sum('balance'))['balance__sum'] or 0,
            'by_status': list(by_status),
            'by_purpose': list(by_purpose),
            'new_accounts_last_month': new_accounts,
            'purposes_count': queryset.values('purpose').distinct().count()
        })


class RegisterAgencyWithUserView(generics.CreateAPIView):
    permission_classes = [ApiAccessPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    serializer_class = AgencyAccountSerializer

    def post(self, request, *args, **kwargs):
        bank_db = getattr(self.request, 'source_bank_db', 'default')
        user_data = request.data.get('user')
        
        if not user_data:
            return Response({'user': 'Les informations de l\'utilisateur sont requises.'}, status=400)

        # Vérifier si l'utilisateur existe déjà
        if User.objects.using(bank_db).filter(
            Q(email=user_data.get('email')) | Q(phone_number=user_data.get('phone_number'))
        ).exists():
            return Response({'detail': 'Un utilisateur avec cet email ou ce numéro existe déjà.'}, status=400)

        # Créer l'utilisateur
        user = User.objects.db_manager(bank_db).create_user(  # ✅ create_user + db_manager
            username=user_data.get('username'),
            email=user_data.get('email'),
            password=user_data.get('password', 'defaultPassword123'),
            phone_number=user_data.get('phone_number'),
            date_of_birth=user_data.get('date_of_birth')
        )

        # Injecter son numéro dans les données pour le compte
        data = request.data.copy()
        data['phone_number'] = user.phone_number

        print(f"Using data: {data}")

        # ✅ Passer bank_db via le context
        serializer = self.get_serializer(data=data, context={'bank_db': bank_db})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=201)

    def perform_create(self, serializer):
        # ❌ Ne pas faire serializer.save(using=...)
        # ✅ Laisser le serializer lire bank_db via self.context
        serializer.save()



        
class RegisterBusnissWithUserView(generics.CreateAPIView):
    permission_classes = [ApiAccessPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    serializer_class = BusinessAccountSerializer

    def post(self, request, *args, **kwargs):
        bank_db = getattr(self.request, 'source_bank_db', 'default')
        user_data = request.data.get('user')
        
        if not user_data:
            return Response({'user': 'Les informations de l\'utilisateur sont requises.'}, status=400)

        # Vérifier si l'utilisateur existe déjà
        if User.objects.using(bank_db).filter(
            Q(email=user_data.get('email')) | Q(phone_number=user_data.get('phone_number'))
        ).exists():
            return Response({'detail': 'Un utilisateur avec cet email ou ce numéro existe déjà.'}, status=400)

        # Créer l'utilisateur
        user = User.objects.db_manager(bank_db).create_user(  # ✅ create_user + db_manager
            username=user_data.get('username'),
            email=user_data.get('email'),
            password=user_data.get('password', 'defaultPassword123'),
            phone_number=user_data.get('phone_number'),
            date_of_birth=user_data.get('date_of_birth')
        )

        # Injecter son numéro dans les données pour le compte
        data = request.data.copy()
        data['phone_number'] = user.phone_number

        print(f"Using data: {data}")

        # ✅ Passer bank_db via le context
        serializer = self.get_serializer(data=data, context={'bank_db': bank_db})
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=201)

    def perform_create(self, serializer):
        # ❌ Ne pas faire serializer.save(using=...)
        # ✅ Laisser le serializer lire bank_db via self.context
        serializer.save()




class TransactionListView(generics.ListAPIView):
    permission_classes = [ApiAccessPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    """Classe de base pour les vues de transactions avec statistiques"""
    serializer_class = TransactionListSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['type', 'status']
    search_fields = ['amount', 'source_account_id', 'destination_account_id', 'external_account_number']
    ordering_fields = ['date', 'amount', 'id']
    ordering = ['-date', '-id']

    def get_queryset(self):
        bank_db = getattr(self.request, 'source_bank_db', 'default')
        return Transaction.objects.using(bank_db).order_by('-date', '-id')

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['bank_db'] = getattr(self.request, 'source_bank_db', 'default')
        return context
    
    def list(self, request, *args, **kwargs):
        """Redirige vers get_statistics si action=statistics"""
        if request.query_params.get('action') == 'statistics':
            return self.get_statistics(request)
        return super().list(request, *args, **kwargs)

    def get_statistics(self, request):
        queryset = self.get_queryset()
        queryset = self.filter_queryset(queryset)

        last_week = timezone.now() - timedelta(days=7)

        total_transactions = queryset.count()
        total_amount = queryset.aggregate(Sum('amount'))['amount__sum'] or 0
        recent_transactions = queryset.filter(date__gte=last_week).count()

        by_type = list(queryset.values('type').annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        ).order_by('-total_amount'))

        by_status = list(queryset.values('status').annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        ).order_by('-total_amount'))

        top_amounts = list(queryset.order_by('-amount')[:5].values(
            'id', 'amount', 'type', 'status', 'date'
        ))

        daily_stats = []
        for i in range(7):
            date = timezone.now().date() - timedelta(days=i)
            day_stats = queryset.filter(date__date=date).aggregate(
                count=Count('id'),
                total_amount=Sum('amount')
            )
            daily_stats.append({
                'date': date.isoformat(),
                'count': day_stats['count'] or 0,
                'total_amount': day_stats['total_amount'] or 0
            })

        average_amount = total_amount / total_transactions if total_transactions > 0 else 0

        return Response({
            'total_transactions': total_transactions,
            'total_amount': float(total_amount),
            'average_amount': round(average_amount, 2),
            'recent_transactions': recent_transactions,
            'by_type': by_type,
            'by_status': by_status,
            'top_amounts': top_amounts,
            'daily_evolution': daily_stats,
            'success_rate': round(
                (queryset.filter(status='success').count() / total_transactions * 100)
                if total_transactions > 0 else 0, 2
            )
        })

    
    
class FeeRuleViewSet(MultiDatabaseViewSetMixin, viewsets.ModelViewSet):
    permission_classes = [ApiAccessPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    queryset = FeeRule.objects.all()
    serializer_class = FeeRuleSerializer
    # permission_classes = [RoleBasedPermission]
    # authentication_classes = [MultiDatabaseJWTAuthentication]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['transaction_type']
    ordering = ['max_amount']
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['bank_db'] = self.get_database()  # récupérée via request.source_bank_db
        return context

class UpdatePhoneNumberView(APIView):
    permission_classes = [ApiAccessPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    # permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        new_phone = request.data.get('phone_number')
        bank_db = getattr(request, 'source_bank_db', 'default')  # base dynamique

        if not new_phone:
            return Response({'detail': 'Le nouveau numéro est requis.'}, status=status.HTTP_400_BAD_REQUEST)

        print(f"Updating phone number for user {pk} to {new_phone} on DB: {bank_db}")

        try:
            user = User.objects.using(bank_db).get(id=pk)
        except User.DoesNotExist:
            return Response({'detail': 'Utilisateur non trouvé.'}, status=status.HTTP_404_NOT_FOUND)

        # Vérifie que le nouveau numéro n'est pas déjà utilisé par un autre utilisateur
        if User.objects.using(bank_db).exclude(pk=pk).filter(phone_number=new_phone).exists():
            return Response({'detail': 'Ce numéro est déjà utilisé.'}, status=status.HTTP_400_BAD_REQUEST)

        user.phone_number = new_phone
        user.save(using=bank_db)

        return Response({'detail': 'Numéro de téléphone mis à jour avec succès.'}, status=status.HTTP_200_OK)


class DashboardViewSet(MultiDatabaseViewSetMixin, viewsets.ViewSet):
    permission_classes = [ApiAccessPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    # permission_classes = [RoleBasedPermission]
    # authentication_classes = [MultiDatabaseJWTAuthentication]
    
    def get_all_accounts_data(self, db, queryset_filter=None):
        """Helper pour récupérer les données de tous les types de comptes"""
        account_models = [PersonalAccount, BusinessAccount, AgencyAccount, InternAccount]
        
        total_count = 0
        active_count = 0
        pending_count = 0
        total_balance = 0
        accounts_by_type = []
        
        for model in account_models:
            model_name = model.__name__
            
            # Queryset de base
            qs = model.objects.using(db)
            
            # Appliquer les filtres si fournis
            if queryset_filter:
                qs = qs.filter(**queryset_filter)
            
            # Compter les comptes
            model_total = qs.count()
            model_active = qs.filter(status='ACTIVE').count()
            model_pending = qs.filter(status='PENDING').count()
            model_balance = qs.aggregate(Sum('balance'))['balance__sum'] or 0
            
            # Ajouter aux totaux
            total_count += model_total
            active_count += model_active
            pending_count += model_pending
            total_balance += model_balance
            
            # Ajouter aux stats par type
            if model_total > 0:  # Seulement si il y a des comptes
                accounts_by_type.append({
                    'type': model_name,
                    'count': model_total,
                    'total_balance': float(model_balance)
                })
        
        return {
            'total_count': total_count,
            'active_count': active_count,
            'pending_count': pending_count,
            'total_balance': float(total_balance),
            'by_type': accounts_by_type
        }
    
    def get_accounts_by_status(self, db, queryset_filter=None):
        """Helper pour récupérer les comptes par statut"""
        account_models = [PersonalAccount, BusinessAccount, AgencyAccount, InternAccount]
        
        status_counts = {}
        
        for model in account_models:
            qs = model.objects.using(db)
            
            if queryset_filter:
                qs = qs.filter(**queryset_filter)
            
            # Compter par statut pour ce modèle
            model_status_counts = qs.values('status').annotate(count=Count('id'))
            
            for item in model_status_counts:
                status = item['status']
                count = item['count']
                
                if status in status_counts:
                    status_counts[status] += count
                else:
                    status_counts[status] = count
        
        # Convertir en format attendu
        return [{'status': k, 'count': v} for k, v in status_counts.items()]
    
    def get_daily_account_creation(self, db, queryset_filter=None):
        """Helper pour l'évolution quotidienne des créations de comptes"""
        account_models = [PersonalAccount, BusinessAccount, AgencyAccount, InternAccount]
        
        daily_data = {}
        
        for model in account_models:
            qs = model.objects.using(db)
            
            if queryset_filter:
                qs = qs.filter(**queryset_filter)
            
            # Grouper par jour pour ce modèle
            model_daily = qs.extra(
                select={'day': 'date(created_at)'}
            ).values('day').annotate(count=Count('id'))
            
            for item in model_daily:
                day = item['day']
                count = item['count']
                
                if day in daily_data:
                    daily_data[day] += count
                else:
                    daily_data[day] = count
        
        # Convertir en format attendu et trier par jour
        result = [{'day': k, 'count': v} for k, v in daily_data.items()]
        return sorted(result, key=lambda x: x['day'])
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Vue d'ensemble du dashboard"""
        user_groups = request.user.groups.values_list('name', flat=True)
        
        #Vérifier les permissions de reporting
        # if not any(role in ['admin', 'reporting'] for role in user_groups):
        #     return Response(
        #         {'error': 'Permission denied'}, 
        #         status=status.HTTP_403_FORBIDDEN
        #     )
        
        db = self.get_database()
        
        # Données générales
        today = timezone.now().date()
        last_7_days = today - timedelta(days=7)
        last_30_days = today - timedelta(days=30)
        
        # Transactions
        total_transactions = Transaction.objects.using(db).count()
        transactions_today = Transaction.objects.using(db).filter(date__date=today).count()
        transactions_7_days = Transaction.objects.using(db).filter(date__date__gte=last_7_days).count()
        
        # Comptes - utiliser la nouvelle méthode
        accounts_data = self.get_all_accounts_data(db)
        
        # Montants
        total_volume = Transaction.objects.using(db).filter(
            status='success'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        volume_7_days = Transaction.objects.using(db).filter(
            date__date__gte=last_7_days,
            status='success'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Frais - adapter selon votre modèle Fee si il existe
        try:
            intern_type = ContentType.objects.using(db).get(pk=18)  # get, pas filter
            intern_compt = InternAccount.objects.using(db).get(purpose='commission')  # get, pas filter

            print(f"Intern account type: {intern_type.id}, ID: {intern_compt.id}")  

            fees_7_days = Transaction.objects.using(db).filter(
                date__date__gte=last_7_days,
                status='success',
                destination_account_type=intern_type,
                destination_account_id=intern_compt.id
            ).aggregate(Sum('amount'))['amount__sum'] or 0

            total_fees = Transaction.objects.using(db).filter(
                status='success',
                destination_account_type=intern_type,
                destination_account_id=intern_compt.id
            ).aggregate(Sum('amount'))['amount__sum'] or 0

        except Exception as e:
            print(f"Erreur fallback fees: {str(e)}")
            total_fees = Transaction.objects.using(db).aggregate(Sum('fee'))['fee__sum'] or 0
            fees_7_days = Transaction.objects.using(db).filter(
                date__date__gte=last_7_days
            ).aggregate(Sum('fee'))['fee__sum'] or 0
        
        return Response({
             
            'transactions': {
                'total': total_transactions,
                'today': transactions_today,
                'last_7_days': transactions_7_days
            },
            'accounts': {
                'total': accounts_data['total_count'],
                'active': accounts_data['active_count'],
                'pending': accounts_data['pending_count'],
                'total_balance': accounts_data['total_balance'],
                'by_type': accounts_data['by_type']
            },
            'volume': {
                'total': float(total_volume),
                'last_7_days': float(volume_7_days)
            },
            'fees': {
                'total': float(total_fees),
                'last_7_days': float(fees_7_days)
            }
        })
    
    @action(detail=False, methods=['get'])
    def financial_report(self, request):
        """Rapport financier détaillé"""
        user_groups = request.user.groups.values_list('name', flat=True)
        
        # if not any(role in ['admin', 'reporting'] for role in user_groups):
        #     return Response(
        #         {'error': 'Permission denied'}, 
        #         status=status.HTTP_403_FORBIDDEN
        #     )
        
        db = self.get_database()
        
        # Paramètres de date
        start_date = request.query_params.get('start_date')
        end_date = request.query_params.get('end_date')
        
        # Base queryset pour les transactions
        transactions_queryset = Transaction.objects.using(db).filter(status='success')
        
        if start_date:
            transactions_queryset = transactions_queryset.filter(date__date__gte=start_date)
        if end_date:
            transactions_queryset = transactions_queryset.filter(date__date__lte=end_date)
        
        # Filtre pour les comptes basé sur les dates
        accounts_filter = {}
        if start_date:
            accounts_filter['created_at__date__gte'] = start_date
        if end_date:
            accounts_filter['created_at__date__lte'] = end_date
        
        # === DONNÉES TRANSACTIONS ===
        # Analyse par type de transaction
        by_type = transactions_queryset.values('type').annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        )
        
        # Évolution quotidienne des transactions
        daily_evolution = transactions_queryset.extra(
            select={'day': 'date(date)'}
        ).values('day').annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        ).order_by('day')
        
        # === DONNÉES COMPTES ===
        # Utiliser les nouvelles méthodes helpers
        accounts_data = self.get_all_accounts_data(db, accounts_filter)
        accounts_by_status = self.get_accounts_by_status(db, accounts_filter)
        accounts_daily_creation = self.get_daily_account_creation(db, accounts_filter)
        
        # === DONNÉES UTILISATEURS ===
        # Récupérer tous les utilisateurs avec des comptes actifs
        user_ids_with_active_accounts = set()
        account_models = [PersonalAccount, BusinessAccount, AgencyAccount, InternAccount]
        
        for model in account_models:
            active_users = model.objects.using(db).filter(
                status='ACTIVE',
                user__isnull=False
            ).values_list('user_id', flat=True)
            user_ids_with_active_accounts.update(active_users)
        
        verified_users_count = len(user_ids_with_active_accounts)
        
        # Utilisateurs par type de compte
        users_by_account_type = []
        for model in account_models:
            model_name = model.__name__
            user_count = model.objects.using(db).filter(
                user__isnull=False
            ).values('user_id').distinct().count()
            
            if user_count > 0:
                users_by_account_type.append({
                    'account_type': model_name,
                    'count': user_count
                })
        
        # Total des utilisateurs avec des comptes
        all_user_ids = set()
        for model in account_models:
            user_ids = model.objects.using(db).filter(
                user__isnull=False
            ).values_list('user_id', flat=True)
            all_user_ids.update(user_ids)
        
        total_users_with_accounts = len(all_user_ids)
        
        return Response({
             
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            
            # === TRANSACTIONS ===
            'transactions': {
                'by_type': list(by_type),
                'daily_evolution': list(daily_evolution),
                'total_transactions': transactions_queryset.count(),
                'total_amount': float(transactions_queryset.aggregate(Sum('amount'))['amount__sum'] or 0)
            },
            
            # === COMPTES ===
            'accounts': {
                'by_status': accounts_by_status,
                'by_type': accounts_data['by_type'],
                'daily_creation': accounts_daily_creation,
                'total_count': accounts_data['total_count'],
                'active_count': accounts_data['active_count'],
                'total_balance': accounts_data['total_balance'],
                'verification_rate': round((accounts_data['active_count'] / accounts_data['total_count'] * 100), 2) if accounts_data['total_count'] > 0 else 0
            },
            
            # === UTILISATEURS ===
            'users': {
                'verified_count': verified_users_count,
                'by_account_type': users_by_account_type,
                'total_with_accounts': total_users_with_accounts
            },
            
            # === COMPATIBILITÉ AVEC L'ANCIEN FORMAT ===
            'by_type': list(by_type),  # Pour la compatibilité
            'daily_evolution': list(daily_evolution),  # Pour la compatibilité
            'total_transactions': transactions_queryset.count(),
            'total_amount': float(transactions_queryset.aggregate(Sum('amount'))['amount__sum'] or 0)
        })


class AccountStatementView(generics.GenericAPIView):
    permission_classes = [ApiAccessPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    """
    View générique pour récupérer les données du relevé de compte
    Le PDF sera généré côté frontend
    """
    # permission_classes = [ApiAccessPermission]
    
    def post(self, request, account_id):
        print(request.data)
        """
        Récupère les données pour le relevé de compte
        
        Body parameters:
        - start_date (str): Date de début au format YYYY-MM-DD (optionnel)
        - end_date (str): Date de fin au format YYYY-MM-DD (optionnel)
        - account_type (str): Type de compte pour filtrer (optionnel)
        """
        try:
            # Récupération des paramètres
            start_date = request.data.get('start_date')
            end_date = request.data.get('end_date')
            account_type = request.data.get('account_type')
            
            # Validation et parsing des dates
            if start_date and end_date:
                try:
                    start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                    end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                except ValueError:
                    return Response({
                        'error': 'Format de date invalide. Utilisez YYYY-MM-DD'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                # Validation des contraintes métier
                date_diff = (end_date_obj - start_date_obj).days
                
                if date_diff < 30:
                    return Response({
                        'error': 'La période doit être d\'au moins 30 jours (1 mois)'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                if date_diff > 90:
                    return Response({
                        'error': 'La période ne peut pas dépasser 90 jours (3 mois)'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                if end_date_obj > timezone.now().date():
                    return Response({
                        'error': 'La date de fin ne peut pas être dans le futur'
                    }, status=status.HTTP_400_BAD_REQUEST)
                
                if start_date_obj >= end_date_obj:
                    return Response({
                        'error': 'La date de début doit être antérieure à la date de fin'
                    }, status=status.HTTP_400_BAD_REQUEST)
                    
            else:
                # Utiliser le mois dernier par défaut
                today = timezone.now().date()
                start_date_obj = today.replace(day=1) - relativedelta(months=1)
                end_date_obj = today.replace(day=1) - timedelta(days=1)
            
            # Récupération de la base de données
            bank_db = getattr(request, 'source_bank_db', 'default')
            
            # Construction du QuerySet de base pour les transactions
            transactions_qs = Transaction.objects.using(bank_db).filter(
                date__date__gte=start_date_obj,
                date__date__lte=end_date_obj
            )
            
            # Filtrage par compte (source ou destination)
            account_filter = Q(source_account_id=account_id) | Q(destination_account_id=account_id)
            transactions_qs = transactions_qs.filter(account_filter)
            
            # Tri par date
            transactions_qs = transactions_qs.order_by('-date', '-id')
            
            # Sérialisation des transactions
            context = {'bank_db': bank_db}
            serializer = TransactionListSerializer(transactions_qs, many=True, context=context)
            
            # Calcul des statistiques
            stats = self._calculate_statistics(transactions_qs, account_id)
            
            # Récupération des informations du compte
            account_info = self._get_account_info(account_id, account_type, bank_db)
            
            # Préparation de la réponse
            response_data = {
                'account_info': account_info,
                'period': {
                    'start_date': start_date_obj.strftime('%Y-%m-%d'),
                    'end_date': end_date_obj.strftime('%Y-%m-%d'),
                    'start_date_formatted': start_date_obj.strftime('%d/%m/%Y'),
                    'end_date_formatted': end_date_obj.strftime('%d/%m/%Y'),
                    'duration_days': (end_date_obj - start_date_obj).days + 1
                },
                'transactions': serializer.data,
                'statistics': stats,
                'generated_at': timezone.now().isoformat(),
                'total_transactions': len(serializer.data)
            }
            
            return Response(response_data, status=status.HTTP_200_OK)
            
        except Exception as e:
            import traceback
            traceback.print_exc()  # 👈 Imprime la stack trace
            return Response({
                'error': f'Erreur lors de la génération du relevé: {str(e)}'
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    
    def _calculate_statistics(self, transactions_qs, account_id):
        """Calcule les statistiques pour le relevé"""
    
        # Séparation des transactions entrantes et sortantes
        incoming_transactions = transactions_qs.filter(destination_account_id=account_id)
        outgoing_transactions = transactions_qs.filter(source_account_id=account_id)
        
        # Calculs des montants
        total_incoming = incoming_transactions.aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        total_outgoing = outgoing_transactions.aggregate(
            total=Sum('amount')
        )['total'] or 0
        
        net_flow = total_incoming - total_outgoing
        
        # Statistiques par statut
        stats_by_status = transactions_qs.values('status').annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        )
        
        # Statistiques par type
        stats_by_type = transactions_qs.values('type').annotate(count=Count('id')).order_by('type')
        
        # Répartition par mois (si la période couvre plusieurs mois)
        monthly_stats = transactions_qs.annotate(
                month=TruncMonth('date')
            ).values('month').annotate(
                count=Count('id'),
                total_amount=Sum('amount')
            ).order_by('month')
        
        return {
            'summary': {
                'total_incoming': float(total_incoming),
                'total_outgoing': float(total_outgoing),
                'net_flow': float(net_flow),
                'total_transactions': transactions_qs.count(),
                'incoming_count': incoming_transactions.count(),
                'outgoing_count': outgoing_transactions.count()
            },
            'by_status': [
                {
                    'status': item['status'],
                    'count': item['count'],
                    'total_amount': float(item['total_amount'] or 0)
                }
                for item in stats_by_status
            ],
            'by_type': [
                {
                    'type': item['type'],
                    'count': item['count'],
                    # 'total_amount': float(item['total_amount'] or 0)
                }
                for item in stats_by_type
            ],
            'by_month': [
                {
                    'month_year': item['month'],
                    'count': item['count'],
                    'total_amount': float(item['total_amount'] or 0)
                }
                for item in monthly_stats
            ]
        }
    
    def _get_account_info(self, account_id, account_type, bank_db):
        """Récupère les informations du compte selon son type"""
        from django.contrib.contenttypes.models import ContentType
        print(f"Fetching account info for ID: {account_id}, Type: {account_type}, DB: {bank_db}")
        # Import des modèles (ajustez selon votre structure)
        try:
            from ..accounts.models import PersonalAccount, AgencyAccount, BusinessAccount, InternAccount
        except ImportError:
            # Fallback si les modèles ont des noms différents
            return {
                'account_number': f'COMPTE-{account_id}',
                'type': account_type or 'unknown',
                'error': 'Impossible de charger les informations du compte'
            }
        
        # Mapping des types de comptes
        account_models = {
            'personnel': PersonalAccount,
            'personal': PersonalAccount,
            'agency': AgencyAccount,
            'business': BusinessAccount,
            'intern': InternAccount,
        }
        
        # Détermination du modèle à utiliser
        if account_type and account_type.lower() in account_models:
            model_class = account_models[account_type.lower()]
        else:
            # Essayer de deviner le type en cherchant dans tous les modèles
            for model_class in account_models.values():
                try:
                    account = model_class.objects.using(bank_db).get(id=account_id)
                    break
                except model_class.DoesNotExist:
                    continue
            else:
                return {
                    'account_number': f'COMPTE-{account_id}',
                    'type': account_type or 'unknown',
                    'error': 'Compte non trouvé'
                }
        
        try:
            # Récupération avec utilisateur si applicable
            if hasattr(model_class, 'user'):
                account = model_class.objects.using(bank_db).select_related('user').get(id=account_id)
                user_info = {
                    'username': account.user.username if account.user else None,
                    'email': account.user.email if account.user else None,
                    'phone_number': account.user.phone_number if account.user else None,
                    'is_active': account.user.is_active if account.user else None
                }
            else:
                account = model_class.objects.using(bank_db).get(id=account_id)
                user_info = None
            
            # Informations de base du compte
            account_info = {
                'id': account.id,
                'account_number': account.account_number,
                'balance': float(account.balance) if hasattr(account, 'balance') and account.balance else 0.0,
                'status': account.status if hasattr(account, 'status') else 'ACTIVE',
                'created_at': account.created_at.isoformat() if hasattr(account, 'created_at') else None,
                'type': account_type or model_class.__name__.lower().replace('account', ''),
                'user': user_info
            }
            
            # Informations spécifiques selon le type
            if account_type == 'agency':
                account_info.update({
                    'deposit_percentage': getattr(account, 'deposit_porcentage', None),
                    'withdrawal_percentage': getattr(account, 'retrai_percentage', None)
                })
            elif account_type == 'business':
                account_info.update({
                    'registration_number': getattr(account, 'registration_number', None),
                    'tax_id': getattr(account, 'tax_id', None)
                })
            elif account_type == 'intern':
                account_info.update({
                    'purpose': getattr(account, 'purpose', None)
                })
            
            return account_info
            
        except model_class.DoesNotExist:
            return {
                'account_number': f'COMPTE-{account_id}',
                'type': account_type or 'unknown',
                'error': 'Compte non trouvé'
            }
        except Exception as e:
            return {
                'account_number': f'COMPTE-{account_id}',
                'type': account_type or 'unknown',
                'error': f'Erreur lors de la récupération: {str(e)}'
            }
            
            
class UserManagementViewSet(MultiDatabaseViewSetMixin, viewsets.ViewSet):
    permission_classes = [ApiAccessPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    # permission_classes = [IsAuthenticated]
    
    def list(self, request):
        """
        Récupérer tous les utilisateurs staff avec leurs groupes
        """
        # Vérifier les permissions admin
        # if not request.user.is_staff:
        #     return Response(
        #         {'error': 'Permission denied. Admin access required.'}, 
        #         status=status.HTTP_403_FORBIDDEN
        #     )
        
        # Récupérer la base de données à utiliser
        db = self.get_database()
        
        # Récupérer tous les utilisateurs staff avec la bonne base de données
        staff_users = User.objects.using(db).filter(is_staff=True).select_related().prefetch_related('groups')
        
        users_data = []
        for user in staff_users:
            user_groups = list(user.groups.values('id', 'name'))
            users_data.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'phone_number': getattr(user, 'phone_number', None),  # Si vous avez un champ phone
                'is_staff': user.is_staff,
                'date_joined': user.date_joined,
                'last_login': user.last_login,
                'groups': user_groups,
                'groups_count': len(user_groups)
            })
        
        return Response({
             
            'users': users_data,
            'total_count': len(users_data)
        })
    
    @action(detail=False, methods=['get'])
    def get_all_groups(self, request):
        """
        Récupérer la liste de tous les groupes disponibles
        """
        # if not request.user.is_staff:
        #     return Response(
        #         {'error': 'Permission denied. Admin access required.'}, 
        #         status=status.HTTP_403_FORBIDDEN
        #     )
        
        # Utiliser la bonne base de données
        db = self.get_database()
        groups = Group.objects.using(db).all().values('id', 'name')
        return Response({
             
            'groups': list(groups),
            'total_groups': groups.count()
        })
    
    @action(detail=False, methods=['post'])
    def find_user_by_phone(self, request):
        """
        Trouver un utilisateur par son numéro de téléphone et retourner son nom
        """
        # if not request.user.is_staff:
        #     return Response(
        #         {'error': 'Permission denied. Admin access required.'}, 
        #         status=status.HTTP_403_FORBIDDEN
        #     )
        
        phone_number = request.data.get('phone_number')
        if not phone_number:
            return Response(
                {'error': 'Phone number is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Utiliser la bonne base de données
        db = self.get_database()
        
        # Normaliser le numéro de téléphone (enlever espaces, tirets, etc.)
        normalized_phone = re.sub(r'[^\d+]', '', phone_number)
        
        try:
            # Chercher l'utilisateur par numéro de téléphone
            # Adapter selon votre modèle User (phone_number, phone, mobile, etc.)
            user = None
            
            # Essayer différents champs possibles pour le téléphone
            phone_fields = ['phone_number', 'phone', 'mobile', 'telephone']
            
            for field in phone_fields:
                try:
                    # Chercher avec le numéro exact
                    user = User.objects.using(db).get(**{field: phone_number})
                    break
                except (ObjectDoesNotExist, AttributeError):
                    try:
                        # Chercher avec le numéro normalisé
                        user = User.objects.using(db).get(**{field: normalized_phone})
                        break
                    except (ObjectDoesNotExist, AttributeError):
                        continue
            
            # Si pas trouvé avec les champs dédiés, chercher dans username si c'est un numéro
            if not user:
                try:
                    user = User.objects.using(db).get(username=phone_number)
                except ObjectDoesNotExist:
                    try:
                        user = User.objects.using(db).get(username=normalized_phone)
                    except ObjectDoesNotExist:
                        pass
            
            if not user:
                return Response(
                    {'error': 'User not found with this phone number'}, 
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Récupérer les groupes de l'utilisateur
            user_groups = list(user.groups.values('id', 'name'))
            
            return Response({
                 
                'user_found': True,
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'is_staff': user.is_staff,
                    'is_active': user.is_active,
                    'groups': user_groups,
                    'phone_number': user.phone_number
                }
            })
            
        except Exception as e:
            return Response(
                {'error': f'Error searching user: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def assign_groups_to_user(self, request):
        """
        Assigner des groupes à un utilisateur
        """
        # if not request.user.is_staff:
        #     return Response(
        #         {'error': 'Permission denied. Admin access required.'}, 
        #         status=status.HTTP_403_FORBIDDEN
        #     )
        
        user_id = request.data.get('user_id')
        group_ids = request.data.get('group_ids', [])
        
        if not user_id:
            return Response(
                {'error': 'User ID is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Utiliser la bonne base de données
        db = self.get_database()
        
        try:
            user = User.objects.using(db).get(id=user_id)
            
            # Vérifier que les groupes existent
            groups = Group.objects.using(db).filter(id__in=group_ids)
            if len(groups) != len(group_ids):
                return Response(
                    {'error': 'Some groups do not exist'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Supprimer les anciennes relations
            User.groups.through.objects.using(db).filter(user_id=user.id).delete()

            # Créer manuellement les relations ManyToMany (dans la bonne base)
            UserGroupThrough = User.groups.through
            UserGroupThrough.objects.using(db).bulk_create([
                UserGroupThrough(user_id=user.id, group_id=group.id) for group in groups
])
            
            # Récupérer les groupes mis à jour
            updated_groups = list(user.groups.using(db).values('id', 'name'))
            
            return Response({
                'success': True,
                'message': f'Groups assigned to user {user.username}',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'phone_number': user.phone_number,
                    'groups': updated_groups
                }
            })
            
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Error assigning groups: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def remove_user_staff_access(self, request):
        """
        Enlever les droits staff d'un utilisateur et vider ses groupes
        """
        # if not request.user.is_staff:
        #     return Response(
        #         {'error': 'Permission denied. Admin access required.'}, 
        #         status=status.HTTP_403_FORBIDDEN
        #     )
        
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response(
                {'error': 'User ID is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Utiliser la bonne base de données
        db = self.get_database()
        
        try:
            user = User.objects.using(db).get(id=user_id)
            
            # Vérifier qu'on ne se supprime pas soi-même
            if user.id == request.user.id:
                return Response(
                    {'error': 'You cannot remove your own staff access'}, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Sauvegarder l'état précédent
            previous_state = {
                'is_staff': user.is_staff,
                'groups': list(user.groups.using(db).values('id', 'name'))
            }
            
            # Enlever les droits staff et vider les groupes
            user.is_staff = False
            user.groups.clear()
            user.save(using=db)
            
            return Response({
                 
                'success': True,
                'message': f'Staff access removed for user {user.username}',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'phone_number': user.phone_number,
                    'is_staff': user.is_staff,
                    'groups': [],
                    'previous_state': previous_state
                }
            })
            
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Error removing staff access: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def grant_staff_access(self, request):
        """
        Donner les droits staff à un utilisateur
        """
        # if not request.user.is_staff:
        #     return Response(
        #         {'error': 'Permission denied. Admin access required.'}, 
        #         status=status.HTTP_403_FORBIDDEN
        #     )
        
        user_id = request.data.get('user_id')
        
        if not user_id:
            return Response(
                {'error': 'User ID is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Utiliser la bonne base de données
        db = self.get_database()
        
        try:
            user = User.objects.using(db).get(id=user_id)
            
            # Donner les droits staff
            user.is_staff = True
            user.save(using=db)
            
            return Response({
                 
                'success': True,
                'message': f'Staff access granted to user {user.username}',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'full_name': f"{user.first_name} {user.last_name}".strip() or user.username,
                    'is_staff': user.is_staff,
                    'groups': list(user.groups.using(db).values('id', 'name'))
                }
            })
            
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'}, 
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': f'Error granting staff access: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
    
    @action(detail=False, methods=['post'])
    def search_users(self, request):
        """
        Rechercher des utilisateurs par nom, email ou téléphone
        """
        # if not request.user.is_staff:
        #     return Response(
        #         {'error': 'Permission denied. Admin access required.'}, 
        #         status=status.HTTP_403_FORBIDDEN
        #     )
        
        search_term = request.data.get('search_term', '').strip()
        
        if not search_term:
            return Response(
                {'error': 'Search term is required'}, 
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Utiliser la bonne base de données
        db = self.get_database()
        
        # Construire la requête de recherche
        search_query = Q()
        
        # Rechercher dans différents champs
        search_query |= Q(username__icontains=search_term)
        search_query |= Q(email__icontains=search_term)
        search_query |= Q(first_name__icontains=search_term)
        search_query |= Q(last_name__icontains=search_term)
        
        # Rechercher dans les champs de téléphone si ils existent
        phone_fields = ['phone_number', 'phone', 'mobile', 'telephone']
        for field in phone_fields:
            try:
                search_query |= Q(**{f"{field}__icontains": search_term})
            except:
                continue
        
        users = User.objects.using(db).filter(search_query).select_related().prefetch_related('groups')[:20]  # Limiter à 20 résultats
        
        users_data = []
        for user in users:
            user_groups = list(user.groups.values('id', 'name'))
            users_data.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'phone_number': getattr(user, 'phone_number', None),
                'is_active': user.is_active,
                'is_staff': user.is_staff,
                'groups': user_groups
            })
        
        return Response({
             
            'users': users_data,
            'total_found': len(users_data),
            'search_term': search_term
        })