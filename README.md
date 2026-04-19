# D-corp KPI Bot — Indicateurs Logistiques

Bot Telegram d'automatisation des indicateurs logistiques pour l'entrepôt de stockage de D-corp.

Remplace le travail manuel de 2 à 4 heures par semaine du responsable logistique Denis GAUD, en automatisant l'extraction, le calcul, la mise en forme graphique et la génération de rapports PDF des indicateurs présentés lors des réunions **Point 15'** (hebdomadaire) et **Point 45'** (mensuelle).

---

## Table des matières

1. [Fonctionnalités](#fonctionnalités)
2. [Architecture du projet](#architecture-du-projet)
3. [Prérequis](#prérequis)
4. [Installation](#installation)
5. [Configuration](#configuration)
6. [Lancement](#lancement)
7. [Commandes Telegram](#commandes-telegram)
8. [Utilisation CLI (sans Telegram)](#utilisation-cli-sans-telegram)
9. [Rapports automatiques](#rapports-automatiques)
10. [Format des données WMS](#format-des-données-wms)
11. [Déploiement Raspberry Pi](#déploiement-raspberry-pi)
12. [Maintenance et dépannage](#maintenance-et-dépannage)

---

## Fonctionnalités

### Les 6 indicateurs calculés automatiquement

| # | Indicateur | Description |
|---|-----------|-------------|
| 1 | **Commandes traitées** | Nombre total, répartition par client (FOD, AZO, GAA, SMP) et par référence produit (13 Edriseurs) |
| 2 | **Délai de traitement interne** | Temps entre l'arrivée du bon de commande et l'expédition. Moyenne, médiane, min, max + détection automatique des anomalies (> 2× la médiane) |
| 3 | **Taux de transfert qualité** | Pourcentage de commandes passant par la zone de contrôle qualité (QUA), global et par client |
| 4 | **Cadence horaire par opérateur** | Nombre de mouvements par heure travaillée, par opérateur logistique (7 opérateurs) |
| 5 | **Lissage de la charge** | Quantités cumulées par jour, visualisation de la répartition de la charge de travail sur la période |
| 6 | **Indicateurs bonus** | Taux de service (expédié le jour même), top/flop 5 références, répartition de charge entre opérateurs |

### Automatisation complète

- Import des données CSV exportées du WMS (via Telegram ou en ligne de commande)
- Détection automatique du séparateur CSV (point-virgule ou virgule)
- Stockage dans une base SQLite locale pour requêtage rapide
- Génération de 10 graphiques (management visuel, couleurs contrastées)
- Génération d'un rapport PDF au format A3 paysage (prêt à imprimer)
- Nommage automatique : `2025_S49_Rapport_Hebdomadaire.pdf` ou `2025_M12_Rapport_Mensuel.pdf`
- Envoi automatique programmé chaque lundi matin (Point 15') et chaque 1er du mois (Point 45')

---

## Architecture du projet

```
dcorp_kpi_bot/
│
├── bot.py                  # Bot Telegram principal + scheduler APScheduler
├── config.py               # Configuration centralisée (tokens, couleurs, paramètres métier)
├── data_manager.py         # Ingestion CSV → SQLite (nettoyage, colonnes calculées, index)
├── kpi_engine.py           # Moteur de calcul des 6 KPIs (requêtes SQL + pandas)
├── charts.py               # Génération des graphiques matplotlib (10 graphiques)
├── pdf_report.py           # Assemblage du rapport PDF A3 avec ReportLab
├── formatters.py           # Formatage texte HTML pour les messages Telegram
├── generate_report.py      # Script CLI autonome (tests et génération sans Telegram)
│
├── .env                    # Variables d'environnement (TOKEN, IDs) — À CRÉER
├── .env.example            # Template du fichier .env
├── requirements.txt        # Dépendances Python
├── dcorp_kpi_bot.service   # Fichier service systemd (déploiement Raspberry Pi)
│
├── data/                   # Dossier pour les fichiers CSV du WMS
├── output/                 # Rapports PDF et graphiques PNG générés
└── README.md               # Ce fichier
```

### Flux de données

```
CSV du WMS ──→ data_manager.py ──→ SQLite ──→ kpi_engine.py ──→ charts.py ──→ pdf_report.py ──→ PDF A3
                                                    │
                                                    └──→ formatters.py ──→ Messages Telegram
```

---

## Prérequis

- **Python 3.10 ou supérieur** (testé avec Python 3.12)
- **Un bot Telegram** créé via @BotFather
- **pip** (gestionnaire de paquets Python)

### Vérifier votre version de Python

**Windows (PowerShell) :**
```powershell
python --version
```

**Mac (Terminal) :**
```bash
python3 --version
```

---

## Installation

### Étape 1 — Extraire le projet

Décompressez le fichier `dcorp_kpi_bot.zip` à l'emplacement de votre choix.

### Étape 2 — Ouvrir un terminal dans le dossier du projet

**Windows (PowerShell) :**
```powershell
cd C:\Users\VOTRE_NOM\Downloads\dcorp_kpi_bot\dcorp_kpi_bot
```

**Mac (Terminal) :**
```bash
cd ~/Downloads/dcorp_kpi_bot/dcorp_kpi_bot
```

### Étape 3 — Installer les dépendances Python

**Windows :**
```powershell
pip install -r requirements.txt
```

**Mac :**
```bash
pip3 install -r requirements.txt
```

Les dépendances installées sont :
- `python-telegram-bot` — interface avec l'API Telegram
- `python-dotenv` — lecture du fichier .env
- `pandas` — traitement des données CSV
- `matplotlib` + `seaborn` — génération des graphiques
- `reportlab` — génération des fichiers PDF
- `APScheduler` — programmation des envois automatiques

---

## Configuration

### Étape 1 — Créer le bot Telegram

1. Ouvrez Telegram et cherchez **@BotFather**
2. Envoyez `/newbot`
3. Choisissez un nom d'affichage (ex: `D-corp KPI Bot`)
4. Choisissez un username unique terminant par `bot` (ex: `dcorp_kpi_bot`)
5. BotFather vous donne un **token** de la forme `7123456789:AAH_xxxxxxxxxxxxxxxxxxxxx`
6. **Copiez ce token**, vous en aurez besoin

### Étape 2 — Trouver votre ID Telegram

1. Cherchez **@userinfobot** sur Telegram
2. Envoyez-lui `/start`
3. Il vous répond avec votre **ID** (un nombre comme `123456789`)

### Étape 3 — Créer le fichier .env

**Windows :**
```powershell
copy .env.example .env
```

**Mac :**
```bash
cp .env.example .env
```

### Étape 4 — Remplir le fichier .env

Ouvrez `.env` dans votre éditeur (Cursor, VS Code, Notepad...) et remplissez :

```properties
# Token du bot Telegram (obtenu via @BotFather à l'étape 1)
TELEGRAM_TOKEN=7123456789:AAH_votre_vrai_token_ici

# Votre ID Telegram (obtenu via @userinfobot à l'étape 2)
# Plusieurs IDs possibles, séparés par des virgules
ALLOWED_IDS=123456789

# Chat ID pour les rapports automatiques (optionnel)
# 0 = désactivé (les rapports ne sont envoyés que sur demande)
# Votre ID perso = rapports envoyés dans votre conversation privée
# ID négatif = rapports envoyés dans un groupe Telegram
AUTO_REPORT_CHAT_ID=0
```

**Important :** `AUTO_REPORT_CHAT_ID=0` désactive les envois automatiques. Le bot fonctionne normalement, mais uniquement à la demande (quand vous tapez une commande). Vous pouvez le configurer plus tard.

### Étape 5 — Placer le fichier CSV dans data/

Copiez votre fichier CSV exporté du WMS dans le dossier `data/` du projet.

**Windows :**
```powershell
copy C:\chemin\vers\dcorp_WMS_data.csv data\
```

**Mac :**
```bash
cp ~/Downloads/dcorp_WMS_data.csv data/
```

> **Note :** Le séparateur CSV est détecté automatiquement (virgule ou point-virgule). Si votre fichier est au format `.xls` ou `.xlsx`, ouvrez-le d'abord dans Excel et enregistrez-le au format **CSV (séparateur point-virgule)**.

### Étape 6 — Importer les données dans la base

**Windows :**
```powershell
python generate_report.py --import-all
```

**Mac :**
```bash
python3 generate_report.py --import-all
```

Vous devriez voir : `✅ 9941 lignes importées au total` (ou un nombre similaire selon votre jeu de données).

---

## Lancement

### Lancer le bot Telegram

**Windows :**
```powershell
python bot.py
```

**Mac :**
```bash
python3 bot.py
```

Le terminal affiche :
```
Bot prêt. Démarrage du polling...
```

Le bot tourne maintenant. **Laissez le terminal ouvert** — si vous le fermez, le bot s'arrête.

Pour arrêter le bot : appuyez sur `Ctrl+C` dans le terminal.

### Premier test sur Telegram

1. Ouvrez Telegram et cherchez votre bot par son username
2. Envoyez `/start` — le bot doit répondre avec un message d'accueil
3. Envoyez `/kpi S49` — résumé des indicateurs de la semaine 49
4. Envoyez `/rapport S49` — génère et envoie le rapport PDF complet

---

## Commandes Telegram

### Commandes principales

| Commande | Description | Exemple |
|----------|-------------|---------|
| `/start` | Message d'accueil | `/start` |
| `/help` | Liste de toutes les commandes | `/help` |
| `/kpi [période]` | Résumé rapide de tous les KPIs | `/kpi S49` |
| `/rapport [période]` | Génère et envoie le rapport PDF complet + dashboard | `/rapport M12` |
| `/semaines` | Liste des périodes disponibles dans la base | `/semaines` |
| `/status` | État de la base de données (nb lignes, plage de dates) | `/status` |

### Commandes détaillées par indicateur

| Commande | Description | Exemple |
|----------|-------------|---------|
| `/commandes [période]` | Détail commandes par client et par référence | `/commandes S50` |
| `/delais [période]` | Délais de traitement + anomalies | `/delais S49` |
| `/qualite [période]` | Taux de transfert qualité | `/qualite S51` |
| `/cadence [période]` | Cadence horaire par opérateur | `/cadence S52` |
| `/charge [période]` | Lissage de charge + graphique | `/charge M12` |

### Format des périodes

| Format | Signification | Exemple |
|--------|--------------|---------|
| `S49` | Semaine 49 | `/kpi S49` |
| `S 49` | Semaine 49 (avec espace) | `/kpi S 49` |
| `49` | Semaine 49 (raccourci) | `/kpi 49` |
| `M12` | Mois de décembre | `/rapport M12` |
| `M 12` | Mois de décembre (avec espace) | `/rapport M 12` |
| *(rien)* | Dernière semaine disponible | `/kpi` |

### Import de données via Telegram

Vous pouvez envoyer un nouveau fichier `.csv` directement au bot dans la conversation. Il l'importera automatiquement dans la base de données.

---

## Utilisation CLI (sans Telegram)

Le script `generate_report.py` permet de générer des rapports sans passer par Telegram. Utile pour les tests ou la génération en lot.

### Importer des données

**Windows :**
```powershell
# Importer tous les CSV du dossier data/
python generate_report.py --import-all

# Importer un fichier spécifique
python generate_report.py --import-file data\mon_fichier.csv
```

**Mac :**
```bash
# Importer tous les CSV du dossier data/
python3 generate_report.py --import-all

# Importer un fichier spécifique
python3 generate_report.py --import-file data/mon_fichier.csv
```

### Générer des rapports

**Windows :**
```powershell
# Rapport hebdomadaire semaine 49
python generate_report.py --week 49

# Rapport mensuel décembre
python generate_report.py --month 12

# Tous les rapports pour toutes les périodes
python generate_report.py --all

# Avec une année spécifique
python generate_report.py --week 49 --year 2025
```

**Mac :**
```bash
# Rapport hebdomadaire semaine 49
python3 generate_report.py --week 49

# Rapport mensuel décembre
python3 generate_report.py --month 12

# Tous les rapports pour toutes les périodes
python3 generate_report.py --all
```

Les fichiers générés (PDF + graphiques PNG) se trouvent dans le dossier `output/`.

---

## Rapports automatiques

Si `AUTO_REPORT_CHAT_ID` est configuré dans `.env` (différent de `0`), le bot envoie automatiquement :

| Rapport | Fréquence | Horaire | Contenu |
|---------|-----------|---------|---------|
| **Point 15'** | Chaque lundi | 07h00 (heure de Paris) | Résumé texte + dashboard + PDF de la dernière semaine |
| **Point 45'** | Chaque 1er du mois | 07h00 (heure de Paris) | Résumé texte + dashboard + PDF du mois écoulé |

### Comment configurer

1. Récupérez l'ID du chat cible :
   - **Chat privé** : utilisez @userinfobot pour obtenir votre ID
   - **Groupe** : ajoutez le bot au groupe, envoyez un message, puis consultez `https://api.telegram.org/botVOTRE_TOKEN/getUpdates` pour trouver le `chat.id` (nombre négatif)

2. Mettez à jour `.env` :
```properties
AUTO_REPORT_CHAT_ID=123456789
```

3. Redémarrez le bot.

---

## Format des données WMS

Le fichier CSV exporté du WMS doit contenir les colonnes suivantes :

| Colonne | Type | Description |
|---------|------|-------------|
| `Operation_ID` | texte | Identifiant unique de l'opération (ex: OP296811) |
| `Operator_ID` | texte | ID de l'opérateur (A999999 = système, A000017 = humain) |
| `Operation_type` | texte | `ORDER` (réception commande) ou `MOVE` (mouvement physique) |
| `Operation_timestamp` | nombre | Timestamp Unix en secondes |
| `OHH_code` | nombre | Code OHH |
| `Location_from` | texte | Zone d'origine du mouvement |
| `Location_to` | texte | Zone de destination du mouvement |
| `Reference_ID` | texte | Code référence produit (ex: P00C37) |
| `Reference_name` | texte | Nom du produit (ex: Edriseur type "C37") |
| `Qty` | nombre | Quantité déplacée |
| `TKID_code` | nombre | Code tracking |
| `Order_ID` | texte | ID commande, dont le préfixe identifie le client (FOD, AZO, GAA, SMP) |
| `Operation_status` | texte | Statut de l'opération (OK) |

Le séparateur (virgule `,` ou point-virgule `;`) est détecté automatiquement.

### Flux logistique dans l'entrepôt

```
ORDER (bon de commande)
   │
   ▼
  PROD (zone de production / réception)
   │
   ├──→ ST10 (stockage zone 10)
   │      │
   │      ├──→ QUA (contrôle qualité) ──→ retour ST10/ST20
   │      │
   │      └──→ TPA (zone de préparation)
   │
   └──→ ST20 (stockage zone 20)
          │
          ├──→ QUA (contrôle qualité) ──→ retour ST10/ST20
          │
          └──→ TPA (zone de préparation)
                 │
                 ▼
               SHIP (quai d'expédition) ──→ Livraison client
```

### Calcul des indicateurs à partir des données

- **Commandes** : lignes avec `Operation_type = ORDER` (une par commande)
- **Délai de traitement** : `timestamp(dernier MOVE vers SHIP) - timestamp(ORDER)` pour chaque `Order_ID`
- **Transfert qualité** : commandes dont au moins un MOVE a `Location_to = QUA`
- **Cadence** : nombre de MOVE par opérateur / heures travaillées (estimées via premier et dernier MOVE du jour)
- **Charge** : somme des `Qty` de tous les MOVE par jour

---

## Déploiement Raspberry Pi

Pour un fonctionnement permanent (24h/24), déployez le bot sur un Raspberry Pi.

### Installation

```bash
# Copier le projet sur le Pi
scp -r dcorp_kpi_bot/ pi@adresse_ip_du_pi:~/

# Se connecter au Pi
ssh pi@adresse_ip_du_pi

# Aller dans le dossier
cd ~/dcorp_kpi_bot

# Installer les dépendances
pip3 install -r requirements.txt

# Configurer
cp .env.example .env
nano .env
# Remplir TELEGRAM_TOKEN, ALLOWED_IDS, AUTO_REPORT_CHAT_ID
```

### Créer le service systemd

```bash
# Copier le fichier de service
sudo cp dcorp_kpi_bot.service /etc/systemd/system/

# Recharger systemd
sudo systemctl daemon-reload

# Activer le démarrage automatique
sudo systemctl enable dcorp_kpi_bot

# Démarrer le bot
sudo systemctl start dcorp_kpi_bot

# Vérifier que ça tourne
sudo systemctl status dcorp_kpi_bot
```

### Commandes utiles sur le Pi

```bash
# Voir les logs en temps réel
journalctl -u dcorp_kpi_bot -f

# Voir les 50 dernières lignes de log
journalctl -u dcorp_kpi_bot -n 50

# Redémarrer le bot
sudo systemctl restart dcorp_kpi_bot

# Arrêter le bot
sudo systemctl stop dcorp_kpi_bot
```

---

## Maintenance et dépannage

### Problèmes fréquents

| Problème | Cause | Solution |
|----------|-------|----------|
| `InvalidToken` | Token mal copié dans `.env` | Vérifiez le token, sauvegardez le fichier (Ctrl+S) |
| `Base de données vide` | Pas de données importées | Placez un CSV dans `data/` puis lancez `--import-all` |
| `KeyError: 'Operation_timestamp'` | Mauvais séparateur CSV | Le fichier est peut-être un `.xls` — convertissez-le en CSV via Excel |
| `0 lignes importées` | Aucun fichier `.csv` dans `data/` | Vérifiez l'extension du fichier (doit être `.csv`, pas `.xls`) |
| `Aucune donnée pour cette période` | La période demandée n'existe pas | Tapez `/semaines` pour voir les périodes disponibles |
| `Accès non autorisé` | Votre ID n'est pas dans `ALLOWED_IDS` | Ajoutez votre ID Telegram dans `.env` |
| Bot ne répond pas | Le terminal a été fermé | Relancez `python bot.py` (ou déployez sur Raspberry Pi) |
| Graphiques vides | Les données ne couvrent pas la période | Vérifiez avec `/status` la plage de dates en base |

### Réinitialiser la base de données

Si vous souhaitez repartir de zéro :

**Windows :**
```powershell
del dcorp_kpi.db
python generate_report.py --import-all
```

**Mac :**
```bash
rm dcorp_kpi.db
python3 generate_report.py --import-all
```

### Mettre à jour les données

Deux méthodes :

1. **Via Telegram** : envoyez le nouveau fichier `.csv` directement au bot dans la conversation
2. **Via le terminal** : placez le CSV dans `data/` et lancez `python generate_report.py --import-all`

Les nouvelles données sont ajoutées à la base (les doublons sont ignorés via l'`Operation_ID`).

---

## Crédits

Développé dans le cadre du projet **MLT2 — Développement d'applications informatiques** pour D-corp Logistique.

Responsable logistique : Denis GAUD (denisgaud@gmail.com)

### Stack technique

- Python 3.12
- pandas (traitement de données)
- matplotlib + seaborn (graphiques)
- ReportLab (génération PDF)
- python-telegram-bot (API Telegram)
- APScheduler (planification des envois)
- SQLite (base de données locale)