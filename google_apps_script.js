function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Transactions");
  var userSheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Utilisateurs");
  
  if (!sheet) {
    sheet = SpreadsheetApp.getActiveSpreadsheet().insertSheet("Transactions");
    sheet.appendRow(["Date", "Utilisateur", "Produit", "Montant", "Action", "Nouveau Solde"]);
  }
  
  if (!userSheet) {
    userSheet = SpreadsheetApp.getActiveSpreadsheet().insertSheet("Utilisateurs");
    userSheet.appendRow(["Utilisateur", "Solde"]);
    userSheet.appendRow(["Client_5", 5000]); // Exemple par défaut
  }

  var data = JSON.parse(e.postData.contents);
  var userID = data.userID || "Client_Inconnu";
  var montant = parseFloat(data.montant) || 0;
  var action = data.action || "achat"; // 'achat' ou 'recharge'
  var produit = data.produit || "N/A";

  // 1. Trouver l'utilisateur et son solde actuel
  var userRows = userSheet.getDataRange().getValues();
  var userRowIndex = -1;
  var soldeActuel = 0;

  for (var i = 1; i < userRows.length; i++) {
    if (userRows[i][0] == userID) {
      userRowIndex = i + 1;
      soldeActuel = userRows[i][1];
      break;
    }
  }

  // Si l'utilisateur n'existe pas, on le crée
  if (userRowIndex == -1) {
    userSheet.appendRow([userID, 5000]); // Offre de bienvenue de 5000 FCFA
    userRowIndex = userSheet.getLastRow();
    soldeActuel = 5000;
  }

  // 2. Calculer le nouveau solde
  var nouveauSolde = soldeActuel;
  if (action == "achat") {
    if (soldeActuel >= montant) {
      nouveauSolde = soldeActuel - montant;
    } else {
      return ContentService.createTextOutput(JSON.stringify({"status": "error", "message": "Solde insuffisant"}))
             .setMimeType(ContentService.MimeType.JSON);
    }
  } else if (action == "recharge") {
    nouveauSolde = soldeActuel + montant;
  }

  // 3. Mettre à jour les feuilles
  userSheet.getRange(userRowIndex, 2).setValue(nouveauSolde);
  sheet.appendRow([new Date(), userID, produit, montant, action, nouveauSolde]);

  return ContentService.createTextOutput(JSON.stringify({
    "status": "success", 
    "nouveau_solde": nouveauSolde
  })).setMimeType(ContentService.MimeType.JSON);
}

function doGet(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheetByName("Transactions");
  if (!sheet) return ContentService.createTextOutput("[]").setMimeType(ContentService.MimeType.JSON);
  
  var data = sheet.getDataRange().getValues();
  var headers = data[0];
  var json = [];

  for (var i = 1; i < data.length; i++) {
    var obj = {};
    for (var j = 0; j < headers.length; j++) {
      obj[headers[j]] = data[i][j];
    }
    json.push(obj);
  }

  return ContentService.createTextOutput(JSON.stringify(json))
         .setMimeType(ContentService.MimeType.JSON);
}

function initialiserSheet() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  
  // 1. Initialiser la feuille Transactions
  var sheet = ss.getSheetByName("Transactions");
  if (sheet) {
    sheet.clear();
  } else {
    sheet = ss.insertSheet("Transactions");
  }
  sheet.appendRow(["Date", "Utilisateur", "Produit", "Montant", "Action", "Nouveau Solde"]);
  
  // 2. Initialiser la feuille Utilisateurs
  var userSheet = ss.getSheetByName("Utilisateurs");
  if (userSheet) {
    userSheet.clear();
  } else {
    userSheet = ss.insertSheet("Utilisateurs");
  }
  userSheet.appendRow(["Utilisateur", "Solde"]);
  userSheet.appendRow(["Client_5", 5000]); // Compte de test
  
  Logger.log("Initialisation terminée ! Les feuilles Transactions et Utilisateurs ont été créées.");
}
