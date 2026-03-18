import streamlit as st
import pandas as pd
import requests
import time
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

# --- STYLE PREMIUM ---
st.set_page_config(
    page_title="Pick & Go | Dashboard",
    
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- CONFIGURATION ---
URL_API = os.getenv("URL_API", "")
if not URL_API:
    st.error(" URL_API introuvable. Veuillez configurer le fichier .env !")
    st.stop()
USER_ID = "Client_5"

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Outfit', sans-serif;
    }
    
    .main {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    }
    
    .stMetric {
        background: rgba(255, 255, 255, 0.7);
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255, 255, 255, 0.3);
    }
    
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        background: linear-gradient(90deg, #4facfe 0%, #00f2fe 100%);
        color: white;
        border: none;
        padding: 10px 20px;
        font-weight: 600;
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 5px 15px rgba(79, 172, 254, 0.4);
    }
    
    .transaction-card {
        background: white;
        padding: 15px;
        border-radius: 12px;
        margin-bottom: 10px;
        border-left: 5px solid #4facfe;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
</style>
""", unsafe_allow_html=True)

# --- HEADER ---
col1, col2 = st.columns([3, 1])
with col1:
    st.title(" Pick & Go Smart Store")
    st.write(f"Connecté en tant que : **{USER_ID}**")
with col2:
    if st.button(" Actualiser"):
        st.rerun()

st.divider()

# --- ESPACE PORTEFEUILLE ---
col_stats1, col_stats2 = st.columns(2)

@st.fragment(run_every=10)
def wallet_section():
    try:
        r = requests.get(URL_API, timeout=5)
        if r.status_code == 200:
            df = pd.DataFrame(r.json())
            df.columns = [c.strip().lower() for c in df.columns]
            
            user_data = df[df['utilisateur'].astype(str).str.lower() == USER_ID.lower()]
            
            if not user_data.empty:
                dernier_solde = user_data.iloc[-1]['nouveau solde']
                with col_stats1:
                    st.metric("Solde Disponible", f"{int(dernier_solde)} FCFA", delta_color="normal")
                
                with col_stats2:
                    nb_achats = len(user_data[user_data['action'] == 'achat'])
                    st.metric("Total Achats", f"{nb_achats} articles")
                
                st.subheader("🧾 Historique Récent")
                # Affichage des transactions
                achats = user_data.iloc[::-1].head(10)
                for _, row in achats.iterrows():
                    icon = "" if row['action'] == 'achat' else ""
                    color = "#ff4b4b" if row['action'] == 'achat' else "#28a745"
                    
                    with st.container():
                        c1, c2, c3, c4 = st.columns([0.5, 3, 2, 2])
                        c1.write(icon)
                        c2.write(f"**{row['produit'] if row['action'] == 'achat' else 'Recharge'}**")
                        
                        # Add color styling to the amount based on action
                        amount_display = f"<span style='color:{color}; font-weight:bold;'>{'-' if row['action'] == 'achat' else '+'}{row['montant']} FCFA</span>"
                        c3.markdown(amount_display, unsafe_allow_html=True)
                        
                        # Bouton facture
                        if row['action'] == 'achat':
                            date_str = row['date'] if 'date' in row else datetime.now().strftime("%Y-%m-%d %H:%M")
                            txt = f"FACTURE PICK & GO\n-------------------\nClient: {USER_ID}\nArticle: {row['produit']}\nPrix: {row['montant']} FCFA\nDate: {date_str}\n\nMerci de votre visite !"
                            c4.download_button("📂 Recu", txt, file_name=f"facture_{row['produit']}.txt", key=f"btn_{time.time()}_{_}")
                        else:
                            c4.write(f" Complété")
            else:
                st.info("Aucune transaction trouvée pour ce compte.")
    except Exception as e:
        st.error("Impossible de récupérer les données. Vérifiez l'URL de votre API Apps Script.")

wallet_section()

# --- SECTION ACTIONS MANUELLES ---
st.sidebar.header("🕹️ Simulation Manuelle")
st.sidebar.caption("Testez le système sans la caméra")
sim_item = st.sidebar.selectbox("Produit", ["Bouteille Naturelle", "Bouteille Gazelle", "Bouteille Eau Kirene"])
sim_price = {"Bouteille Naturelle": 500, "Bouteille Gazelle": 1000, "Bouteille Eau Kirene": 250}[sim_item]

if st.sidebar.button(f"Simuler Achat ({sim_price} FCFA)", type="primary"):
    with st.sidebar:
        with st.spinner("Achat en cours..."):
            try:
                res = requests.post(URL_API, json={"userID": USER_ID, "produit": sim_item, "montant": sim_price, "action": "achat"})
                data = res.json()
                if data.get("status") == "success":
                    st.success(" Achat validé !")
                    time.sleep(1)
                    st.rerun()
                elif data.get("status") == "error":
                    st.error(f" Refusé : {data.get('message')}")
            except Exception as e:
                st.error("Erreur de connexion API.")

# --- SECTION RECHARGE ---
st.sidebar.header("➕ Recharger mon compte")
montant_add = st.sidebar.number_input("Montant (FCFA)", min_value=500, step=500, value=2000)
if st.sidebar.button("Confirmer la recharge"):
    with st.sidebar:
        with st.spinner("Traitement..."):
            try:
                res = requests.post(URL_API, json={"userID": USER_ID, "montant": montant_add, "action": "recharge"})
                if res.status_code == 200:
                    st.success(f"Compte crédité de {montant_add} FCFA !")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("Erreur lors de la recharge.")
            except:
                st.error("Erreur de connexion API.")

# --- FOOTER ---
st.sidebar.divider()
st.sidebar.info("Application propulsée par l'IA (YOLOv8) et Google Sheets.")