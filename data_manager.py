"""
Module d'ingestion des données WMS → SQLite.
Lit les CSV exportés du WMS, nettoie et stocke dans la base locale.
"""
import os
import sqlite3
import pandas as pd
import logging
from datetime import datetime

from config import DB_PATH, DATA_DIR, CSV_SEPARATOR, SYSTEM_OPERATOR

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
#  SCHEMA
# ════════════════════════════════════════════════════════════

SCHEMA = """
CREATE TABLE IF NOT EXISTS operations (
    operation_id    TEXT PRIMARY KEY,
    operator_id     TEXT NOT NULL,
    operation_type  TEXT NOT NULL,        -- ORDER | MOVE
    timestamp_utc   TEXT NOT NULL,        -- ISO 8601
    timestamp_unix  REAL NOT NULL,
    ohh_code        REAL,
    location_from   TEXT,
    location_to     TEXT,
    reference_id    TEXT,
    reference_name  TEXT,
    qty             REAL,
    tkid_code       REAL,
    order_id        TEXT NOT NULL,
    operation_status TEXT,
    -- Colonnes calculées
    date_str        TEXT NOT NULL,        -- YYYY-MM-DD
    week_number     INTEGER NOT NULL,
    year            INTEGER NOT NULL,
    hour            INTEGER NOT NULL,
    client_code     TEXT NOT NULL         -- 3 premiers caractères de order_id
);

CREATE INDEX IF NOT EXISTS idx_ops_type ON operations(operation_type);
CREATE INDEX IF NOT EXISTS idx_ops_order ON operations(order_id);
CREATE INDEX IF NOT EXISTS idx_ops_week ON operations(year, week_number);
CREATE INDEX IF NOT EXISTS idx_ops_operator ON operations(operator_id);
CREATE INDEX IF NOT EXISTS idx_ops_date ON operations(date_str);
CREATE INDEX IF NOT EXISTS idx_ops_locs ON operations(location_from, location_to);

CREATE TABLE IF NOT EXISTS import_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    rows_count  INTEGER NOT NULL
);
"""


def get_connection() -> sqlite3.Connection:
    """Retourne une connexion SQLite avec WAL activé."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Crée le schéma si nécessaire."""
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    logger.info("Base de données initialisée : %s", DB_PATH)


# ════════════════════════════════════════════════════════════
#  IMPORT CSV
# ════════════════════════════════════════════════════════════

def import_csv(filepath: str, replace: bool = False) -> int:
    """
    Importe un fichier CSV WMS dans la base SQLite.

    Args:
        filepath: chemin du fichier CSV
        replace: si True, remplace les doublons (sinon ignore)

    Returns:
        nombre de lignes importées
    """
    logger.info("Import CSV : %s", filepath)

