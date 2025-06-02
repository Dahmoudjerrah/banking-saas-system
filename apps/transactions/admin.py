from django.contrib import admin
from .models import Transaction

class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'source_account', 'destination_account', 'amount', 'type', 'date')

    def get_queryset(self, request):
        selected_db = request.session.get('admin_selected_bank', 'default')
        return super().get_queryset(request).using(selected_db)

    def get_object(self, request, object_id, from_field=None):
        selected_db = request.session.get('admin_selected_bank', 'default')
        try:
            return self.model._default_manager.using(selected_db).get(pk=object_id)
        except self.model.DoesNotExist:
            return None

    def get_form(self, request, obj=None, **kwargs):
        selected_db = request.session.get('admin_selected_bank', 'default')
        form = super().get_form(request, obj, **kwargs)

        
        for field_name, field in form.base_fields.items():
            if hasattr(field, 'queryset') and field.queryset is not None:
                field.queryset = field.queryset.using(selected_db)

        return form

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        selected_db = request.session.get('admin_selected_bank', 'default')
        kwargs['using'] = selected_db
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


admin.site.register(Transaction, TransactionAdmin)
