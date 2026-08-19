import pandas as pd
from sqlalchemy import create_engine, text
from sklearn.model_selection import train_test_split
from dotenv import load_dotenv
import os

# ============================================
# CONNEXION À LA BASE (réutilise le .env existant)
# ============================================
load_dotenv()
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

engine = create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")


# ============================================
# ÉTAPE 1 : EXTRACTION depuis PostgreSQL vers Pandas
# ============================================
requete = text("""
    SELECT status, therapeutic_category, dosage_form, company_name
    FROM medicaments
    WHERE status IN ('Current', 'To Be Discontinued')
""")

with engine.connect() as conn:
    df = pd.read_sql(requete, conn)

print(f"[EXTRACTION] {len(df)} lignes récupérées (Resolved exclu)")
print(df.head())


# ============================================
# ÉTAPE 2 : NETTOYAGE de therapeutic_category
# ============================================
def garder_premiere_categorie(valeur):
    if valeur is None:
        return "Inconnu" 
    # Sépare sur la virgule et garde le premier élément, en enlevant les espaces
    return valeur.split(",")[0].strip() # to extract the very first piece of a text string that has been divided by a comma, and then clean up any extra spaces around that piece.

df["therapeutic_category"] = df["therapeutic_category"].apply(garder_premiere_categorie)

print(f"[NETTOYAGE] Nombre de catégories uniques après nettoyage : {df['therapeutic_category'].nunique()}")


# ============================================
# ÉTAPE 3 : CRÉATION de la cible numérique    it calls label encoding, which is a technique used to convert categorical labels into numerical values. In this case, the 'status' column is being mapped to a new column called 'cible', where "Current" is mapped to 0 and "To Be Discontinued" is mapped to 1. This transformation is essential for machine learning models that require numerical input.
# ============================================
df["cible"] = df["status"].map({"Current": 0, "To Be Discontinued": 1})

print(f"[CIBLE] Répartition :\n{df['cible'].value_counts()}")


# ============================================
# ÉTAPE 4 : ONE-HOT ENCODING des 3 features --> in simple words, one-hot encoding is a method used to convert categorical variables into a format that can be provided to machine learning algorithms to improve predictions. It creates new binary columns for each unique category in the original categorical column. For example, if you have a column "Color" with categories "Red", "Green", and "Blue", one-hot encoding will create three new columns: "Color_Red", "Color_Green", and "Color_Blue". Each row will have a 1 in the column corresponding to its color and 0s in the others. This allows the model to understand categorical data without assuming any ordinal relationship between the categories.
# ============================================
features_a_encoder = ["therapeutic_category", "dosage_form", "company_name"]

df_encode = pd.get_dummies(df, columns=features_a_encoder, drop_first=True) # we do drop_first=True to avoid the dummy variable trap, which can lead to multicollinearity in regression models. By dropping the first category, we ensure that the remaining categories are independent of each other.

print(f"[ENCODING] Nombre de colonnes après encoding : {df_encode.shape[1]}") # shape[1] gives the number of columns in the DataFrame, which is useful to see how many features we have after one-hot encoding.


# ============================================
# ÉTAPE 5 : SÉPARER FEATURES (X) et CIBLE (y)
# ============================================
X = df_encode.drop(columns=["status", "cible"])  # tout sauf le texte original et la cible # feature metrix
y = df_encode["cible"] # the traget columsn or the traget vetor what i want to predict 

print(f"[X/y] X a {X.shape[1]} colonnes (features) | y a {len(y)} valeurs (cible)") # shape(1) gives the number of columns in the DataFrame, which is useful to see how many features we have after one-hot encoding.

# ============================================
# ÉTAPE 6 : SPLIT TRAIN/TEST
# ============================================
X_train, X_test, y_train, y_test = train_test_split(
    X, y, 
    test_size=0.2,        # 20% pour le test, 80% pour l'entraînement
    random_state=42,       # pour que le split soit reproductible (toujours le même découpage)
    stratify=y              # garde la même proportion Temporaire/Définitif dans train et test
)

print(f"[SPLIT] Train : {len(X_train)} lignes | Test : {len(X_test)} lignes")
print(f"[SPLIT] Répartition cible dans Train :\n{y_train.value_counts(normalize=True)}")
print(f"[SPLIT] Répartition cible dans Test :\n{y_test.value_counts(normalize=True)}")



from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, 
    f1_score, confusion_matrix, classification_report
)
import pandas as pd

# ============================================
# ÉTAPE 1 : ENTRAÎNEMENT du modèle
# ============================================
modele = RandomForestClassifier(
    n_estimators=100,      # nombre d'arbres dans la forêt
    random_state=42,        # reproductibilité
    max_depth=10 ,            # limite la profondeur de chaque arbre (évite l'overfitting)
    class_weight='balanced',

)

modele.fit(X_train, y_train)
print("[ENTRAÎNEMENT] Modèle entraîné avec succès.")


# ============================================
# ÉTAPE 2 : PRÉDICTIONS sur le Test (jamais vu par le modèle)
# ============================================
y_pred = modele.predict(X_test)


# ============================================
# ÉTAPE 3 : ÉVALUATION honnête (pas juste Accuracy)
# ============================================
accuracy = accuracy_score(y_test, y_pred)
precision = precision_score(y_test, y_pred)
recall = recall_score(y_test, y_pred)
f1 = f1_score(y_test, y_pred)

print(f"\n[ÉVALUATION]")
print(f"Accuracy  : {accuracy:.3f}")
print(f"Precision : {precision:.3f}")
print(f"Recall    : {recall:.3f}")
print(f"F1-score  : {f1:.3f}")

print(f"\n[MATRICE DE CONFUSION]")
print(confusion_matrix(y_test, y_pred))

print(f"\n[RAPPORT DÉTAILLÉ]")
print(classification_report(y_test, y_pred, target_names=["Temporaire", "Définitif"]))


# ============================================
# ÉTAPE 4 : FEATURE IMPORTANCE (validation croisée avec ton analyse manuelle)
# ============================================
importances = pd.DataFrame({
    "feature": X_train.columns,
    "importance": modele.feature_importances_
}).sort_values("importance", ascending=False)

print(f"\n[TOP 15 FEATURES LES PLUS IMPORTANTES]")
print(importances.head(15)) 

import joblib 

# ============================================
# SAUVEGARDE DU MODÈLE ET DES COLONNES
# ============================================
joblib.dump(modele, "modele_random_forest.pkl")

# On sauvegarde aussi la LISTE exacte des colonnes utilisées à l'entraînement
# (indispensable pour que Streamlit encode les futures entrées de la même façon)
joblib.dump(list(X_train.columns), "colonnes_modele.pkl")

print("[SAUVEGARDE] Modèle et colonnes sauvegardés avec succès.")








