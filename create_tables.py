from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os 
import sys  

# ============================================
# ÉTAPE 1 : Charger les variables depuis .env    
# ============================================
env_charge = load_dotenv() 

if not env_charge:
    print("[ERREUR] Fichier .env introuvable. Vérifie qu'il est à la racine du projet, au même niveau que ce script (pas dans .venv).")
    sys.exit(1)

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

# ============================================
# ÉTAPE 2 : Vérifier qu'aucune variable ne manque
# (sans jamais afficher le mot de passe en clair) 
# ============================================
variables = {
    "DB_USER": DB_USER,
    "DB_PASSWORD": DB_PASSWORD,
    "DB_HOST": DB_HOST,
    "DB_PORT": DB_PORT,
    "DB_NAME": DB_NAME
}

variables_manquantes = [nom for nom, valeur in variables.items() if valeur is None]

if variables_manquantes:
    print(f"[ERREUR] Variables manquantes dans le .env : {variables_manquantes}")
    sys.exit(1)

print("[OK] Toutes les variables d'environnement sont chargées.")

# ============================================
# ÉTAPE 3 : Connexion à PostgreSQL
# ============================================
url_connexion = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

try:
    engine = create_engine(url_connexion)
    with engine.connect() as conn:
        print("[OK] Connexion à PostgreSQL réussie !")
except Exception as e:
    print(f"[ERREUR] Connexion échouée : {e}")
    print("[AIDE] Vérifie que Docker Desktop est ouvert et que le conteneur tourne (docker ps).")
    sys.exit(1)

# ============================================
# ÉTAPE 4 : Création des 3 tables
# ============================================
creer_table_medicaments = """
CREATE TABLE IF NOT EXISTS medicaments (
    id SERIAL PRIMARY KEY,
    update_type TEXT,
    initial_posting_date TEXT,
    package_ndc TEXT,
    generic_name TEXT,
    contact_info TEXT,
    update_date TEXT,
    therapeutic_category TEXT,
    presentation TEXT,
    company_name TEXT,
    status TEXT,
    dosage_form TEXT,
    availability TEXT,
    related_info TEXT,
    discontinued_date TEXT,
    shortage_reason TEXT
);
"""

creer_table_openfda = """
CREATE TABLE IF NOT EXISTS openfda_details (
    id SERIAL PRIMARY KEY,
    medicament_id INTEGER REFERENCES medicaments(id),
    brand_name TEXT,
    generic_name_openfda TEXT,
    manufacturer_name TEXT,
    product_type TEXT,
    route TEXT,
    substance_name TEXT,
    application_number TEXT
);
"""

creer_table_classifications = """
CREATE TABLE IF NOT EXISTS classifications_pharma (
    id SERIAL PRIMARY KEY,
    medicament_id INTEGER REFERENCES medicaments(id),
    pharm_class_epc TEXT,
    pharm_class_cs TEXT,
    pharm_class_moa TEXT,
    pharm_class_pe TEXT
);
"""

try:
    with engine.connect() as conn:
        conn.execute(text(creer_table_medicaments))
        conn.execute(text(creer_table_openfda))
        conn.execute(text(creer_table_classifications))
        conn.commit()
    print("[OK] Les 3 tables ont été créées avec succès !")
except Exception as e:
    print(f"[ERREUR] Problème lors de la création des tables : {e}")
    sys.exit(1)