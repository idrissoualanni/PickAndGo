import streamlit as st
import pandas as pd
import requests
import time

URL_API = "https://script.google.com/macros/s/AKfycbwdl-W_s28jDO95Nxv10ZDMHfK4clTOAH2OHbH74Bpza2pROwezw22zZGwufklC9-Bgsg/exec"
USER_ID = "Client_5"

st.set_page_config(page_title="Pick & Go Dashboard", layout="wide")

# --- TITRE FIXE (Ne bouge jamais) ---
st.title("💳 Mon Espace Client Pick & Go")
st.write("Bienvenue dans votre interface de gestion de compte.")

# --- PARTIE RECHARGE FIXE (Ne bouge jamais) ---
# On la place en dehors du fragment pour que l'utilisateur puisse taper tranquillement
with st.expander("➕ Ajouter de l'argent sur mon compte"):
    montant_add = st.number_input("Somme à ajouter (FCFA)", min_value=100, step=500, key="recharge_val")
    if st.button("Confirmer le dépôt", key="btn_confirm"):
        try:
            requests.post(URL_API, json={"userID": USER_ID, "montant": montant_add, "action": "recharge"})
            st.success("Recharge réussie ! Les données vont se mettre à jour.")
        except:
            st.error("Erreur de connexion.")

st.divider()

# --- LE FRAGMENT : Seule cette partie s'actualise ---
@st.fragment(run_every=5) # Actualisation douce toutes les 5 secondes
def afficher_donnees_live():
    try:
        r = requests.get(URL_API, timeout=5)
        if r.status_code == 200:
            df = pd.DataFrame(r.json())
            # On harmonise les noms des colonnes
            df.columns = [c.strip().lower() for c in df.columns]
            
            user_df = df[df['utilisateur'].astype(str).str.lower() == USER_ID.lower()]
            
            if not user_df.empty:
                dernier_solde = user_df.iloc[-1]['nouveau solde']
                
                # Affichage du solde
                st.metric("Solde Actuel", f"{int(dernier_solde)} FCFA")
                
                st.subheader("🧾 Historique des achats")
                # On filtre les achats
                if 'action' in user_df.columns:
                    achats = user_df[user_df['action'] == 'achat'].iloc[::-1]
                    
                    for i, row in achats.iterrows():
                        col_a, col_b, col_c = st.columns([3, 1, 1])
                        col_a.write(f"🛍️ **{row['produit']}**")
                        col_b.write(f"{row['montant']} FCFA")
                        
                        # Bouton facture
                        txt = f"FACTURE\nClient: {USER_ID}\nArticle: {row['produit']}\nPrix: {row['montant']}\nDate: {row['date']}"
                        col_c.download_button("📥 Facture", txt, file_name=f"recu_{i}.txt", key=f"f_{i}")
                else:
                    st.warning("Colonne 'Action' non détectée.")
            else:
                st.info("En attente de votre première transaction...")
    except Exception as e:
        st.info("Recherche de nouvelles données...")

# Lancement du fragment
afficher_donnees_live()