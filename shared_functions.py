import pandas as pd


def garder_premiere_categorie(valeur):
    """
    Nettoie therapeutic_category en ne gardant que la première valeur
    avant la virgule. Utilisée à l'identique partout : à l'entraînement,
    dans l'app Streamlit, et dans le batch prediction — pour garantir que
    le modèle voit toujours la même transformation, peu importe où elle
    est appliquée.
    """
    if pd.isna(valeur):
        return "Inconnu"
    return valeur.split(",")[0].strip()


def encoder_et_aligner(df_features, colonnes_modele):
    """
    Prend un DataFrame avec les colonnes brutes (therapeutic_category,
    dosage_form, company_name), applique le même one-hot encoding que
    l'entraînement, puis force l'alignement exact sur colonnes_modele
    (mêmes colonnes, même ordre, 0 pour celles absentes).

    Fonctionne aussi bien pour une seule ligne (widget de prédiction)
    que pour un DataFrame entier (batch prediction).
    """
    df_encode = pd.get_dummies(df_features)
    df_aligne = df_encode.reindex(columns=colonnes_modele, fill_value=0)
    return df_aligne

