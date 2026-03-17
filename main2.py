import requests

# REMPLACE PAR TON URL /exec
URL_API = "https://script.google.com/macros/s/AKfycbwdl-W_s28jDO95Nxv10ZDMHfK4clTOAH2OHbH74Bpza2pROwezw22zZGwufklC9-Bgsg/exec"

def simulation_client():
    # TEST 1 : Recharge de 5000 FCFA
    print("💰 Tentative de recharge...")
    r1 = requests.post(URL_API, json={
        "userID": "Client_5",
        "montant": 5000,
        "action": "recharge",
        "produit": "Recharge Guichet"
    })
    print(f"Réponse Recharge : {r1.text}")

    # TEST 2 : Achat d'une bouteille de 500 FCFA
    print("🛍️ Tentative d'achat...")
    r2 = requests.post(URL_API, json={
        "userID": "Client_5",
        "montant": 500,
        "action": "achat",
        "produit": "Bouteille Eau 1.5L"
    })
    print(f"Réponse Achat : {r2.text}")

if __name__ == "__main__":
    simulation_client()