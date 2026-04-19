"""
Moteur de calcul des KPIs logistiques D-corp.
Chaque fonction retourne un dictionnaire prêt à être graphé ou affiché.
"""
import sqlite3
import pandas as pd
import logging
from typing import Optional

from config import SYSTEM_OPERATOR, ANOMALY_THRESHOLD
from data_manager import get_connection

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════

def _week_filter(year: int, week: int) -> str:
    """Clause SQL pour filtrer sur une semaine ISO."""
    return f"year = {year} AND week_number = {week}"


def _month_filter(year: int, month: int) -> str:
    """Clause SQL pour filtrer sur un mois."""
    return f"CAST(strftime('%Y', timestamp_utc) AS INTEGER) = {year} AND CAST(strftime('%m', timestamp_utc) AS INTEGER) = {month}"


def _period_filter(period_type: str, year: int, value: int) -> str:
    """Retourne la clause SQL selon le type de période."""
    if period_type == "week":
        return _week_filter(year, value)
    elif period_type == "month":
        return _month_filter(year, value)
    else:
        raise ValueError(f"Type de période inconnu : {period_type}")


def _period_label(period_type: str, year: int, value: int) -> str:
    """Label lisible pour une période."""
    if period_type == "week":
        return f"Semaine {value} - {year}"
    else:
        mois = [
            "", "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
            "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
        ]
        return f"{mois[value]} {year}"


# ════════════════════════════════════════════════════════════
#  KPI 1 : NOMBRE DE COMMANDES TRAITÉES
# ════════════════════════════════════════════════════════════

def kpi_commandes(period_type: str, year: int, value: int) -> dict:
    """
    Nombre de commandes traitées, répartition par client et par référence.

    Returns:
        {
            "label": str,
            "total_commandes": int,
            "par_client": {client: count},
            "par_reference": {ref: count},
            "detail_client_ref": {client: {ref: count}},
        }
    """
    filtre = _period_filter(period_type, year, value)
    conn = get_connection()

    # Total commandes (lignes ORDER)
    total = conn.execute(
        f"SELECT COUNT(*) as cnt FROM operations WHERE operation_type='ORDER' AND {filtre}"
    ).fetchone()["cnt"]

    # Par client
    rows_client = conn.execute(
        f"""SELECT client_code, COUNT(*) as cnt
        FROM operations
        WHERE operation_type='ORDER' AND {filtre}
        GROUP BY client_code
        ORDER BY cnt DESC"""
    ).fetchall()
    par_client = {r["client_code"]: r["cnt"] for r in rows_client}

    # Par référence (via les MOVE liés aux commandes de la période)
    # Les ORDER n'ont pas de reference_name, on passe par les MOVE
    rows_ref = conn.execute(
        f"""SELECT reference_name, COUNT(DISTINCT order_id) as cnt
        FROM operations
        WHERE operation_type='MOVE'
        AND reference_name IS NOT NULL
        AND order_id IN (
            SELECT DISTINCT order_id FROM operations
            WHERE operation_type='ORDER' AND {filtre}
        )
        GROUP BY reference_name
        ORDER BY cnt DESC"""
    ).fetchall()
    par_reference = {r["reference_name"]: r["cnt"] for r in rows_ref}

    # Détail croisé client × référence
    rows_detail = conn.execute(
        f"""SELECT client_code, reference_name, COUNT(DISTINCT o2.order_id) as cnt
        FROM operations o2
        WHERE operation_type='MOVE'
        AND reference_name IS NOT NULL
        AND order_id IN (
            SELECT DISTINCT order_id FROM operations
            WHERE operation_type='ORDER' AND {filtre}
        )
        GROUP BY client_code, reference_name
        ORDER BY client_code, cnt DESC"""
    ).fetchall()
    detail = {}
    for r in rows_detail:
        client = r["client_code"]
        if client not in detail:
            detail[client] = {}
        detail[client][r["reference_name"]] = r["cnt"]

    conn.close()

    return {
        "label": _period_label(period_type, year, value),
        "total_commandes": total,
        "par_client": par_client,
        "par_reference": par_reference,
        "detail_client_ref": detail,
    }


# ════════════════════════════════════════════════════════════
#  KPI 2 : DÉLAI DE TRAITEMENT INTERNE
# ════════════════════════════════════════════════════════════

