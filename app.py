import streamlit as st
import pandas as pd
import joblib
from shared_functions import garder_premiere_categorie, encoder_et_aligner

# ============================================
# CONFIG PAGE
# ============================================
st.set_page_config(
    page_title="Drug Shortages Monitor",
    page_icon="💊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================
# SNAPSHOT DATE — change this line each time you refresh the pipeline
# ============================================
SNAPSHOT_DATE = "2026-08-12"

# ============================================
# CUSTOM CSS — design tokens
# ============================================
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=IBM+Plex+Mono:wght@500;600&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

.stApp {
    background-color: #F8F9FB;
}

section[data-testid="stSidebar"] {
    background-color: #FFFFFF;
    border-right: 1px solid #E2E5EA;
}

/* KPI card */
.kpi-card {
    background: #FFFFFF;
    border: 1px solid #E2E5EA;
    border-radius: 10px;
    padding: 18px 20px;
    box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
}
.kpi-label {
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    color: #64748B;
    margin-bottom: 6px;
}
.kpi-value {
    font-family: 'IBM Plex Mono', monospace;
    font-size: 28px;
    font-weight: 600;
    color: #1E293B;
}

/* Badges */
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 600;
}
.badge-current { background: #DBEAFE; color: #1D4ED8; }
.badge-discontinued { background: #FEE2E2; color: #B91C1C; }
.badge-resolved { background: #E2E8F0; color: #475569; }

/* Snapshot pulse chip */
.pulse-chip {
    display: flex;
    align-items: center;
    gap: 8px;
    background: #F1F5F9;
    border: 1px solid #E2E5EA;
    border-radius: 8px;
    padding: 10px 12px;
    font-size: 12.5px;
    color: #475569;
    margin-top: 6px;
}
.pulse-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #2563EB;
    flex-shrink: 0;
}

/* Prediction result box */
.pred-box {
    border-radius: 10px;
    padding: 20px 24px;
    border: 1px solid #E2E5EA;
}
.pred-temp { background: #EFF6FF; border-color: #BFDBFE; }
.pred-def { background: #FEF2F2; border-color: #FECACA; }

h1, h2, h3 { color: #1E293B; }
</style>
""", unsafe_allow_html=True)

# ============================================
# HELPERS
# ============================================
def badge_html(status):
    mapping = {
        "Current": ("Current", "badge-current"),
        "To Be Discontinued": ("Discontinued", "badge-discontinued"),
        "Resolved": ("Resolved", "badge-resolved"),
    }
    label, css_class = mapping.get(status, (status, "badge-resolved"))
    return f'<span class="badge {css_class}">{label}</span>'

def kpi_card(label, value):
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-label">{label}</div>
        <div class="kpi-value">{value}</div>
    </div>
    """, unsafe_allow_html=True)

# ============================================
# DATA & MODEL LOADING
# ============================================
@st.cache_data
def charger_donnees():
    df = pd.read_csv("medicaments_export.csv")
    df["therapeutic_category_clean"] = df["therapeutic_category"].apply(garder_premiere_categorie)
    return df

@st.cache_resource
def charger_modele():
    modele = joblib.load("modele_random_forest.pkl")
    colonnes_modele = joblib.load("colonnes_modele.pkl")
    return modele, colonnes_modele

df = charger_donnees()
modele, colonnes_modele = charger_modele()

# ============================================
# SIDEBAR — navigation context + filters + snapshot info
# ============================================
with st.sidebar:
    st.markdown("### 💊 Drug Shortages Monitor")
    st.caption("FDA shortage data — point-in-time snapshot")

    st.markdown(f"""
    <div class="pulse-chip">
        <div class="pulse-dot"></div>
        <div>Snapshot frozen on <b>{SNAPSHOT_DATE}</b>. The live FDA API changes daily — this is not a real-time feed.</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()
    st.markdown("**Filters** (apply to Explore tab)")

    filtre_statut = st.multiselect(
        "Status",
        options=sorted(df["status"].unique()),
        default=sorted(df["status"].unique())
    )
    filtre_categorie = st.multiselect(
        "Therapeutic category",
        options=sorted(df["therapeutic_category_clean"].unique())
    )
    recherche_nom = st.text_input("Search by name")

# ============================================
# HEADER
# ============================================
st.title("Drug Shortages Monitor")
st.caption("Overview, prediction, and exploration of FDA-reported drug shortage data.")

# ============================================
# TABS — progressive disclosure instead of one long scroll
# ============================================
tab_overview, tab_predict, tab_explore = st.tabs(["📊 Overview", "🔮 Predict", "🔍 Explore"])

# ------------------------------------------------
# TAB 1 — OVERVIEW
# ------------------------------------------------
with tab_overview:
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card("Total drugs", len(df))
    with c2:
        kpi_card("Current", int((df["status"] == "Current").sum()))
    with c3:
        kpi_card("Discontinued", int((df["status"] == "To Be Discontinued").sum()))
    with c4:
        kpi_card("Resolved", int((df["status"] == "Resolved").sum()))

    st.write("")
    st.info(
        "The model was trained only on **Current** and **To Be Discontinued** records. "
        "**Resolved** cases (~1.5% of the data) are shown here for context but were "
        "excluded from training — too rare to model reliably."
    )

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Status distribution")
        st.bar_chart(df["status"].value_counts())
    with col_b:
        st.subheader("Top 10 therapeutic categories")
        st.bar_chart(df["therapeutic_category_clean"].value_counts().head(10))

    st.subheader("Top dosage forms")
    st.bar_chart(df["dosage_form"].value_counts().head(10))

# ------------------------------------------------
# TAB 2 — PREDICT
# ------------------------------------------------
with tab_predict:
    st.subheader("Predict shortage outcome")
    st.write(
        "Choose a drug's characteristics to estimate whether a similar shortage "
        "would resolve as **Temporary** or become **Definitive**."
    )

    with st.form("formulaire_prediction"):
        c1, c2, c3 = st.columns(3)
        with c1:
            categorie_choisie = st.selectbox(
                "Therapeutic category",
                sorted(df["therapeutic_category_clean"].unique())
            )
        with c2:
            forme_choisie = st.selectbox(
                "Dosage form",
                sorted(df["dosage_form"].dropna().unique())
            )
        with c3:
            entreprise_choisie = st.selectbox(
                "Company",
                sorted(df["company_name"].dropna().unique())
            )
        valider = st.form_submit_button("Predict")

    if valider:
        entree = pd.DataFrame([{
            "therapeutic_category": categorie_choisie,
            "dosage_form": forme_choisie,
            "company_name": entreprise_choisie
        }])
        entree_alignee = encoder_et_aligner(entree, colonnes_modele)

        prediction = modele.predict(entree_alignee)[0]
        proba = modele.predict_proba(entree_alignee)[0]
        confiance = proba[prediction]

        st.write("")
        if prediction == 1:
            st.markdown(f"""
            <div class="pred-box pred-def">
                <span class="badge badge-discontinued">Definitive</span>
                <div style="margin-top:10px; font-family:'IBM Plex Mono'; font-size:22px; color:#1E293B;">
                    Confidence: {confiance:.1%}
                </div>
            </div>
            """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
            <div class="pred-box pred-temp">
                <span class="badge badge-current">Temporary</span>
                <div style="margin-top:10px; font-family:'IBM Plex Mono'; font-size:22px; color:#1E293B;">
                    Confidence: {confiance:.1%}
                </div>
            </div>
            """, unsafe_allow_html=True)

        st.caption(
            f"Temporary: {proba[0]:.1%} · Definitive: {proba[1]:.1%}. "
            "The model's recall on Definitive cases is limited — treat this as a signal, not a certainty."
        )

# ------------------------------------------------
# TAB 3 — EXPLORE
# ------------------------------------------------
with tab_explore:
    df_filtre = df[df["status"].isin(filtre_statut)]
    if filtre_categorie:
        df_filtre = df_filtre[df_filtre["therapeutic_category_clean"].isin(filtre_categorie)]
    if recherche_nom:
        df_filtre = df_filtre[df_filtre["generic_name"].str.contains(recherche_nom, case=False, na=False)]

    st.subheader(f"{len(df_filtre)} result(s)")

    df_affiche = df_filtre[[
        "generic_name", "brand_name", "status", "therapeutic_category_clean",
        "dosage_form", "company_name", "route", "initial_posting_date"
    ]].rename(columns={"therapeutic_category_clean": "therapeutic_category"}).copy()

    df_affiche["status"] = df_affiche["status"].apply(badge_html)

    st.write(
        df_affiche.to_html(escape=False, index=False),
        unsafe_allow_html=True
    )

