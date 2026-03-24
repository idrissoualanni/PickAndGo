"""
Pick & Go — Dashboard Streamlit.
Affiche le solde, l'historique et permet la simulation manuelle.
"""

import time
import os
import requests
import pandas as pd
import streamlit as st
from datetime import datetime
from dotenv import load_dotenv

from config import PRODUCTS

load_dotenv()

URL_API = os.getenv("URL_API", "")
USER_ID = "Client_5"

st.set_page_config(page_title="Pick & Go | Dashboard", layout="wide", initial_sidebar_state="collapsed")

if not URL_API:
    st.error("URL_API introuvable. Configurez le fichier .env !")
    st.stop()

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap');
    html, body, [class*="css"] { font-family: 'Outfit', sans-serif; }
    .main { background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }
    .stMetric {
        background: rgba(255,255,255,0.7);
        padding: 20px; border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.3);
    }
    .stButton>button {
        width: 100%; border-radius: 10px;
        background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%);
        color: white; border: none; padding: 10px 20px;
        font-weight: 600; transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(79,172,254,0.4);
    }
</style>
""", unsafe_allow_html=True)

# --- Header ---
col1, col2 = st.columns([3, 1])
with col1:
    st.title("🛒 Pick & Go Smart Store")
    st.write(f"Connecté : **{USER_ID}**")
with col2:
    if st.button("🔄 Actualiser"):
        st.rerun()

st.divider()

col_stat1, col_stat2 = st.columns(2)


# --- Portefeuille (auto-refresh 10s) ---
@st.fragment(run_every=10)
def wallet_section():
    try:
        r = requests.get(URL_API, timeout=5)
        r.raise_for_status()
        df = pd.DataFrame(r.json())
        df.columns = [c.strip().lower() for c in df.columns]

        if df.empty:
            st.info("Aucune donnée disponible.")
            return

        if "utilisateur" not in df.columns:
            st.error("Format de base invalide (colonne 'Utilisateur' manquante).")
            return

        user_df = df[df["utilisateur"].astype(str).str.lower() == USER_ID.lower()]

        if user_df.empty:
            st.info("Aucune transaction trouvée pour ce compte.")
            return

        # Solde
        if "nouveau solde" in user_df.columns and not user_df["nouveau solde"].empty:
            solde = int(user_df.iloc[-1]["nouveau solde"])
            with col_stat1:
                st.metric("Solde Disponible", f"{solde} FCFA")
        else:
            with col_stat1:
                st.metric("Solde Disponible", "--- FCFA")

        # Nb achats
        with col_stat2:
            nb = len(user_df[user_df["action"] == "achat"]) if "action" in user_df.columns else 0
            st.metric("Total Achats", f"{nb} articles")

        # Historique
        st.subheader("🧾 Historique Récent")
        for _, row in user_df.iloc[::-1].head(10).iterrows():
            is_achat = row.get("action") == "achat"
            icon     = "🛒" if is_achat else "➕"
            color    = "#ff4b4b" if is_achat else "#28a745"
            sign     = "-" if is_achat else "+"
            label    = row.get("produit", "?") if is_achat else "Recharge"
            montant  = row.get("montant", 0)
            date_str = str(row.get("date", datetime.now().strftime("%Y-%m-%d %H:%M")))

            c1, c2, c3, c4 = st.columns([0.5, 3, 2, 2])
            c1.write(icon)
            c2.write(f"**{label}**")
            c3.markdown(
                f"<span style='color:{color};font-weight:bold;'>{sign}{montant} FCFA</span>",
                unsafe_allow_html=True,
            )
            if is_achat:
                receipt = (
                    f"FACTURE PICK & GO\n-------------------\n"
                    f"Client : {USER_ID}\nArticle : {label}\n"
                    f"Prix    : {montant} FCFA\nDate    : {date_str}\n\nMerci !"
                )
                c4.download_button(
                    "📂 Reçu", receipt,
                    file_name=f"facture_{label}.txt",
                    key=f"dl_{time.time()}_{_}",
                )
            else:
                c4.write("✅ Complété")

    except Exception:
        st.error("Impossible de récupérer les données. Vérifiez l'URL API.")


wallet_section()

# --- Simulation manuelle ---
product_names  = [info["nom"] for info in PRODUCTS.values()]
price_by_name  = {info["nom"]: info["prix"] for info in PRODUCTS.values()}

st.sidebar.header("🕹️ Simulation Manuelle")
st.sidebar.caption("Testez sans la caméra")
sim_item  = st.sidebar.selectbox("Produit", product_names)
sim_price = price_by_name[sim_item]

if st.sidebar.button(f"Simuler Achat ({sim_price} FCFA)", type="primary"):
    with st.sidebar, st.spinner("Achat en cours..."):
        try:
            res  = requests.post(URL_API, json={"userID": USER_ID, "produit": sim_item, "montant": sim_price, "action": "achat"})
            data = res.json()
            if data.get("status") == "success":
                st.sidebar.success("✅ Achat validé !")
                time.sleep(1)
                st.rerun()
            else:
                st.sidebar.error(f"❌ Refusé : {data.get('message')}")
        except Exception:
            st.sidebar.error("Erreur de connexion API.")

# --- Recharge ---
st.sidebar.header("➕ Recharger mon compte")
montant_add = st.sidebar.number_input("Montant (FCFA)", min_value=500, step=500, value=2000)
if st.sidebar.button("Confirmer la recharge"):
    with st.sidebar, st.spinner("Traitement..."):
        try:
            res = requests.post(URL_API, json={"userID": USER_ID, "montant": montant_add, "action": "recharge"})
            if res.status_code == 200:
                st.sidebar.success(f"✅ Compte crédité de {montant_add} FCFA !")
                time.sleep(1)
                st.rerun()
            else:
                st.sidebar.error("Erreur lors de la recharge.")
        except Exception:
            st.sidebar.error("Erreur de connexion API.")

st.sidebar.divider()
st.sidebar.info("Propulsé par YOLOv8 & Google Sheets.")
