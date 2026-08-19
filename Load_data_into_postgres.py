import requests
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os
import sys

# ============================================
# CONNEXION À LA BASE
# ============================================
env_charge = load_dotenv()
if not env_charge:
    print("[ERREUR] Fichier .env introuvable à la racine du projet.")
    sys.exit(1)

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

variables_manquantes = [n for n, v in {
    "DB_USER": DB_USER, "DB_PASSWORD": DB_PASSWORD,
    "DB_HOST": DB_HOST, "DB_PORT": DB_PORT, "DB_NAME": DB_NAME
}.items() if v is None]

if variables_manquantes:
    print(f"[ERREUR] Variables manquantes dans .env : {variables_manquantes}")
    sys.exit(1)

engine = create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

try:
    with engine.connect() as conn:
        print("[OK] Connexion à PostgreSQL réussie.")
except Exception as e:
    print(f"[ERREUR] Connexion échouée : {e}")
    print("[AIDE] Vérifie que Docker tourne (docker ps) et relance le conteneur si besoin (docker start fda-postgres).")
    sys.exit(1)


# ============================================
# EXTRACT
# ============================================
def recuperer_toutes_les_donnees():
    tous_les_medicaments = []

    url1 = "https://api.fda.gov/drug/shortages.json?limit=1000&skip=0"
    reponse1 = requests.get(url1)
    donnees1 = reponse1.json()
    total_annonce = donnees1['meta']['results']['total']
    tous_les_medicaments.extend(donnees1["results"])

    url2 = "https://api.fda.gov/drug/shortages.json?limit=1000&skip=1000"
    reponse2 = requests.get(url2)
    donnees2 = reponse2.json()
    tous_les_medicaments.extend(donnees2["results"])

    print(f"[EXTRACT] Total annoncé par l'API : {total_annonce} | Total récupéré : {len(tous_les_medicaments)}")
    return tous_les_medicaments


# ============================================
# TRANSFORM (fonction utilitaire)
# ============================================
def liste_vers_texte(valeur):
    if valeur is None:
        return None
    if isinstance(valeur, list):
        return ", ".join(str(v) for v in valeur)
    return valeur


# ============================================
# TRANSFORM + LOAD (par médicament)
# ============================================
def inserer_medicament(conn, medicament):
    requete_principale = text("""
        INSERT INTO medicaments (
            update_type, initial_posting_date, package_ndc, generic_name,
            contact_info, update_date, therapeutic_category, presentation,
            company_name, status, dosage_form, availability, related_info,
            discontinued_date, shortage_reason
        ) VALUES (
            :update_type, :initial_posting_date, :package_ndc, :generic_name,
            :contact_info, :update_date, :therapeutic_category, :presentation,
            :company_name, :status, :dosage_form, :availability, :related_info,
            :discontinued_date, :shortage_reason
        )
        RETURNING id
    """)

    resultat = conn.execute(requete_principale, {
        "update_type": medicament.get("update_type"),
        "initial_posting_date": medicament.get("initial_posting_date"),
        "package_ndc": medicament.get("package_ndc"),
        "generic_name": medicament.get("generic_name"),
        "contact_info": medicament.get("contact_info"),
        "update_date": medicament.get("update_date"),
        "therapeutic_category": liste_vers_texte(medicament.get("therapeutic_category")),
        "presentation": medicament.get("presentation"),
        "company_name": medicament.get("company_name"),
        "status": medicament.get("status"),
        "dosage_form": medicament.get("dosage_form"),
        "availability": medicament.get("availability"),
        "related_info": medicament.get("related_info"),
        "discontinued_date": medicament.get("discontinued_date"),
        "shortage_reason": medicament.get("shortage_reason"),
    })

    medicament_id = resultat.fetchone()[0]  #fectchone pour récupérer l'id du médicament inséré

    openfda = medicament.get("openfda")
    if openfda:
        requete_openfda = text("""
            INSERT INTO openfda_details (
                medicament_id, brand_name, generic_name_openfda, manufacturer_name,
                product_type, route, substance_name, application_number
            ) VALUES (
                :medicament_id, :brand_name, :generic_name_openfda, :manufacturer_name,
                :product_type, :route, :substance_name, :application_number
            )
        """)
        conn.execute(requete_openfda, {
            "medicament_id": medicament_id,
            "brand_name": liste_vers_texte(openfda.get("brand_name")),
            "generic_name_openfda": liste_vers_texte(openfda.get("generic_name")),
            "manufacturer_name": liste_vers_texte(openfda.get("manufacturer_name")),
            "product_type": liste_vers_texte(openfda.get("product_type")),
            "route": liste_vers_texte(openfda.get("route")),
            "substance_name": liste_vers_texte(openfda.get("substance_name")),
            "application_number": liste_vers_texte(openfda.get("application_number")),
        })

        a_une_classification = any([
            openfda.get("pharm_class_epc"),
            openfda.get("pharm_class_cs"),
            openfda.get("pharm_class_moa"),
            openfda.get("pharm_class_pe"),
        ])
        if a_une_classification:
            requete_classification = text("""
                INSERT INTO classifications_pharma (
                    medicament_id, pharm_class_epc, pharm_class_cs,
                    pharm_class_moa, pharm_class_pe
                ) VALUES (
                    :medicament_id, :pharm_class_epc, :pharm_class_cs,
                    :pharm_class_moa, :pharm_class_pe
                )
            """)
            conn.execute(requete_classification, {
                "medicament_id": medicament_id,
                "pharm_class_epc": liste_vers_texte(openfda.get("pharm_class_epc")),
                "pharm_class_cs": liste_vers_texte(openfda.get("pharm_class_cs")),
                "pharm_class_moa": liste_vers_texte(openfda.get("pharm_class_moa")),
                "pharm_class_pe": liste_vers_texte(openfda.get("pharm_class_pe")),
            })


# ============================================
# EXÉCUTION PRINCIPALE
# ============================================
if __name__ == "__main__":
    medicaments = recuperer_toutes_les_donnees()

    nb_succes = 0
    nb_erreurs = 0

    with engine.connect() as conn:
        for i, medicament in enumerate(medicaments):
            try:
                inserer_medicament(conn, medicament)
                nb_succes += 1
            except Exception as e:
                nb_erreurs += 1
                print(f"[ERREUR ligne {i}] {medicament.get('generic_name', 'inconnu')} : {e}")
                continue
        conn.commit()

    print(f"\n[TERMINÉ] {nb_succes} médicaments insérés avec succès, {nb_erreurs} erreurs.")