def kpi_delais(period_type: str, year: int, value: int) -> dict:
    """
    Délai de traitement = timestamp(dernière opération SHIP) - timestamp(ORDER).

    Returns:
        {
            "label": str,
            "nb_commandes": int,
            "delai_moyen_min": float,
            "delai_median_min": float,
            "delai_max_min": float,
            "delai_min_min": float,
            "distribution": [(order_id, delai_min)],
            "par_client": {client: delai_moyen},
            "anomalies": [(order_id, delai_min)],
        }
    """
    filtre = _period_filter(period_type, year, value)
    conn = get_connection()

    # Timestamp ORDER par commande
    orders = pd.read_sql_query(
        f"""SELECT order_id, client_code, MIN(timestamp_unix) as order_ts
        FROM operations
        WHERE operation_type='ORDER' AND {filtre}
        GROUP BY order_id""",
        conn,
    )

    # Timestamp dernière expédition (SHIP) par commande
    ships = pd.read_sql_query(
        f"""SELECT order_id, MAX(timestamp_unix) as ship_ts
        FROM operations
        WHERE operation_type='MOVE' AND location_to='SHIP'
        AND order_id IN (
            SELECT DISTINCT order_id FROM operations
            WHERE operation_type='ORDER' AND {filtre}
        )
        GROUP BY order_id""",
        conn,
    )

    conn.close()

    # Jointure
    merged = orders.merge(ships, on="order_id", how="inner")
    merged["delai_sec"] = merged["ship_ts"] - merged["order_ts"]
    merged["delai_min"] = merged["delai_sec"] / 60.0

    if merged.empty:
        return {
            "label": _period_label(period_type, year, value),
            "nb_commandes": 0,
            "delai_moyen_min": 0,
            "delai_median_min": 0,
            "delai_max_min": 0,
            "delai_min_min": 0,
            "distribution": [],
            "par_client": {},
            "anomalies": [],
        }

    median = merged["delai_min"].median()
    threshold = median * ANOMALY_THRESHOLD
    anomalies = merged[merged["delai_min"] > threshold][
        ["order_id", "delai_min"]
    ].values.tolist()

    # Délai moyen par client
    par_client = (
        merged.groupby("client_code")["delai_min"]
        .mean()
        .round(1)
        .to_dict()
    )

    return {
        "label": _period_label(period_type, year, value),
        "nb_commandes": len(merged),
        "delai_moyen_min": round(merged["delai_min"].mean(), 1),
        "delai_median_min": round(median, 1),
        "delai_max_min": round(merged["delai_min"].max(), 1),
        "delai_min_min": round(merged["delai_min"].min(), 1),
        "distribution": merged[["order_id", "delai_min"]].values.tolist(),
        "par_client": par_client,
        "anomalies": anomalies,
    }


# ════════════════════════════════════════════════════════════
#  KPI 3 : TAUX DE TRANSFERT QUALITÉ
# ════════════════════════════════════════════════════════════

def kpi_qualite(period_type: str, year: int, value: int) -> dict:
    """
    Taux de transfert qualité = commandes passant par QUA / total commandes.

    Returns:
        {
            "label": str,
            "total_commandes": int,
            "commandes_qua": int,
            "taux_qua_pct": float,
            "par_client": {client: {"total": int, "qua": int, "taux": float}},
        }
    """
    filtre = _period_filter(period_type, year, value)
    conn = get_connection()

    # Total commandes de la période
    total = conn.execute(
        f"SELECT COUNT(*) as cnt FROM operations WHERE operation_type='ORDER' AND {filtre}"
    ).fetchone()["cnt"]

    # Commandes passées par QUA
    qua_count = conn.execute(
        f"""SELECT COUNT(DISTINCT order_id) as cnt
        FROM operations
        WHERE operation_type='MOVE' AND location_to='QUA'
        AND order_id IN (
            SELECT DISTINCT order_id FROM operations
            WHERE operation_type='ORDER' AND {filtre}
        )"""
    ).fetchone()["cnt"]

    # Par client
    rows = conn.execute(
        f"""SELECT client_code,
            COUNT(DISTINCT order_id) as total_orders
        FROM operations
        WHERE operation_type='ORDER' AND {filtre}
        GROUP BY client_code"""
    ).fetchall()

    par_client = {}
    for r in rows:
        client = r["client_code"]
        t = r["total_orders"]
        q = conn.execute(
            f"""SELECT COUNT(DISTINCT order_id) as cnt
            FROM operations
            WHERE operation_type='MOVE' AND location_to='QUA'
            AND client_code=?
            AND order_id IN (
                SELECT DISTINCT order_id FROM operations
                WHERE operation_type='ORDER' AND {filtre}
            )""",
            (client,),
        ).fetchone()["cnt"]
        par_client[client] = {
            "total": t,
            "qua": q,
            "taux": round(q / t * 100, 1) if t > 0 else 0.0,
        }

    conn.close()

    return {
        "label": _period_label(period_type, year, value),
        "total_commandes": total,
        "commandes_qua": qua_count,
        "taux_qua_pct": round(qua_count / total * 100, 1) if total > 0 else 0.0,
        "par_client": par_client,
    }