# Lecture du CSV avec détection automatique du séparateur
    try:
        df = pd.read_csv(filepath, sep=CSV_SEPARATOR)
        if len(df.columns) <= 1:
            raise ValueError("Séparateur incorrect")
    except (ValueError, Exception):
        df = pd.read_csv(filepath, sep=None, engine="python")

    # Nettoyage des noms de colonnes
    df.columns = df.columns.str.strip()

    # Conversion du timestamp Unix → datetime
    df["dt"] = pd.to_datetime(df["Operation_timestamp"], unit="s", utc=True)

    # Supprimer les lignes sans timestamp valide
    df = df.dropna(subset=["Operation_timestamp"]).copy()

    # Colonnes calculées (convertir en timezone-naive pour éviter les NaN)
    dt_naive = df["dt"].dt.tz_localize(None)
    df["date_str"] = dt_naive.dt.strftime("%Y-%m-%d")
    df["week_number"] = dt_naive.dt.isocalendar().week.astype("Int64").fillna(0).astype(int)
    df["year"] = dt_naive.dt.year.astype(int)
    df["hour"] = dt_naive.dt.hour.astype(int)
    df["client_code"] = df["Order_ID"].str[:3]
    df["timestamp_utc"] = dt_naive.dt.strftime("%Y-%m-%dT%H:%M:%S")

    # Préparation pour l'insertion
    records = []
    for _, row in df.iterrows():
        records.append((
            row["Operation_ID"],
            row["Operator_ID"],
            row["Operation_type"],
            row["timestamp_utc"],
            float(row["Operation_timestamp"]),
            row["OHH_code"] if pd.notna(row["OHH_code"]) else None,
            row["Location_from"] if pd.notna(row["Location_from"]) else None,
            row["Location_to"] if pd.notna(row["Location_to"]) else None,
            row["Reference_ID"] if pd.notna(row["Reference_ID"]) else None,
            row["Reference_name"] if pd.notna(row["Reference_name"]) else None,
            row["Qty"] if pd.notna(row["Qty"]) else None,
            row["TKID_code"] if pd.notna(row["TKID_code"]) else None,
            row["Order_ID"],
            row["Operation_status"] if pd.notna(row["Operation_status"]) else None,
            row["date_str"],
            int(row["week_number"]),
            int(row["year"]),
            int(row["hour"]),
            row["client_code"],
        ))

    # Insertion en base
    conn = get_connection()
    conflict = "REPLACE" if replace else "IGNORE"
    conn.executemany(
        f"""INSERT OR {conflict} INTO operations
        (operation_id, operator_id, operation_type, timestamp_utc,
         timestamp_unix, ohh_code, location_from, location_to,
         reference_id, reference_name, qty, tkid_code, order_id,
         operation_status, date_str, week_number, year, hour, client_code)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        records,
    )

    # Log d'import
    conn.execute(
        "INSERT INTO import_log (filename, imported_at, rows_count) VALUES (?,?,?)",
        (os.path.basename(filepath), datetime.now().isoformat(), len(records)),
    )

    conn.commit()
    inserted = conn.total_changes
    conn.close()

    logger.info("Import terminé : %d lignes traitées", len(records))
    return len(records)


def import_all_csv_in_data_dir(replace: bool = False) -> int:
    """Importe tous les CSV trouvés dans DATA_DIR."""
    total = 0
    for fname in sorted(os.listdir(DATA_DIR)):
        if fname.lower().endswith(".csv"):
            total += import_csv(os.path.join(DATA_DIR, fname), replace=replace)
    return total


# ════════════════════════════════════════════════════════════
#  REQUÊTES UTILITAIRES
# ════════════════════════════════════════════════════════════

def get_available_weeks() -> list[tuple[int, int]]:
    """Retourne la liste des (année, semaine) disponibles, triées."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT DISTINCT year, week_number FROM operations ORDER BY year, week_number"
    ).fetchall()
    conn.close()
    return [(r["year"], r["week_number"]) for r in rows]


def get_available_months() -> list[tuple[int, int]]:
    """Retourne la liste des (année, mois) disponibles."""
    conn = get_connection()
    rows = conn.execute(
        """SELECT DISTINCT
            CAST(strftime('%Y', timestamp_utc) AS INTEGER) as year,
            CAST(strftime('%m', timestamp_utc) AS INTEGER) as month
        FROM operations
        ORDER BY year, month"""
    ).fetchall()
    conn.close()
    return [(r["year"], r["month"]) for r in rows]


def get_date_range() -> tuple[str, str]:
    """Retourne (date_min, date_max) des données."""
    conn = get_connection()
    row = conn.execute(
        "SELECT MIN(date_str) as dmin, MAX(date_str) as dmax FROM operations"
    ).fetchone()
    conn.close()
    return (row["dmin"], row["dmax"])


def get_row_count() -> int:
    """Nombre total de lignes en base."""
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) as cnt FROM operations").fetchone()
    conn.close()
    return row["cnt"]


# ════════════════════════════════════════════════════════════
#  INIT AU CHARGEMENT DU MODULE
# ════════════════════════════════════════════════════════════

init_db()
