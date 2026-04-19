"""
Configuration du bot D-corp KPI Logistique.
Toutes les variables sensibles sont lues depuis .env
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ── Telegram ────────────────────────────────────────────────
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
# IDs Telegram autorisés (séparés par des virgules dans .env)
ALLOWED_IDS = [
    int(x.strip())
    for x in os.getenv("ALLOWED_IDS", "").split(",")
    if x.strip()
]
# Chat ID pour les envois automatiques (groupe ou individuel)
AUTO_REPORT_CHAT_ID = int(os.getenv("AUTO_REPORT_CHAT_ID", "0"))

# ── Chemins ─────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
DB_PATH = os.path.join(BASE_DIR, "dcorp_kpi.db")

# Créer les dossiers s'ils n'existent pas
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ── Paramètres métier ───────────────────────────────────────
# Séparateur CSV du WMS
CSV_SEPARATOR = ";"

# Mapping clients (préfixe Order_ID → nom complet)
CLIENT_NAMES = {
    "FOD": "FOD",
    "AZO": "AZO",
    "GAA": "GAA",
    "SMP": "SMP",
}

# Opérateur système (à exclure des cadences)
SYSTEM_OPERATOR = "A999999"

# Locations clés dans le flux logistique
LOC_SHIP = "SHIP"      # Quai d'expédition
LOC_QUA = "QUA"         # Zone de contrôle qualité
LOC_PROD = "PROD"       # Zone de production / réception

# Seuil de délai anormal (multiplicateur de la médiane)
ANOMALY_THRESHOLD = 2.0

# Heures planifiées de travail par jour (pour cadence théorique)
PLANNED_HOURS_PER_DAY = 8.0

# ── Scheduler (envois automatiques) ─────────────────────────
# Point 15' : chaque lundi matin
WEEKLY_REPORT_DAY = "mon"
WEEKLY_REPORT_HOUR = 7
WEEKLY_REPORT_MINUTE = 0

# Point 45' : le 1er de chaque mois
MONTHLY_REPORT_DAY = 1
MONTHLY_REPORT_HOUR = 7
MONTHLY_REPORT_MINUTE = 0

# ── Couleurs des graphiques (management visuel) ─────────────
COLORS = {
    "primary":    "#1B4F72",   # Bleu marine
    "secondary":  "#2E86C1",   # Bleu clair
    "accent":     "#E67E22",   # Orange
    "success":    "#27AE60",   # Vert
    "danger":     "#E74C3C",   # Rouge
    "warning":    "#F39C12",   # Jaune
    "neutral":    "#7F8C8D",   # Gris
    "background": "#FAFAFA",   # Fond clair
    "text":       "#2C3E50",   # Texte sombre
}

# Palette pour les clients
CLIENT_COLORS = {
    "FOD": "#2E86C1",
    "AZO": "#E67E22",
    "GAA": "#27AE60",
    "SMP": "#8E44AD",
}

# Palette pour les opérateurs
OPERATOR_COLORS = [
    "#1B4F72", "#2E86C1", "#E67E22", "#27AE60",
    "#E74C3C", "#8E44AD", "#F39C12",
]
