// Pick & Go — Google Apps Script
// Deployer : Application Web | Executer en tant que : Moi | Acces : Toute personne
// Copier l URL deploye et la mettre dans .env -> URL_API

var SHEET_TRANSACTIONS = "Transactions";
var SHEET_UTILISATEURS = "Utilisateurs";
var SOLDE_INITIAL      = 5000; // FCFA offerts a la creation du compte

// ─────────────────────────────────────────────
// POST : achat ou recharge
// ─────────────────────────────────────────────
function doPost(e) {
  try {
    var data    = JSON.parse(e.postData.contents);
    var userID  = (data.userID  || "").toString().trim();
    var montant = parseFloat(data.montant) || 0;
    var action  = (data.action  || "achat").toString().toLowerCase();
    var produit = (data.produit || "N/A").toString();

    if (!userID) return jsonResponse({status:"error", message:"userID manquant"});

    var ss        = SpreadsheetApp.getActiveSpreadsheet();
    var userSheet = getOrCreateSheet(ss, SHEET_UTILISATEURS, ["Utilisateur","Solde"]);
    var txSheet   = getOrCreateSheet(ss, SHEET_TRANSACTIONS,
                      ["Date","Utilisateur","Produit","Montant","Action","Nouveau Solde"]);

    var userInfo     = getUser(userSheet, userID);
    var solde        = userInfo.solde;
    var rowIndex     = userInfo.rowIndex;
    var nouveauSolde = solde;

    if (action === "achat") {
      if (solde < montant) {
        return jsonResponse({status:"error", message:"Solde insuffisant ("+solde+" FCFA)"});
      }
      nouveauSolde = solde - montant;
    } else if (action === "recharge") {
      nouveauSolde = solde + montant;
    } else {
      return jsonResponse({status:"error", message:"Action inconnue: "+action});
    }

    userSheet.getRange(rowIndex, 2).setValue(nouveauSolde);
    var dateStr = Utilities.formatDate(new Date(), Session.getScriptTimeZone(), "yyyy-MM-dd HH:mm:ss");
    txSheet.appendRow([dateStr, userID, produit, montant, action, nouveauSolde]);

    return jsonResponse({
      status:        "success",
      nouveau_solde: nouveauSolde,
      message:       action === "achat" ? produit+" achete" : "Recharge de "+montant+" FCFA"
    });

  } catch(err) {
    return jsonResponse({status:"error", message:"Erreur serveur: "+err.toString()});
  }
}

// ─────────────────────────────────────────────
// GET : historique des transactions
// ─────────────────────────────────────────────
function doGet(e) {
  try {
    var ss    = SpreadsheetApp.getActiveSpreadsheet();
    var sheet = ss.getSheetByName(SHEET_TRANSACTIONS);

    if (!sheet || sheet.getLastRow() < 2) {
      return ContentService.createTextOutput("[]").setMimeType(ContentService.MimeType.JSON);
    }

    var data    = sheet.getDataRange().getValues();
    var headers = data[0];
    var rows    = [];

    for (var i = 1; i < data.length; i++) {
      var obj = {};
      for (var j = 0; j < headers.length; j++) {
        var val = data[i][j];
        if (val instanceof Date) {
          val = Utilities.formatDate(val, Session.getScriptTimeZone(), "yyyy-MM-dd HH:mm:ss");
        }
        obj[headers[j]] = val;
      }
      rows.push(obj);
    }

    return ContentService
      .createTextOutput(JSON.stringify(rows))
      .setMimeType(ContentService.MimeType.JSON);

  } catch(err) {
    return jsonResponse({status:"error", message:err.toString()});
  }
}

// ─────────────────────────────────────────────
// Utilitaires internes
// ─────────────────────────────────────────────
function jsonResponse(obj) {
  return ContentService
    .createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}

function getOrCreateSheet(ss, name, headers) {
  var sheet = ss.getSheetByName(name);
  if (!sheet) { sheet = ss.insertSheet(name); sheet.appendRow(headers); }
  return sheet;
}

function getUser(userSheet, userID) {
  var rows = userSheet.getDataRange().getValues();
  for (var i = 1; i < rows.length; i++) {
    if (rows[i][0].toString().toLowerCase() === userID.toLowerCase()) {
      return { solde: parseFloat(rows[i][1]) || 0, rowIndex: i + 1 };
    }
  }
  // Creer le compte avec solde de bienvenue
  userSheet.appendRow([userID, SOLDE_INITIAL]);
  return { solde: SOLDE_INITIAL, rowIndex: userSheet.getLastRow() };
}

// ─────────────────────────────────────────────
// Initialisation manuelle (lancer une seule fois)
// ─────────────────────────────────────────────
function initialiserSheets() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();

  var tx = ss.getSheetByName(SHEET_TRANSACTIONS);
  if (tx) tx.clear(); else tx = ss.insertSheet(SHEET_TRANSACTIONS);
  tx.appendRow(["Date","Utilisateur","Produit","Montant","Action","Nouveau Solde"]);

  var users = ss.getSheetByName(SHEET_UTILISATEURS);
  if (users) users.clear(); else users = ss.insertSheet(SHEET_UTILISATEURS);
  users.appendRow(["Utilisateur","Solde"]);
  users.appendRow(["Client_5", SOLDE_INITIAL]);

  Logger.log("OK — Client_5 initialise avec "+SOLDE_INITIAL+" FCFA");
}
