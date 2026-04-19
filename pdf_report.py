"""
Génération du rapport PDF au format A3 pour impression.
Contient le dashboard + tous les graphiques KPI + résumé texte.
"""
import os
import logging
from datetime import datetime

from reportlab.lib.pagesizes import A3, landscape
from reportlab.lib.units import mm, cm
from reportlab.lib.colors import HexColor
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image as RLImage,
    Table, TableStyle, PageBreak, KeepTogether,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT

from config import COLORS, OUTPUT_DIR

logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════════════
#  STYLES
# ════════════════════════════════════════════════════════════

def _get_styles():
    """Styles personnalisés pour le rapport D-corp."""
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        "DCTitle",
        parent=styles["Title"],
        fontSize=22,
        textColor=HexColor(COLORS["primary"]),
        spaceAfter=8 * mm,
        alignment=TA_CENTER,
        fontName="Helvetica-Bold",
    ))

    styles.add(ParagraphStyle(
        "DCSubtitle",
        parent=styles["Normal"],
        fontSize=13,
        textColor=HexColor(COLORS["secondary"]),
        spaceAfter=6 * mm,
        alignment=TA_CENTER,
        fontName="Helvetica",
    ))

    styles.add(ParagraphStyle(
        "DCHeading",
        parent=styles["Heading2"],
        fontSize=14,
        textColor=HexColor(COLORS["primary"]),
        spaceBefore=8 * mm,
        spaceAfter=4 * mm,
        fontName="Helvetica-Bold",
    ))

    styles.add(ParagraphStyle(
        "DCBody",
        parent=styles["Normal"],
        fontSize=10,
        textColor=HexColor(COLORS["text"]),
        spaceAfter=3 * mm,
        fontName="Helvetica",
        leading=14,
    ))

    styles.add(ParagraphStyle(
        "DCSmall",
        parent=styles["Normal"],
        fontSize=8,
        textColor=HexColor(COLORS["neutral"]),
        alignment=TA_RIGHT,
    ))

    styles.add(ParagraphStyle(
        "DCKPIValue",
        parent=styles["Normal"],
        fontSize=18,
        textColor=HexColor(COLORS["primary"]),
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
    ))

    return styles


# ════════════════════════════════════════════════════════════
#  TABLE HELPER
# ════════════════════════════════════════════════════════════

def _make_table(headers: list, rows: list, col_widths=None) -> Table:
    """Crée une table stylée pour le rapport."""
    data = [headers] + rows

    table = Table(data, colWidths=col_widths)
    table.setStyle(TableStyle([
        # En-tête
        ("BACKGROUND", (0, 0), (-1, 0), HexColor(COLORS["primary"])),
        ("TEXTCOLOR", (0, 0), (-1, 0), HexColor("#FFFFFF")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        # Corps
        ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 1), (-1, -1), 9),
        ("ALIGN", (1, 1), (-1, -1), "CENTER"),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        # Bordures
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CCCCCC")),
        # Alternance couleur
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [HexColor("#FFFFFF"), HexColor("#F8F9FA")]),
    ]))

    return table


# ════════════════════════════════════════════════════════════
#  GÉNÉRATION DU RAPPORT
# ════════════════════════════════════════════════════════════

