"""
Génération des graphiques pour les rapports D-corp.
Style management visuel : lisible, couleurs contrastées, accessible.
"""
import os
import matplotlib
matplotlib.use("Agg")  # Backend sans GUI

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.patches import FancyBboxPatch
import numpy as np
import logging

from config import COLORS, CLIENT_COLORS, OPERATOR_COLORS, OUTPUT_DIR

logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════
#  STYLE GLOBAL
# ════════════════════════════════════════════════════════════

plt.rcParams.update({
    "figure.facecolor": COLORS["background"],
    "axes.facecolor": "#FFFFFF",
    "axes.edgecolor": "#CCCCCC",
    "axes.labelcolor": COLORS["text"],
    "axes.titleweight": "bold",
    "axes.titlesize": 14,
    "axes.labelsize": 11,
    "xtick.color": COLORS["text"],
    "ytick.color": COLORS["text"],
    "xtick.labelsize": 9,
    "ytick.labelsize": 9,
    "legend.fontsize": 9,
    "legend.framealpha": 0.9,
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans"],
    "grid.alpha": 0.3,
    "grid.linestyle": "--",
})


def _save_fig(fig, name: str) -> str:
    """Sauvegarde et retourne le chemin du fichier."""
    path = os.path.join(OUTPUT_DIR, f"{name}.png")
    fig.savefig(path, dpi=150, bbox_inches="tight", pad_inches=0.3)
    plt.close(fig)
    logger.info("Graphique sauvegardé : %s", path)
    return path


def _add_value_labels(ax, bars, fmt="{:.0f}", fontsize=8, offset=0.5):
    """Ajoute les valeurs au-dessus des barres."""
    for bar in bars:
        height = bar.get_height()
        if height > 0:
            ax.text(
                bar.get_x() + bar.get_width() / 2.0,
                height + offset,
                fmt.format(height),
                ha="center", va="bottom",
                fontsize=fontsize, fontweight="bold",
                color=COLORS["text"],
            )


# ════════════════════════════════════════════════════════════
#  GRAPHIQUE 1 : COMMANDES PAR CLIENT
# ════════════════════════════════════════════════════════════

def chart_commandes_client(data: dict) -> str:
    """Barres horizontales : répartition des commandes par client."""
    par_client = data["par_client"]
    if not par_client:
        return ""

    clients = list(par_client.keys())
    values = list(par_client.values())
    colors = [CLIENT_COLORS.get(c, COLORS["neutral"]) for c in clients]

    fig, ax = plt.subplots(figsize=(8, 3.5))

    bars = ax.barh(clients, values, color=colors, edgecolor="white", height=0.6)

    # Valeurs sur les barres
    for bar, val in zip(bars, values):
        ax.text(
            bar.get_width() + max(values) * 0.02,
            bar.get_y() + bar.get_height() / 2,
            f"{val}",
            ha="left", va="center",
            fontsize=11, fontweight="bold", color=COLORS["text"],
        )

    ax.set_xlabel("Nombre de commandes")
    ax.set_title(
        f"Répartition des commandes par client\n{data['label']}",
        fontsize=13, fontweight="bold", color=COLORS["primary"],
    )
    ax.set_xlim(0, max(values) * 1.2)
    ax.grid(axis="x", alpha=0.3)
    ax.invert_yaxis()

    # Total en annotation
    total = data["total_commandes"]
    ax.annotate(
        f"Total : {total} commandes",
        xy=(0.98, 0.02), xycoords="axes fraction",
        ha="right", va="bottom",
        fontsize=11, fontweight="bold",
        color=COLORS["primary"],
        bbox=dict(boxstyle="round,pad=0.3", facecolor=COLORS["background"], edgecolor=COLORS["primary"]),
    )

    fig.tight_layout()
    return _save_fig(fig, "kpi1_commandes_client")