# ════════════════════════════════════════════════════════════
#  KPI 4 : CADENCE HORAIRE PAR OPÉRATEUR
# ════════════════════════════════════════════════════════════

def kpi_cadence(period_type: str, year: int, value: int) -> dict:
    """
    Cadence = nombre de MOVEs / heures travaillées par opérateur.
    Les heures travaillées sont estimées via premier et dernier MOVE du jour.

    Returns:
        {
            "label": str,
            "operateurs": {
                operator_id: {
                    "total_moves": int,
                    "total_hours": float,
                    "days_worked": int,
                    "cadence_moy": float,
                    "qty_totale": float,
                }
            }
        }
    """
    filtre = _period_filter(period_type, year, value)
    conn = get_connection()

    df = pd.read_sql_query(
        f"""SELECT operator_id, date_str, timestamp_unix, qty
        FROM operations
        WHERE operation_type='MOVE'
        AND operator_id != '{SYSTEM_OPERATOR}'
        AND {filtre}""",
        conn,
    )
    conn.close()

    if df.empty:
        return {"label": _period_label(period_type, year, value), "operateurs": {}}

    # Par opérateur et par jour : premier/dernier move
    daily = df.groupby(["operator_id", "date_str"]).agg(
        first_ts=("timestamp_unix", "min"),
        last_ts=("timestamp_unix", "max"),
        nb_moves=("operator_id", "count"),
        qty_day=("qty", "sum"),
    ).reset_index()

    daily["hours"] = (daily["last_ts"] - daily["first_ts"]) / 3600.0
    # Minimum 30 min par jour (si un seul move)
    daily.loc[daily["hours"] < 0.5, "hours"] = 0.5

    # Agrégation par opérateur
    result = {}
    for op_id, grp in daily.groupby("operator_id"):
        result[op_id] = {
            "total_moves": int(grp["nb_moves"].sum()),
            "total_hours": round(grp["hours"].sum(), 1),
            "days_worked": len(grp),
            "cadence_moy": round(grp["nb_moves"].sum() / grp["hours"].sum(), 1),
            "qty_totale": round(grp["qty_day"].sum(), 0),
        }

    return {
        "label": _period_label(period_type, year, value),
        "operateurs": result,
    }


# ════════════════════════════════════════════════════════════
#  KPI 5 : LISSAGE DE LA CHARGE (CUMUL)
# ════════════════════════════════════════════════════════════

def kpi_charge(period_type: str, year: int, value: int) -> dict:
    """
    Quantités cumulées par jour pour visualiser le lissage de la charge.

    Returns:
        {
            "label": str,
            "par_jour": {date: {"qty": float, "nb_commandes": int, "nb_moves": int}},
            "cumul_qty": {date: float},
            "cumul_commandes": {date: int},
        }
    """
    filtre = _period_filter(period_type, year, value)
    conn = get_connection()

    # Quantités déplacées par jour (MOVE uniquement)
    df_moves = pd.read_sql_query(
        f"""SELECT date_str, SUM(qty) as total_qty, COUNT(*) as nb_moves
        FROM operations
        WHERE operation_type='MOVE' AND {filtre}
        GROUP BY date_str
        ORDER BY date_str""",
        conn,
    )

    # Commandes par jour
    df_orders = pd.read_sql_query(
        f"""SELECT date_str, COUNT(*) as nb_orders
        FROM operations
        WHERE operation_type='ORDER' AND {filtre}
        GROUP BY date_str
        ORDER BY date_str""",
        conn,
    )

    conn.close()

    # Fusion
    df = df_moves.merge(df_orders, on="date_str", how="outer").fillna(0)
    df = df.sort_values("date_str")

    par_jour = {}
    for _, row in df.iterrows():
        par_jour[row["date_str"]] = {
            "qty": float(row["total_qty"]),
            "nb_commandes": int(row["nb_orders"]),
            "nb_moves": int(row["nb_moves"]),
        }

    # Cumuls
    cumul_qty = {}
    cumul_cmd = {}
    running_qty = 0.0
    running_cmd = 0
    for date in sorted(par_jour.keys()):
        running_qty += par_jour[date]["qty"]
        running_cmd += par_jour[date]["nb_commandes"]
        cumul_qty[date] = running_qty
        cumul_cmd[date] = running_cmd

    return {
        "label": _period_label(period_type, year, value),
        "par_jour": par_jour,
        "cumul_qty": cumul_qty,
        "cumul_commandes": cumul_cmd,
    }