def generate_pdf_report(all_kpis: dict, chart_paths: list[str]) -> str:
    """
    Génère le rapport PDF complet au format A3.

    Args:
        all_kpis: dictionnaire complet des KPIs
        chart_paths: liste des chemins vers les graphiques PNG

    Returns:
        chemin du fichier PDF généré
    """
    styles = _get_styles()
    label = all_kpis["label"]
    period_type = all_kpis["period_type"]
    year = all_kpis["year"]
    value = all_kpis["value"]

    # Nom du fichier
    if period_type == "week":
        filename = f"{year}_S{value:02d}_Rapport_Hebdomadaire.pdf"
    else:
        filename = f"{year}_M{value:02d}_Rapport_Mensuel.pdf"

    filepath = os.path.join(OUTPUT_DIR, filename)

    # Document A3 paysage
    doc = SimpleDocTemplate(
        filepath,
        pagesize=landscape(A3),
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
    )

    story = []

    # ══════════════════════════════════════════════════
    #  PAGE 1 : DASHBOARD + RÉSUMÉ
    # ══════════════════════════════════════════════════

    # Titre
    if period_type == "week":
        title_text = f"RAPPORT HEBDOMADAIRE — Point 15'"
    else:
        title_text = f"RAPPORT MENSUEL — Point 45'"

    story.append(Paragraph(title_text, styles["DCTitle"]))
    story.append(Paragraph(
        f"D-corp Logistique — {label} — Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}",
        styles["DCSubtitle"],
    ))

    # Dashboard image (premier graphique)
    dashboard_path = None
    for p in chart_paths:
        if "dashboard" in p:
            dashboard_path = p
            break

    if dashboard_path and os.path.exists(dashboard_path):
        img = RLImage(dashboard_path, width=380 * mm, height=180 * mm)
        story.append(img)

    story.append(PageBreak())

    # ══════════════════════════════════════════════════
    #  PAGE 2 : KPI 1 - COMMANDES
    # ══════════════════════════════════════════════════

    story.append(Paragraph("1. Commandes traitées", styles["DCHeading"]))

    cmd = all_kpis["commandes"]
    story.append(Paragraph(
        f"Total de <b>{cmd['total_commandes']}</b> commandes sur la période.",
        styles["DCBody"],
    ))

    # Tableau par client
    if cmd["par_client"]:
        rows = [[c, str(v)] for c, v in sorted(cmd["par_client"].items(), key=lambda x: -x[1])]
        rows.append(["<b>TOTAL</b>", f"<b>{cmd['total_commandes']}</b>"])
        table_data = [["Client", "Nb commandes"]]
        for r in rows:
            table_data.append([Paragraph(r[0], styles["DCBody"]), Paragraph(r[1], styles["DCBody"])])

        t = _make_table(["Client", "Nb commandes"], [[r[0], r[1]] for r in rows[:-1]])
        story.append(t)
        story.append(Spacer(1, 5 * mm))

    # Graphiques commandes
    for p in chart_paths:
        if "kpi1_" in p and os.path.exists(p):
            img = RLImage(p, width=310 * mm, height=130 * mm)
            story.append(img)
            story.append(Spacer(1, 5 * mm))

    story.append(PageBreak())

    # ══════════════════════════════════════════════════
    #  PAGE 3 : KPI 2 - DÉLAIS
    # ══════════════════════════════════════════════════

    story.append(Paragraph("2. Délai de traitement interne", styles["DCHeading"]))

    dl = all_kpis["delais"]
    story.append(Paragraph(
        f"Délai moyen : <b>{dl['delai_moyen_min']:.1f} min</b> | "
        f"Médiane : <b>{dl['delai_median_min']:.1f} min</b> | "
        f"Min : <b>{dl['delai_min_min']:.1f} min</b> | "
        f"Max : <b>{dl['delai_max_min']:.1f} min</b>",
        styles["DCBody"],
    ))

    if dl["anomalies"]:
        story.append(Paragraph(
            f"<font color='{COLORS['danger']}'><b>{len(dl['anomalies'])} anomalies</b></font> "
            f"détectées (délai > {dl['delai_median_min'] * 2:.0f} min).",
            styles["DCBody"],
        ))

    for p in chart_paths:
        if "kpi2_" in p and os.path.exists(p):
            img = RLImage(p, width=300 * mm, height=130 * mm)
            story.append(img)
            story.append(Spacer(1, 5 * mm))

    story.append(PageBreak())

    # ══════════════════════════════════════════════════
    #  PAGE 4 : KPI 3 + KPI 4
    # ══════════════════════════════════════════════════

    # Qualité
    story.append(Paragraph("3. Taux de transfert qualité", styles["DCHeading"]))

    qu = all_kpis["qualite"]
    story.append(Paragraph(
        f"Taux global : <b>{qu['taux_qua_pct']:.1f}%</b> "
        f"({qu['commandes_qua']}/{qu['total_commandes']} commandes).",
        styles["DCBody"],
    ))

    for p in chart_paths:
        if "kpi3_" in p and os.path.exists(p):
            img = RLImage(p, width=310 * mm, height=120 * mm)
            story.append(img)
            story.append(Spacer(1, 3 * mm))

    # Cadence
    story.append(Paragraph("4. Cadence horaire par opérateur", styles["DCHeading"]))

    cd = all_kpis["cadence"]
    if cd["operateurs"]:
        rows_cadence = []
        for op_id in sorted(cd["operateurs"].keys()):
            o = cd["operateurs"][op_id]
            rows_cadence.append([
                op_id,
                str(o["total_moves"]),
                f"{o['total_hours']:.1f}",
                str(o["days_worked"]),
                f"{o['cadence_moy']:.1f}",
                f"{o['qty_totale']:,.0f}",
            ])

        t = _make_table(
            ["Opérateur", "Moves", "Heures", "Jours", "Cadence (m/h)", "Qté totale"],
            rows_cadence,
            col_widths=[50 * mm, 35 * mm, 35 * mm, 30 * mm, 45 * mm, 45 * mm],
        )
        story.append(t)

    for p in chart_paths:
        if "kpi4_" in p and os.path.exists(p):
            img = RLImage(p, width=310 * mm, height=130 * mm)
            story.append(img)

    story.append(PageBreak())

    # ══════════════════════════════════════════════════
    #  PAGE 5 : KPI 5 + KPI 6
    # ══════════════════════════════════════════════════

    story.append(Paragraph("5. Lissage de la charge", styles["DCHeading"]))

    for p in chart_paths:
        if "kpi5_" in p and os.path.exists(p):
            img = RLImage(p, width=350 * mm, height=140 * mm)
            story.append(img)
            story.append(Spacer(1, 5 * mm))

    story.append(Paragraph("6. Indicateurs complémentaires", styles["DCHeading"]))

    bn = all_kpis["bonus"]
    story.append(Paragraph(
        f"Taux de service (expédié le jour même) : <b>{bn['taux_service_pct']:.1f}%</b> "
        f"({bn['same_day_count']}/{bn['total_expedie']})",
        styles["DCBody"],
    ))

    for p in chart_paths:
        if "kpi6_" in p and os.path.exists(p):
            img = RLImage(p, width=250 * mm, height=110 * mm)
            story.append(img)
            story.append(Spacer(1, 3 * mm))

    # Footer
    story.append(Spacer(1, 10 * mm))
    story.append(Paragraph(
        f"Rapport généré automatiquement par D-corp KPI Bot — {datetime.now().strftime('%d/%m/%Y %H:%M')}",
        styles["DCSmall"],
    ))

    # Build
    doc.build(story)
    logger.info("Rapport PDF généré : %s", filepath)
    return filepath