def chart_commandes_reference(data: dict) -> str:
    """Barres : répartition des commandes par référence produit."""
    par_ref = data["par_reference"]
    if not par_ref:
        return ""

    # Trier par volume décroissant
    refs = sorted(par_ref.keys(), key=lambda r: par_ref[r], reverse=True)
    values = [par_ref[r] for r in refs]
    # Raccourcir les noms
    short_refs = [r.replace('Edriseur ', '').replace('"', '') for r in refs]

    fig, ax = plt.subplots(figsize=(10, 4.5))

    colors_gradient = plt.cm.Blues(np.linspace(0.4, 0.85, len(refs)))
    bars = ax.bar(range(len(refs)), values, color=colors_gradient, edgecolor="white", width=0.7)

    _add_value_labels(ax, bars, offset=max(values) * 0.02)

    ax.set_xticks(range(len(refs)))
    ax.set_xticklabels(short_refs, rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Nombre de commandes")
    ax.set_title(
        f"Répartition par référence produit\n{data['label']}",
        fontsize=13, fontweight="bold", color=COLORS["primary"],
    )
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    return _save_fig(fig, "kpi1_commandes_reference")


# ════════════════════════════════════════════════════════════
#  GRAPHIQUE 2 : DÉLAIS DE TRAITEMENT
# ════════════════════════════════════════════════════════════

def chart_delais_histo(data: dict) -> str:
    """Histogramme des délais de traitement interne."""
    distribution = data["distribution"]
    if not distribution:
        return ""

    delais = [d[1] for d in distribution]

    fig, ax = plt.subplots(figsize=(9, 4.5))

    # Histogramme
    n, bins, patches = ax.hist(
        delais, bins=25, color=COLORS["secondary"], edgecolor="white",
        alpha=0.85, zorder=3,
    )

    # Lignes de référence
    mean_val = data["delai_moyen_min"]
    median_val = data["delai_median_min"]

    ax.axvline(mean_val, color=COLORS["accent"], linewidth=2, linestyle="-",
               label=f"Moyenne : {mean_val:.1f} min", zorder=4)
    ax.axvline(median_val, color=COLORS["success"], linewidth=2, linestyle="--",
               label=f"Médiane : {median_val:.1f} min", zorder=4)

    # Zone d'anomalie
    threshold = median_val * 2
    ax.axvspan(threshold, max(delais) + 5, alpha=0.1, color=COLORS["danger"],
               label=f"Zone anomalie (>{threshold:.0f} min)", zorder=1)

    ax.set_xlabel("Délai de traitement (minutes)")
    ax.set_ylabel("Nombre de commandes")
    ax.set_title(
        f"Distribution des délais de traitement interne\n{data['label']}",
        fontsize=13, fontweight="bold", color=COLORS["primary"],
    )
    ax.legend(loc="upper right", framealpha=0.9)
    ax.grid(axis="y", alpha=0.3, zorder=0)

    # KPI box
    info_text = (
        f"Min : {data['delai_min_min']:.1f} min\n"
        f"Max : {data['delai_max_min']:.1f} min\n"
        f"Anomalies : {len(data['anomalies'])}"
    )
    ax.text(
        0.98, 0.72, info_text,
        transform=ax.transAxes, ha="right", va="top",
        fontsize=9,
        bbox=dict(boxstyle="round,pad=0.4", facecolor="#FFF3E0", edgecolor=COLORS["accent"]),
    )

    fig.tight_layout()
    return _save_fig(fig, "kpi2_delais_histo")


def chart_delais_client(data: dict) -> str:
    """Barres : délai moyen par client."""
    par_client = data["par_client"]
    if not par_client:
        return ""

    clients = list(par_client.keys())
    values = list(par_client.values())
    colors = [CLIENT_COLORS.get(c, COLORS["neutral"]) for c in clients]

    fig, ax = plt.subplots(figsize=(7, 3.5))

    bars = ax.bar(clients, values, color=colors, edgecolor="white", width=0.5)
    _add_value_labels(ax, bars, fmt="{:.1f}", offset=max(values) * 0.02)

    ax.set_ylabel("Délai moyen (minutes)")
    ax.set_title(
        f"Délai moyen de traitement par client\n{data['label']}",
        fontsize=13, fontweight="bold", color=COLORS["primary"],
    )
    ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    return _save_fig(fig, "kpi2_delais_client")


# ════════════════════════════════════════════════════════════
#  GRAPHIQUE 3 : TAUX DE QUALITÉ
# ════════════════════════════════════════════════════════════

def chart_qualite(data: dict) -> str:
    """Jauge + barres par client pour le taux de transfert qualité."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4), gridspec_kw={"width_ratios": [1, 1.5]})

    # ── Jauge (pie chart simplifié) ──
    taux = data["taux_qua_pct"]
    sizes = [taux, 100 - taux]
    colors_pie = [COLORS["warning"], "#EEEEEE"]

    wedges, _ = ax1.pie(
        sizes, colors=colors_pie, startangle=90,
        wedgeprops=dict(width=0.35, edgecolor="white"),
    )

    ax1.text(0, 0, f"{taux:.1f}%", ha="center", va="center",
             fontsize=24, fontweight="bold", color=COLORS["text"])
    ax1.text(0, -0.15, "Transfert qualité", ha="center", va="center",
             fontsize=10, color=COLORS["neutral"])

    ax1.set_title(
        f"Taux global\n({data['commandes_qua']}/{data['total_commandes']} commandes)",
        fontsize=11, fontweight="bold", color=COLORS["primary"],
    )

    # ── Barres par client ──
    par_client = data["par_client"]
    if par_client:
        clients = list(par_client.keys())
        taux_vals = [par_client[c]["taux"] for c in clients]
        colors_bar = [CLIENT_COLORS.get(c, COLORS["neutral"]) for c in clients]

        bars = ax2.bar(clients, taux_vals, color=colors_bar, edgecolor="white", width=0.5)
        _add_value_labels(ax2, bars, fmt="{:.1f}%", offset=0.5)

        ax2.set_ylabel("Taux de transfert qualité (%)")
        ax2.set_title(
            f"Taux par client\n{data['label']}",
            fontsize=11, fontweight="bold", color=COLORS["primary"],
        )
        ax2.set_ylim(0, max(taux_vals) * 1.3 if taux_vals else 50)
        ax2.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    return _save_fig(fig, "kpi3_qualite")


# ════════════════════════════════════════════════════════════
#  GRAPHIQUE 4 : CADENCE PAR OPÉRATEUR
# ════════════════════════════════════════════════════════════

def chart_cadence(data: dict) -> str:
    """Barres groupées : cadence et volume par opérateur."""
    operateurs = data["operateurs"]
    if not operateurs:
        return ""

    ops = sorted(operateurs.keys())
    cadences = [operateurs[o]["cadence_moy"] for o in ops]
    moves = [operateurs[o]["total_moves"] for o in ops]
    jours = [operateurs[o]["days_worked"] for o in ops]

    fig, ax1 = plt.subplots(figsize=(10, 5))

    x = np.arange(len(ops))
    width = 0.35

    bars1 = ax1.bar(x - width / 2, cadences, width, label="Cadence (moves/h)",
                    color=COLORS["primary"], edgecolor="white")
    _add_value_labels(ax1, bars1, fmt="{:.1f}", offset=0.1)

    ax2 = ax1.twinx()
    bars2 = ax2.bar(x + width / 2, moves, width, label="Total moves",
                    color=COLORS["accent"], edgecolor="white", alpha=0.7)
    _add_value_labels(ax2, bars2, fmt="{:.0f}", offset=5)

    ax1.set_xlabel("Opérateur")
    ax1.set_ylabel("Cadence (moves/heure)", color=COLORS["primary"])
    ax2.set_ylabel("Total moves sur la période", color=COLORS["accent"])

    ax1.set_xticks(x)
    labels = [f"{o}\n({jours[i]}j)" for i, o in enumerate(ops)]
    ax1.set_xticklabels(labels, fontsize=9)

    ax1.set_title(
        f"Cadence horaire par opérateur\n{data['label']}",
        fontsize=13, fontweight="bold", color=COLORS["primary"],
    )

    # Légende combinée
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper right")

    ax1.grid(axis="y", alpha=0.2)
    fig.tight_layout()
    return _save_fig(fig, "kpi4_cadence")


# ════════════════════════════════════════════════════════════
#  GRAPHIQUE 5 : LISSAGE DE LA CHARGE
# ════════════════════════════════════════════════════════════

def chart_charge(data: dict) -> str:
    """Courbe cumulée + barres journalières pour le lissage de charge."""
    par_jour = data["par_jour"]
    cumul_qty = data["cumul_qty"]
    if not par_jour:
        return ""

    dates = sorted(par_jour.keys())
    qty_jour = [par_jour[d]["qty"] for d in dates]
    qty_cumul = [cumul_qty[d] for d in dates]
    nb_cmd = [par_jour[d]["nb_commandes"] for d in dates]

    # Labels courts (jour du mois)
    date_labels = [d[8:10] for d in dates]  # DD

    fig, ax1 = plt.subplots(figsize=(12, 5))

    # Barres : quantités journalières
    ax1.bar(range(len(dates)), qty_jour, color=COLORS["secondary"],
            edgecolor="white", alpha=0.7, label="Qté/jour", zorder=2)

    ax1.set_xlabel("Jour du mois")
    ax1.set_ylabel("Quantités déplacées / jour", color=COLORS["secondary"])

    # Courbe cumul sur axe secondaire
    ax2 = ax1.twinx()
    ax2.plot(range(len(dates)), qty_cumul, color=COLORS["danger"],
             linewidth=2.5, marker="o", markersize=3,
             label="Cumul quantités", zorder=3)
    ax2.set_ylabel("Cumul quantités", color=COLORS["danger"])
    ax2.fill_between(range(len(dates)), qty_cumul, alpha=0.05, color=COLORS["danger"])

    ax1.set_xticks(range(len(dates)))
    ax1.set_xticklabels(date_labels, fontsize=7)

    ax1.set_title(
        f"Lissage de la charge — Quantités cumulées\n{data['label']}",
        fontsize=13, fontweight="bold", color=COLORS["primary"],
    )

    # Légende combinée
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    ax1.grid(axis="y", alpha=0.2, zorder=0)
    fig.tight_layout()
    return _save_fig(fig, "kpi5_charge")


# ════════════════════════════════════════════════════════════
#  GRAPHIQUE 6 : INDICATEURS BONUS
# ════════════════════════════════════════════════════════════

def chart_repartition_charge(data: dict) -> str:
    """Pie chart : répartition de la charge entre opérateurs."""
    repartition = data["repartition_charge"]
    if not repartition:
        return ""

    ops = sorted(repartition.keys())
    values = [repartition[o]["nb_moves"] for o in ops]
    colors = OPERATOR_COLORS[:len(ops)]

    fig, ax = plt.subplots(figsize=(7, 5))

    wedges, texts, autotexts = ax.pie(
        values, labels=ops, colors=colors, autopct="%1.1f%%",
        startangle=140, wedgeprops=dict(edgecolor="white", linewidth=2),
        textprops={"fontsize": 10},
    )
    for t in autotexts:
        t.set_fontweight("bold")
        t.set_fontsize(9)

    ax.set_title(
        f"Répartition de la charge par opérateur\n{data['label']}",
        fontsize=13, fontweight="bold", color=COLORS["primary"],
    )

    fig.tight_layout()
    return _save_fig(fig, "kpi6_repartition")


def chart_top_refs(data: dict) -> str:
    """Barres horizontales : top 5 références par volume."""
    top = data["top_references"]
    if not top:
        return ""

    refs = [r["reference_name"].replace('Edriseur ', '').replace('"', '') for r in top]
    qtys = [r["total_qty"] for r in top]

    fig, ax = plt.subplots(figsize=(8, 3.5))

    colors_gradient = plt.cm.Oranges(np.linspace(0.4, 0.85, len(refs)))
    bars = ax.barh(refs[::-1], qtys[::-1], color=colors_gradient[::-1],
                   edgecolor="white", height=0.5)

    for bar, val in zip(bars, qtys[::-1]):
        ax.text(
            bar.get_width() + max(qtys) * 0.02,
            bar.get_y() + bar.get_height() / 2,
            f"{val:,.0f}",
            ha="left", va="center", fontsize=10, fontweight="bold",
        )

    ax.set_xlabel("Quantité totale")
    ax.set_title(
        f"Top 5 références par volume\n{data['label']}",
        fontsize=13, fontweight="bold", color=COLORS["primary"],
    )
    ax.set_xlim(0, max(qtys) * 1.2)
    ax.grid(axis="x", alpha=0.3)

    fig.tight_layout()
    return _save_fig(fig, "kpi6_top_refs")


# ════════════════════════════════════════════════════════════
#  DASHBOARD SYNTHÉTIQUE (page résumé)
# ════════════════════════════════════════════════════════════

def chart_dashboard(all_kpis: dict) -> str:
    """
    Génère une page dashboard avec les KPIs clés en grands chiffres.
    Style management visuel pour un coup d'œil rapide.
    """
    fig, axes = plt.subplots(2, 3, figsize=(14, 7))
    fig.patch.set_facecolor(COLORS["background"])

    label = all_kpis["label"]
    fig.suptitle(
        f"TABLEAU DE BORD LOGISTIQUE — {label}",
        fontsize=16, fontweight="bold", color=COLORS["primary"],
        y=0.98,
    )

    # Helper pour les cartes KPI
    def kpi_card(ax, value, unit, title, color, subtitle=""):
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis("off")

        # Fond arrondi
        bg = FancyBboxPatch(
            (0.05, 0.05), 0.9, 0.9,
            boxstyle="round,pad=0.05",
            facecolor="white", edgecolor=color, linewidth=2,
        )
        ax.add_patch(bg)

        # Valeur principale
        ax.text(0.5, 0.55, f"{value}", ha="center", va="center",
                fontsize=28, fontweight="bold", color=color)
        # Unité
        ax.text(0.5, 0.35, unit, ha="center", va="center",
                fontsize=11, color=COLORS["neutral"])
        # Titre
        ax.text(0.5, 0.82, title, ha="center", va="center",
                fontsize=11, fontweight="bold", color=COLORS["text"])
        # Sous-titre
        if subtitle:
            ax.text(0.5, 0.18, subtitle, ha="center", va="center",
                    fontsize=8, color=COLORS["neutral"])

    # ── Carte 1 : Total commandes ──
    cmd = all_kpis["commandes"]
    kpi_card(axes[0, 0], cmd["total_commandes"], "commandes",
             "Commandes traitées", COLORS["primary"])

    # ── Carte 2 : Délai moyen ──
    dl = all_kpis["delais"]
    kpi_card(axes[0, 1], f"{dl['delai_moyen_min']:.1f}", "minutes (moy.)",
             "Délai de traitement", COLORS["secondary"],
             f"Médiane : {dl['delai_median_min']:.1f} min")

    # ── Carte 3 : Taux qualité ──
    qu = all_kpis["qualite"]
    kpi_card(axes[0, 2], f"{qu['taux_qua_pct']:.1f}%", "transfert qualité",
             "Taux qualité", COLORS["warning"],
             f"{qu['commandes_qua']}/{qu['total_commandes']} commandes")

    # ── Carte 4 : Meilleur opérateur ──
    cd = all_kpis["cadence"]
    if cd["operateurs"]:
        best_op = max(cd["operateurs"].items(), key=lambda x: x[1]["cadence_moy"])
        kpi_card(axes[1, 0], f"{best_op[1]['cadence_moy']:.1f}", "moves/h (meilleur)",
                 f"Top cadence : {best_op[0]}", COLORS["success"],
                 f"{best_op[1]['total_moves']} moves en {best_op[1]['days_worked']}j")

    # ── Carte 5 : Taux de service ──
    bn = all_kpis["bonus"]
    kpi_card(axes[1, 1], f"{bn['taux_service_pct']:.1f}%", "expédié le jour même",
             "Taux de service", COLORS["success"],
             f"{bn['same_day_count']}/{bn['total_expedie']} commandes")

    # ── Carte 6 : Anomalies délai ──
    nb_anomalies = len(dl["anomalies"])
    color_anom = COLORS["danger"] if nb_anomalies > 10 else COLORS["warning"] if nb_anomalies > 0 else COLORS["success"]
    kpi_card(axes[1, 2], nb_anomalies, "commandes > 2× médiane",
             "Anomalies de délai", color_anom)

    fig.tight_layout(rect=[0, 0, 1, 0.94])
    return _save_fig(fig, "kpi0_dashboard")


# ════════════════════════════════════════════════════════════
#  GÉNÉRATION COMPLÈTE
# ════════════════════════════════════════════════════════════

def generate_all_charts(all_kpis: dict) -> list[str]:
    """
    Génère tous les graphiques et retourne la liste des chemins.
    """
    charts = []

    # Dashboard synthétique
    charts.append(chart_dashboard(all_kpis))

    # KPI 1 - Commandes
    charts.append(chart_commandes_client(all_kpis["commandes"]))
    charts.append(chart_commandes_reference(all_kpis["commandes"]))

    # KPI 2 - Délais
    charts.append(chart_delais_histo(all_kpis["delais"]))
    charts.append(chart_delais_client(all_kpis["delais"]))

    # KPI 3 - Qualité
    charts.append(chart_qualite(all_kpis["qualite"]))

    # KPI 4 - Cadence
    charts.append(chart_cadence(all_kpis["cadence"]))

    # KPI 5 - Charge
    charts.append(chart_charge(all_kpis["charge"]))

    # KPI 6 - Bonus
    charts.append(chart_repartition_charge(all_kpis["bonus"]))
    charts.append(chart_top_refs(all_kpis["bonus"]))

    # Filtrer les chemins vides
    charts = [c for c in charts if c]

    logger.info("Graphiques générés : %d fichiers", len(charts))
    return charts