# ════════════════════════════════════════════════════════════
#  KPI 6 : INDICATEURS BONUS
# ════════════════════════════════════════════════════════════

def kpi_bonus(period_type: str, year: int, value: int) -> dict:
    """
    Indicateurs supplémentaires :
    - Taux de service (expédié le jour même)
    - Top/Flop références par volume
    - Répartition de charge entre opérateurs
    - Anomalies de délai

    Returns:
        dict avec toutes les sous-sections
    """
    filtre = _period_filter(period_type, year, value)
    conn = get_connection()

    # ── Taux de service (même jour) ──
    df_svc = pd.read_sql_query(
        f"""SELECT o1.order_id, o1.date_str as order_date,
            (SELECT MAX(o2.date_str) FROM operations o2
             WHERE o2.order_id = o1.order_id
             AND o2.operation_type='MOVE' AND o2.location_to='SHIP') as ship_date
        FROM operations o1
        WHERE o1.operation_type='ORDER' AND {filtre}""",
        conn,
    )
    df_svc = df_svc.dropna(subset=["ship_date"])
    same_day = (df_svc["order_date"] == df_svc["ship_date"]).sum()
    taux_service = round(same_day / len(df_svc) * 100, 1) if len(df_svc) > 0 else 0.0

    # ── Top références par volume ──
    df_refs = pd.read_sql_query(
        f"""SELECT reference_name, SUM(qty) as total_qty,
            COUNT(DISTINCT order_id) as nb_orders
        FROM operations
        WHERE operation_type='MOVE' AND reference_name IS NOT NULL
        AND order_id IN (
            SELECT DISTINCT order_id FROM operations
            WHERE operation_type='ORDER' AND {filtre}
        )
        GROUP BY reference_name
        ORDER BY total_qty DESC""",
        conn,
    )

    top_refs = df_refs.head(5)[["reference_name", "total_qty", "nb_orders"]].to_dict("records")
    flop_refs = df_refs.tail(5)[["reference_name", "total_qty", "nb_orders"]].to_dict("records")

    # ── Répartition de charge (% moves par opérateur) ──
    df_charge = pd.read_sql_query(
        f"""SELECT operator_id, COUNT(*) as nb_moves, SUM(qty) as total_qty
        FROM operations
        WHERE operation_type='MOVE' AND operator_id != '{SYSTEM_OPERATOR}'
        AND {filtre}
        GROUP BY operator_id
        ORDER BY nb_moves DESC""",
        conn,
    )
    total_moves = df_charge["nb_moves"].sum()
    repartition = {}
    for _, row in df_charge.iterrows():
        repartition[row["operator_id"]] = {
            "nb_moves": int(row["nb_moves"]),
            "pct": round(row["nb_moves"] / total_moves * 100, 1) if total_moves > 0 else 0,
            "total_qty": float(row["total_qty"]),
        }

    conn.close()

    return {
        "label": _period_label(period_type, year, value),
        "taux_service_pct": taux_service,
        "same_day_count": int(same_day),
        "total_expedie": len(df_svc),
        "top_references": top_refs,
        "flop_references": flop_refs,
        "repartition_charge": repartition,
    }


# ════════════════════════════════════════════════════════════
#  RÉSUMÉ COMPLET (pour le PDF et le texte Telegram)
# ════════════════════════════════════════════════════════════

def compute_all_kpis(period_type: str, year: int, value: int) -> dict:
    """Calcule tous les KPIs pour une période donnée."""
    return {
        "period_type": period_type,
        "year": year,
        "value": value,
        "label": _period_label(period_type, year, value),
        "commandes": kpi_commandes(period_type, year, value),
        "delais": kpi_delais(period_type, year, value),
        "qualite": kpi_qualite(period_type, year, value),
        "cadence": kpi_cadence(period_type, year, value),
        "charge": kpi_charge(period_type, year, value),
        "bonus": kpi_bonus(period_type, year, value),
    }
