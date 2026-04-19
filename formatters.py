"""
Formatage des KPIs en texte pour les messages Telegram.
Utilise le formatage HTML de Telegram.
"""


def format_summary(all_kpis: dict) -> str:
    """Résumé rapide de tous les KPIs (pour /kpi)."""
    label = all_kpis["label"]
    cmd = all_kpis["commandes"]
    dl = all_kpis["delais"]
    qu = all_kpis["qualite"]
    cd = all_kpis["cadence"]
    bn = all_kpis["bonus"]

    lines = [
        f"📊 <b>TABLEAU DE BORD — {label}</b>",
        "",
        f"📦 <b>Commandes :</b> {cmd['total_commandes']}",
    ]

    # Détail clients
    for client, count in sorted(cmd["par_client"].items(), key=lambda x: -x[1]):
        pct = count / cmd["total_commandes"] * 100 if cmd["total_commandes"] > 0 else 0
        lines.append(f"   └ {client} : {count} ({pct:.0f}%)")

    lines += [
        "",
        f"⏱ <b>Délai traitement :</b>",
        f"   Moyenne : {dl['delai_moyen_min']:.1f} min",
        f"   Médiane : {dl['delai_median_min']:.1f} min",
        f"   Max : {dl['delai_max_min']:.1f} min",
        f"   ⚠️ Anomalies : {len(dl['anomalies'])}",
        "",
        f"🔍 <b>Qualité :</b> {qu['taux_qua_pct']:.1f}% ({qu['commandes_qua']}/{qu['total_commandes']})",
        "",
        f"✅ <b>Taux de service :</b> {bn['taux_service_pct']:.1f}%",
    ]

    return "\n".join(lines)


def format_commandes(data: dict) -> str:
    """Détail KPI 1 : commandes (pour /commandes)."""
    lines = [
        f"📦 <b>COMMANDES — {data['label']}</b>",
        "",
        f"Total : <b>{data['total_commandes']}</b> commandes",
        "",
        "<b>Par client :</b>",
    ]

    for client, count in sorted(data["par_client"].items(), key=lambda x: -x[1]):
        pct = count / data["total_commandes"] * 100 if data["total_commandes"] > 0 else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        lines.append(f"  {client} : {count:>4d} {bar} {pct:.0f}%")

    lines += ["", "<b>Par référence :</b>"]
    for ref, count in sorted(data["par_reference"].items(), key=lambda x: -x[1]):
        short_ref = ref.replace('Edriseur ', '').replace('"', '')
        lines.append(f"  {short_ref:>20s} : {count}")

    return "\n".join(lines)


def format_delais(data: dict) -> str:
    """Détail KPI 2 : délais (pour /delais)."""
    lines = [
        f"⏱ <b>DÉLAIS DE TRAITEMENT — {data['label']}</b>",
        "",
        f"📊 Commandes analysées : {data['nb_commandes']}",
        "",
        f"  Moyenne  : <b>{data['delai_moyen_min']:.1f} min</b>",
        f"  Médiane  : <b>{data['delai_median_min']:.1f} min</b>",
        f"  Minimum  : {data['delai_min_min']:.1f} min",
        f"  Maximum  : {data['delai_max_min']:.1f} min",
        "",
        "<b>Par client :</b>",
    ]

    for client, delai in sorted(data["par_client"].items()):
        lines.append(f"  {client} : {delai:.1f} min")

    if data["anomalies"]:
        lines += [
            "",
            f"⚠️ <b>{len(data['anomalies'])} anomalies</b> (> 2× médiane) :",
        ]
        for order_id, delai in sorted(data["anomalies"], key=lambda x: -x[1])[:10]:
            lines.append(f"  {order_id} : {delai:.1f} min")
        if len(data["anomalies"]) > 10:
            lines.append(f"  ... et {len(data['anomalies']) - 10} autres")

    return "\n".join(lines)


def format_qualite(data: dict) -> str:
    """Détail KPI 3 : qualité (pour /qualite)."""
    lines = [
        f"🔍 <b>TRANSFERT QUALITÉ — {data['label']}</b>",
        "",
        f"Taux global : <b>{data['taux_qua_pct']:.1f}%</b>",
        f"({data['commandes_qua']} commandes sur {data['total_commandes']})",
        "",
        "<b>Par client :</b>",
    ]

    for client, info in sorted(data["par_client"].items()):
        lines.append(f"  {client} : {info['taux']:.1f}% ({info['qua']}/{info['total']})")

    return "\n".join(lines)


def format_cadence(data: dict) -> str:
    """Détail KPI 4 : cadence (pour /cadence)."""
    lines = [
        f"🏃 <b>CADENCE HORAIRE — {data['label']}</b>",
        "",
    ]

    if not data["operateurs"]:
        lines.append("Aucune donnée disponible.")
        return "\n".join(lines)

    # Header
    lines.append("<pre>")
    lines.append(f"{'Opér.':>8s} {'Moves':>6s} {'Heures':>7s} {'Jours':>6s} {'Cad.':>6s}")
    lines.append("-" * 40)

    for op_id in sorted(data["operateurs"].keys()):
        o = data["operateurs"][op_id]
        lines.append(
            f"{op_id:>8s} {o['total_moves']:>6d} {o['total_hours']:>7.1f} "
            f"{o['days_worked']:>6d} {o['cadence_moy']:>5.1f}/h"
        )

    lines.append("</pre>")
    return "\n".join(lines)


def format_charge(data: dict) -> str:
    """Résumé KPI 5 : charge (pour /charge)."""
    par_jour = data["par_jour"]
    if not par_jour:
        return f"📈 <b>CHARGE — {data['label']}</b>\n\nAucune donnée."

    dates = sorted(par_jour.keys())
    total_qty = sum(par_jour[d]["qty"] for d in dates)
    total_cmd = sum(par_jour[d]["nb_commandes"] for d in dates)
    avg_qty = total_qty / len(dates) if dates else 0
    max_day = max(dates, key=lambda d: par_jour[d]["qty"])
    min_day = min(dates, key=lambda d: par_jour[d]["qty"])

    lines = [
        f"📈 <b>LISSAGE DE CHARGE — {data['label']}</b>",
        "",
        f"📅 Période : {dates[0]} → {dates[-1]} ({len(dates)} jours)",
        f"📦 Total quantités : {total_qty:,.0f}",
        f"📋 Total commandes : {total_cmd}",
        "",
        f"Moyenne/jour : {avg_qty:,.0f} unités",
        f"Jour max : {max_day[8:]} ({par_jour[max_day]['qty']:,.0f})",
        f"Jour min : {min_day[8:]} ({par_jour[min_day]['qty']:,.0f})",
    ]

    return "\n".join(lines)
