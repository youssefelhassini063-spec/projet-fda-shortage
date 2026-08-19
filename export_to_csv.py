import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

engine = create_engine(f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}")

requete = text("""
    SELECT m.id, m.generic_name, m.status, m.therapeutic_category, 
           m.dosage_form, m.company_name, m.initial_posting_date,
           o.brand_name, o.route
    FROM medicaments m
    LEFT JOIN openfda_details o ON m.id = o.medicament_id
""")

with engine.connect() as conn:
    df_export = pd.read_sql(requete, conn)

df_export.to_csv("medicaments_export.csv", index=False)
print(f"[EXPORT] {len(df_export)} lignes exportées vers medicaments_export.csv")


