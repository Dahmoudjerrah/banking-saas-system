

class TenantRouter:
  
    class DatabaseNotFoundError(Exception):
     pass

    

    def db_for_write(self, model, **hints):
        if 'bank_db' in hints:
            return hints['bank_db']
        if hasattr(model, 'get_db'):
            return model.get_db()
        return 'default'

    def allow_relation(self, obj1, obj2, **hints):
        db_obj1 = hints.get('bank_db', 'default')
        db_obj2 = hints.get('bank_db', 'default')
        if db_obj1 == db_obj2:
            return True
        print(f"Relation not allowed: {db_obj1} != {db_obj2}")

        return None
    

    def allow_migrate(self, db, app_label, model_name=None, **hints):
    # Permet les migrations sur la base de données par défaut pour l'application 'banks'
     if app_label == 'banks':
        return db == 'default'
      # Empêche les migrations des applications 'transactions' et 'accounts' dans la base de données 'default'
     if app_label in ['transactions', 'accounts']:
        return db != 'default'
    # Permet les migrations sur les autres bases de données configurées
     return db in ['default', 'rasidi', 'gaza']


    
