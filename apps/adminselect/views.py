from rest_framework import viewsets, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from apps.accounts.models import Account, DemandeChequiers
from apps.adminselect.authentication import MultiDatabaseJWTAuthentication
from apps.adminselect.serializers import (
    AccountSerializer, AddAgencyAccountSerializer, AddBusinessAccountSerializer, AddBusinessOrAgencyAccountSerializer, DemandeChequiersSerializer, FeeRuleSerializer, 
    FeeSerializer, LoginSerializer, PaymentRequestSerializer, PreTransactionSerializer, RegisterSerializer, RegistrationAcounteAgancyBisenessSerializer, RegistrationAcounteAgancySerializer, RegistrationAcounteBisenessSerializer, 
    TransactionSerializer
)
from apps.transactions.models import Fee, FeeRule, PaymentRequest, PreTransaction, Transaction
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import Q, Sum, Count
from django.utils import timezone
from datetime import datetime, timedelta

from apps.users.models import User
from .permissions import RoleBasedPermission
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
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



class LoginView(APIView):
    """
    Vue de connexion avec JWT et support multi-database
    """
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        # Récupérer la base de données
        bank_db = getattr(request, 'source_bank_db', 'default')
        
        if not bank_db:
            return Response({
                "error": "Base de données bancaire non spécifiée."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = LoginSerializer(
            data=request.data,
            context={'bank_db': bank_db}
        )
        
        if serializer.is_valid():
            user = serializer.validated_data['user']
            
            try:
                # Générer les tokens JWT
                refresh = RefreshToken.for_user(user)
                access = refresh.access_token
                
                # Ajouter des informations personnalisées au token
                access['bank_db'] = bank_db
                access['user_id'] = user.id
                access['username'] = user.username
                
                # Récupérer les groupes de l'utilisateur dans cette DB
                user_groups = user.groups.using(bank_db).values_list('name', flat=True)
                access['groups'] = list(user_groups)
                
                return Response({
                    "message": "Connexion réussie.",
                    "access": str(access),
                    "refresh": str(refresh),
                    "user": {
                        "id": user.id,
                        "username": user.username,
                        "email": user.email,
                        "phone_number": user.phone_number,
                        "groups": list(user_groups)
                    }
                }, status=status.HTTP_200_OK)
                
            except Exception as e:
                return Response({
                    "error": f"Erreur lors de la génération du token: {str(e)}"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RefreshTokenView(APIView):
    """
    Vue pour rafraîchir le token JWT
    """
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get('refresh')
        
        if not refresh_token:
            return Response({
                "error": "Token de rafraîchissement requis."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            refresh = RefreshToken(refresh_token)
            access = refresh.access_token
            
            # Récupérer la base de données du token ou de la requête
            bank_db = getattr(request, 'source_bank_db', 'default')
            
            # Ajouter les informations au nouveau token
            access['bank_db'] = bank_db
            
            # Récupérer l'utilisateur pour mettre à jour les infos
            user_id = refresh.payload.get('user_id')
            if user_id:
                try:
                    user = User.objects.using(bank_db).get(id=user_id)
                    access['user_id'] = user.id
                    access['username'] = user.username
                    
                    user_groups = user.groups.using(bank_db).values_list('name', flat=True)
                    access['groups'] = list(user_groups)
                except User.DoesNotExist:
                    pass
            
            return Response({
                "access": str(access),
                "refresh": str(refresh)
            }, status=status.HTTP_200_OK)
            
        except Exception as e:
            return Response({
                "error": f"Token invalide: {str(e)}"
            }, status=status.HTTP_401_UNAUTHORIZED)

class RegistrationAcounteAgancyBisenessView(APIView):
    permission_classes = [RoleBasedPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    def post(self, request, *args, **kwargs):
        serializer = RegistrationAcounteAgancyBisenessSerializer(data=request.data, context={'bank_db': request.source_bank_db})
        if serializer.is_valid():
            user = serializer.save()
            return Response({"message": "Utilisateur enregistré avec succès"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class RegistrationAcounteAgancyView(APIView):
    permission_classes = [RoleBasedPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    def post(self, request, *args, **kwargs):
        serializer = RegistrationAcounteAgancySerializer(data=request.data, context={'bank_db': request.source_bank_db})
        if serializer.is_valid():
            user = serializer.save()
            return Response({"message": "Utilisateur enregistré avec succès"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class RegistrationAcounteBisenessView(APIView):
    permission_classes = [RoleBasedPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    def post(self, request, *args, **kwargs):
        serializer = RegistrationAcounteBisenessSerializer(data=request.data, context={'bank_db': request.source_bank_db})
        if serializer.is_valid():
            user = serializer.save()
            return Response({"message": "Utilisateur enregistré avec succès"}, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AddBusinessOrAgencyAccountView(APIView):
    permission_classes = [RoleBasedPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    def post(self, request, *args, **kwargs):
        serializer = AddBusinessOrAgencyAccountSerializer(
            data=request.data,
            context={'bank_db': request.source_bank_db}
        )
        if serializer.is_valid():
            account = serializer.save()
            return Response({
                "message": "Compte ajouté avec succès.",
              
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)    

class AddBusinessAccountView(APIView):
    permission_classes = [RoleBasedPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    def post(self, request, *args, **kwargs):
        serializer = AddBusinessAccountSerializer(
            data=request.data,
            context={'bank_db': request.source_bank_db}
        )
        if serializer.is_valid():
            account = serializer.save()
            return Response({
                "message": "Compte ajouté avec succès.",
              
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)  
    
class AddAgencyAccountView(APIView):
    permission_classes = [RoleBasedPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    def post(self, request, *args, **kwargs):
        serializer = AddAgencyAccountSerializer(
            data=request.data,
            context={'bank_db': request.source_bank_db}
        )
        if serializer.is_valid():
            account = serializer.save()
            return Response({
                "message": "Compte ajouté avec succès.",
              
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)  

class RegisterView(APIView):
    """
    Vue pour l'enregistrement d'utilisateurs avec support multi-database
    """
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        # Récupérer la base de données à partir de la requête
        bank_db = getattr(request, 'source_bank_db', 'default')
        
        if not bank_db:
            return Response({
                "error": "Base de données bancaire non spécifiée."
            }, status=status.HTTP_400_BAD_REQUEST)
        
        serializer = RegisterSerializer(
            data=request.data,
            context={'bank_db': bank_db}
        )
        
        if serializer.is_valid():
            try:
                user = serializer.save()
                
                # Attribuer un groupe par défaut (optionnel)
                default_group_name = request.data.get('default_group', 'business')
                try:
                    default_group = Group.objects.using(bank_db).get(name=default_group_name)
                    # user.groups.add(default_group)
                    user.save(using=bank_db)
                except Group.DoesNotExist:
                    pass  # Ignorer si le groupe n'existe pas
                
                return Response({
                    "message": "Utilisateur créé avec succès.",
                    "user_id": user.id,
                    "username": user.username,
                    "email": user.email,
                    "database": bank_db
                }, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                return Response({
                    "error": f"Erreur lors de la création de l'utilisateur: {str(e)}"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TransactionViewSet(MultiDatabaseViewSetMixin, viewsets.ModelViewSet):
    queryset = Transaction.objects.all()
    serializer_class = TransactionSerializer
    permission_classes = [RoleBasedPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type', 'status', 'date']
    search_fields = ['id', 'external_account_number', 'external_bank']
    ordering_fields = ['date', 'amount']
    ordering = ['-date']
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Statistiques des transactions"""
        queryset = self.get_queryset()
        
        # Statistiques générales
        total_transactions = queryset.count()
        total_amount = queryset.aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Par type
        by_type = queryset.values('type').annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        )
        
        # Par statut
        by_status = queryset.values('status').annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        )
        
        # Transactions récentes (7 derniers jours)
        last_week = timezone.now() - timedelta(days=7)
        recent_transactions = queryset.filter(date__gte=last_week).count()
        
        return Response({
            'total_transactions': total_transactions,
            'total_amount': total_amount,
            'by_type': by_type,
            'by_status': by_status,
            'recent_transactions': recent_transactions
        })

class AccountViewSet(MultiDatabaseViewSetMixin, viewsets.ModelViewSet):
    queryset = Account.objects.all()
    serializer_class = AccountSerializer
    permission_classes = [RoleBasedPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['type_account', 'status']
    search_fields = ['account_number', 'user__username', 'user__email']
    ordering_fields = ['created_at', 'balance']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user_groups = self.request.user.groups.values_list('name', flat=True)
        
        # Filtrer selon le rôle
        if 'business' in user_groups:
            queryset = queryset.filter(type_account='business')
        elif 'agency' in user_groups:
            queryset = queryset.filter(type_account='agency')
        elif 'kyc' in user_groups:
            queryset = queryset.filter(status='PENDING',type_account='personnel')
            
        return queryset
    
    @action(detail=True, methods=['patch'])
    def validate_account(self, request, pk=None):
        """Validation d'un compte (pour KYC)"""
        account = self.get_object()
        user_groups = request.user.groups.values_list('name', flat=True)
        
        if 'kyc' not in user_groups and 'admin' not in user_groups:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Utiliser la bonne base de données pour la sauvegarde
        db = self.get_database()
        account.status = 'ACTIVE'
        account.save(using=db)
        
        return Response({'message': 'Account validated successfully'})
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Statistiques des comptes"""
        queryset = self.get_queryset()
        
        # Par type
        by_type = queryset.values('type_account').annotate(
            count=Count('id'),
            total_balance=Sum('balance')
        )
        
        # Par statut
        by_status = queryset.values('status').annotate(
            count=Count('id')
        )
        
        # Comptes récents
        last_month = timezone.now() - timedelta(days=30)
        new_accounts = queryset.filter(created_at__gte=last_month).count()
        
        return Response({
            'total_accounts': queryset.count(),
            'total_balance': queryset.aggregate(Sum('balance'))['balance__sum'] or 0,
            'by_type': by_type,
            'by_status': by_status,
            'new_accounts_last_month': new_accounts
        })

class FeeRuleViewSet(MultiDatabaseViewSetMixin, viewsets.ModelViewSet):
    queryset = FeeRule.objects.all()
    serializer_class = FeeRuleSerializer
    permission_classes = [RoleBasedPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['transaction_type']
    ordering = ['max_amount']
    
    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['bank_db'] = self.get_database()  # récupérée via request.source_bank_db
        return context

class FeeViewSet(MultiDatabaseViewSetMixin, viewsets.ModelViewSet):
    queryset = Fee.objects.all()
    serializer_class = FeeSerializer
    permission_classes = [RoleBasedPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    ordering = ['-created_at']
    
    @action(detail=False, methods=['get'])
    def statistics(self, request):
        """Statistiques des frais"""
        queryset = self.get_queryset()
        
        total_fees = queryset.aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Frais par type de transaction
        by_transaction_type = queryset.values(
            'transaction__type'
        ).annotate(
            count=Count('id'),
            total_amount=Sum('amount')
        )
        
        return Response({
            'total_fees': total_fees,
            'by_transaction_type': by_transaction_type
        })

class PaymentRequestViewSet(MultiDatabaseViewSetMixin, viewsets.ModelViewSet):
    queryset = PaymentRequest.objects.all()
    serializer_class = PaymentRequestSerializer
    permission_classes = [RoleBasedPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status']
    search_fields = ['code', 'merchant__account_number']
    ordering = ['-created_at']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user_groups = self.request.user.groups.values_list('name', flat=True)
        
        # Les business ne voient que leurs demandes
        if 'business' in user_groups:
            db = self.get_database()
            user_accounts = Account.objects.using(db).filter(user=self.request.user)
            queryset = queryset.filter(merchant__in=user_accounts)
            
        return queryset

class PreTransactionViewSet(MultiDatabaseViewSetMixin, viewsets.ModelViewSet):
    queryset = PreTransaction.objects.all()
    serializer_class = PreTransactionSerializer
    permission_classes = [RoleBasedPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['is_used']
    search_fields = ['id', 'code', 'client_phone']
    ordering = ['-created_at']
    
    @action(detail=False, methods=['get'])
    def active_codes(self, request):
        """Codes actifs non utilisés"""
        active_pretransactions = []
        for pt in self.get_queryset().filter(is_used=False):
            if pt.is_active():
                active_pretransactions.append(pt)
        
        serializer = self.get_serializer(active_pretransactions, many=True)
        print(serializer.data)
        return Response(serializer.data)

class DemandeChequiersViewSet(MultiDatabaseViewSetMixin, viewsets.ModelViewSet):
    queryset = DemandeChequiers.objects.all()
    serializer_class = DemandeChequiersSerializer
    permission_classes = [RoleBasedPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['est_traite', 'nombre_pages']
    search_fields = ['compte__account_number', 'motif']
    ordering = ['-demande_le']
    
    def get_queryset(self):
        queryset = super().get_queryset()
        user_groups = self.request.user.groups.values_list('name', flat=True)
        
        # Les business ne voient que leurs demandes
        if 'business' in user_groups:
            db = self.get_database()
            user_accounts = Account.objects.using(db).filter(user=self.request.user)
            queryset = queryset.filter(compte__in=user_accounts)
            
        return queryset
    
    @action(detail=True, methods=['patch'])
    def process_request(self, request, pk=None):
        """Traiter une demande de chéquier"""
        demande = self.get_object()
        user_groups = request.user.groups.values_list('name', flat=True)
        
        if 'agency' not in user_groups and 'admin' not in user_groups:
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Utiliser la bonne base de données
        db = self.get_database()
        demande.est_traite = True
        demande.save(using=db)
        
        return Response({'message': 'Demande traitée avec succès'})

# Dashboard API pour les rapports
class DashboardViewSet(MultiDatabaseViewSetMixin, viewsets.ViewSet):
    permission_classes = [RoleBasedPermission]
    authentication_classes = [MultiDatabaseJWTAuthentication]
    
    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Vue d'ensemble du dashboard"""
        user_groups = request.user.groups.values_list('name', flat=True)
        
        # Vérifier les permissions de reporting
        if not any(role in ['admin', 'reporting'] for role in user_groups):
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
        db = self.get_database()
        
        # Données générales
        today = timezone.now().date()
        last_7_days = today - timedelta(days=7)
        last_30_days = today - timedelta(days=30)
        
        # Transactions
        total_transactions = Transaction.objects.using(db).count()
        transactions_today = Transaction.objects.using(db).filter(date__date=today).count()
        transactions_7_days = Transaction.objects.using(db).filter(date__date__gte=last_7_days).count()
        
        # Comptes
        total_accounts = Account.objects.using(db).count()
        active_accounts = Account.objects.using(db).filter(status='ACTIVE').count()
        pending_accounts = Account.objects.using(db).filter(status='PENDING').count()
        
        # Montants
        total_volume = Transaction.objects.using(db).filter(
            status='success'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        volume_7_days = Transaction.objects.using(db).filter(
            date__date__gte=last_7_days,
            status='success'
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        # Frais
        total_fees = Fee.objects.using(db).aggregate(Sum('amount'))['amount__sum'] or 0
        fees_7_days = Fee.objects.using(db).filter(
            created_at__date__gte=last_7_days
        ).aggregate(Sum('amount'))['amount__sum'] or 0
        
        return Response({
            'database': db,  # Pour debug
            'transactions': {
                'total': total_transactions,
                'today': transactions_today,
                'last_7_days': transactions_7_days
            },
            'accounts': {
                'total': total_accounts,
                'active': active_accounts,
                'pending': pending_accounts
            },
            'volume': {
                'total': total_volume,
                'last_7_days': volume_7_days
            },
            'fees': {
                'total': total_fees,
                'last_7_days': fees_7_days
            }
        })
    
    @action(detail=False, methods=['get'])
    def financial_report(self, request):
        """Rapport financier détaillé"""
        user_groups = request.user.groups.values_list('name', flat=True)
        
        if not any(role in ['admin', 'reporting'] for role in user_groups):
            return Response(
                {'error': 'Permission denied'}, 
                status=status.HTTP_403_FORBIDDEN
            )
        
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
        
        # Base queryset pour les comptes (filtrage par date de création)
        accounts_queryset = Account.objects.using(db)
        
        if start_date:
            accounts_queryset = accounts_queryset.filter(created_at__date__gte=start_date)
        if end_date:
            accounts_queryset = accounts_queryset.filter(created_at__date__lte=end_date)
        
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
        # Statistiques des comptes par statut
        accounts_by_status = accounts_queryset.values('status').annotate(
            count=Count('id')
        )
        
        # Statistiques des comptes par type
        accounts_by_type = accounts_queryset.values('type_account').annotate(
            count=Count('id'),
            total_balance=Sum('balance')
        )
        
        # Évolution quotidienne des créations de comptes
        accounts_daily_creation = accounts_queryset.extra(
            select={'day': 'date(created_at)'}
        ).values('day').annotate(
            count=Count('id')
        ).order_by('day')
        
        # === DONNÉES UTILISATEURS ===
        # Utilisateurs avec comptes vérifiés (status ACTIVE)
        verified_users = User.objects.using(db).filter(
            account__status='ACTIVE'
        ).distinct()
        
        # Utilisateurs par type de compte
        users_by_account_type = User.objects.using(db).filter(
            account__isnull=False
        ).values('account__type_account').annotate(
            count=Count('id', distinct=True)
        )
        
        # === CALCULS GÉNÉRAUX ===
        total_accounts_balance = accounts_queryset.aggregate(
            Sum('balance')
        )['balance__sum'] or 0
        
        # Comptes actifs vs total
        active_accounts_count = accounts_queryset.filter(status='ACTIVE').count()
        total_accounts_count = accounts_queryset.count()
        
        return Response({
            'database': db,  # Pour debug
            'period': {
                'start_date': start_date,
                'end_date': end_date
            },
            
            # === TRANSACTIONS ===
            'transactions': {
                'by_type': by_type,
                'daily_evolution': daily_evolution,
                'total_transactions': transactions_queryset.count(),
                'total_amount': transactions_queryset.aggregate(Sum('amount'))['amount__sum'] or 0
            },
            
            # === COMPTES ===
            'accounts': {
                'by_status': accounts_by_status,
                'by_type': accounts_by_type,
                'daily_creation': accounts_daily_creation,
                'total_count': total_accounts_count,
                'active_count': active_accounts_count,
                'total_balance': total_accounts_balance,
                'verification_rate': round((active_accounts_count / total_accounts_count * 100), 2) if total_accounts_count > 0 else 0
            },
            
            # === UTILISATEURS ===
            'users': {
                'verified_count': verified_users.count(),
                'by_account_type': users_by_account_type,
                'total_with_accounts': User.objects.using(db).filter(account__isnull=False).distinct().count()
            },
            
            # === COMPATIBILITÉ AVEC L'ANCIEN FORMAT ===
            'by_type': by_type,  # Pour la compatibilité
            'daily_evolution': daily_evolution,  # Pour la compatibilité
            'total_transactions': transactions_queryset.count(),
            'total_amount': transactions_queryset.aggregate(Sum('amount'))['amount__sum'] or 0
        })
