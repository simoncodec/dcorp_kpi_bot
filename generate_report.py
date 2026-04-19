#!/usr/bin/env python3
"""
Script CLI pour générer un rapport sans passer par Telegram.
Utile pour les tests et la génération manuelle.

Usage:
    python generate_report.py --import data/mon_fichier.csv
    python generate_report.py --week 49
    python generate_report.py --month 12
    python generate_report.py --all
"""
import argparse
import sys
import os
import logging

# Ajouter le dossier courant au path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data_manager import import_csv, import_all_csv_in_data_dir, get_available_weeks, get_available_months, get_row_count
from kpi_engine import compute_all_kpis
from charts import generate_all_charts
from pdf_report import generate_pdf_report
from formatters import format_summary
from config import OUTPUT_DIR

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def do_import(filepath: str):
    """Importe un fichier CSV."""
    if not os.path.exists(filepath):
        print(f"❌ Fichier introuvable : {filepath}")
        return

    count = import_csv(filepath, replace=True)
    print(f"✅ {count} lignes importées depuis {filepath}")


def do_import_all():
    """Importe tous les CSV du dossier data/."""
    count = import_all_csv_in_data_dir(replace=True)
    print(f"✅ {count} lignes importées au total")


def do_report(period_type: str, year: int, value: int):
    """Génère un rapport complet."""
    print(f"\n{'='*60}")
    print(f"  Génération du rapport : {period_type} {year}-{value}")
    print(f"{'='*60}\n")

    # 1. KPIs
    print("📊 Calcul des KPIs...")
    all_kpis = compute_all_kpis(period_type, year, value)

    # 2. Résumé texte
    print("\n" + format_summary(all_kpis).replace("<b>", "").replace("</b>", "").replace("<i>", "").replace("</i>", ""))

    # 3. Graphiques
    print("\n📈 Génération des graphiques...")
    chart_paths = generate_all_charts(all_kpis)
    for p in chart_paths:
        print(f"   ✓ {os.path.basename(p)}")

    # 4. PDF
    print("\n📄 Génération du PDF...")
    pdf_path = generate_pdf_report(all_kpis, chart_paths)
    print(f"   ✓ {pdf_path}")

    print(f"\n✅ Rapport terminé ! Fichiers dans : {OUTPUT_DIR}/")


def main():
    parser = argparse.ArgumentParser(
        description="D-corp KPI Bot — Génération de rapports en ligne de commande",
    )

    parser.add_argument(
        "--import-file", "-i",
        help="Importer un fichier CSV",
        metavar="FICHIER",
    )
    parser.add_argument(
        "--import-all",
        action="store_true",
        help="Importer tous les CSV du dossier data/",
    )
    parser.add_argument(
        "--week", "-w",
        type=int,
        help="Générer le rapport pour la semaine N (ex: 49)",
        metavar="N",
    )
    parser.add_argument(
        "--month", "-m",
        type=int,
        help="Générer le rapport pour le mois N (ex: 12)",
        metavar="N",
    )
    parser.add_argument(
        "--year", "-y",
        type=int,
        default=2025,
        help="Année (défaut: 2025)",
    )
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Générer les rapports pour toutes les périodes disponibles",
    )

    args = parser.parse_args()

    # Import
    if args.import_file:
        do_import(args.import_file)

    if args.import_all:
        do_import_all()

    # Vérifier qu'il y a des données
    if get_row_count() == 0 and not args.import_file and not args.import_all:
        print("⚠️  Base de données vide. Importez d'abord des données :")
        print("    python generate_report.py --import-file data/mon_fichier.csv")
        print("    python generate_report.py --import-all")
        return

    # Génération
    if args.week:
        do_report("week", args.year, args.week)

    elif args.month:
        do_report("month", args.year, args.month)

    elif args.all:
        for y, w in get_available_weeks():
            do_report("week", y, w)
        for y, m in get_available_months():
            do_report("month", y, m)

    elif not args.import_file and not args.import_all:
        # Par défaut, dernière semaine
        weeks = get_available_weeks()
        if weeks:
            y, w = weeks[-1]
            do_report("week", y, w)
        else:
            print("Aucune donnée. Utilisez --import-file ou --import-all.")


if __name__ == "__main__":
    main()
