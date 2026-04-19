"""
Bot Telegram D-corp KPI Logistique.
Commandes disponibles :
    /start          - Message d'accueil
    /help           - Liste des commandes
    /import         - Importer un nouveau CSV (envoyer le fichier)
    /status         - État de la base de données
    /kpi [S|M] [n]  - Résumé des KPIs (ex: /kpi S49, /kpi M12)
    /commandes      - Détail KPI 1
    /delais         - Détail KPI 2
    /qualite        - Détail KPI 3
    /cadence        - Détail KPI 4
    /charge         - Détail KPI 5 + graphique
    /rapport        - Génère et envoie le PDF complet
    /semaines       - Liste des semaines disponibles
"""
import os
import logging
import asyncio
import atexit
import tempfile
from datetime import datetime, timedelta

from telegram import Update, BotCommand
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes,
)
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import (
    TELEGRAM_TOKEN, ALLOWED_IDS, AUTO_REPORT_CHAT_ID,
    DATA_DIR, OUTPUT_DIR,
    WEEKLY_REPORT_DAY, WEEKLY_REPORT_HOUR, WEEKLY_REPORT_MINUTE,
    MONTHLY_REPORT_DAY, MONTHLY_REPORT_HOUR, MONTHLY_REPORT_MINUTE,
)
from data_manager import (
    import_csv, get_available_weeks, get_available_months,
    get_date_range, get_row_count,
)
from kpi_engine import compute_all_kpis
from charts import generate_all_charts
from pdf_report import generate_pdf_report
from formatters import (
    format_summary, format_commandes, format_delais,
    format_qualite, format_cadence, format_charge,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)
LOCK_FILE_PATH = os.path.join(tempfile.gettempdir(), "dcorp_kpi_bot.lock")
LOCK_FILE_HANDLE = None


def acquire_single_instance_lock() -> bool:
    """
    Empêche le lancement de plusieurs instances du bot.
    Retourne True si le verrou est acquis, sinon False.
    """
    global LOCK_FILE_HANDLE

    try:
        LOCK_FILE_HANDLE = open(LOCK_FILE_PATH, "w", encoding="utf-8")
    except OSError as e:
        logger.error("Impossible d'ouvrir le fichier de verrou : %s", e)
        return False

    try:
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(LOCK_FILE_HANDLE.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(LOCK_FILE_HANDLE.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        logger.error("Une autre instance du bot est déjà en cours d'exécution.")
        LOCK_FILE_HANDLE.close()
        LOCK_FILE_HANDLE = None
        return False

    LOCK_FILE_HANDLE.seek(0)
    LOCK_FILE_HANDLE.truncate()
    LOCK_FILE_HANDLE.write(str(os.getpid()))
    LOCK_FILE_HANDLE.flush()
    atexit.register(release_single_instance_lock)
    return True


def release_single_instance_lock():
    """Libère le verrou de l'instance courante."""
    global LOCK_FILE_HANDLE
    if not LOCK_FILE_HANDLE:
        return
    try:
        LOCK_FILE_HANDLE.close()
    except OSError:
        pass
    LOCK_FILE_HANDLE = None


# ════════════════════════════════════════════════════════════
#  HELPERS
# ════════════════════════════════════════════════════════════

def is_authorized(user_id: int) -> bool:
    """Vérifie si l'utilisateur est autorisé."""
    if not ALLOWED_IDS:
        return True  # Si aucun ID configuré, tout le monde peut accéder
    return user_id in ALLOWED_IDS


def parse_period(args: list) -> tuple[str, int, int]:
    """
    Parse les arguments de période.
    Exemples : S49, S 49, M12, M 12, 49 (= semaine par défaut)
    Retourne (period_type, year, value)
    """
    weeks = get_available_weeks()
    months = get_available_months()

    if not args:
        # Par défaut : dernière semaine disponible
        if weeks:
            y, w = weeks[-1]
            return ("week", y, w)
        return ("week", 2025, 49)

    text = " ".join(args).strip().upper()

    # Format Sxx ou S xx
    if text.startswith("S"):
        num = text[1:].strip()
        if num.isdigit():
            w = int(num)
            # Trouver l'année
            for y, wk in reversed(weeks):
                if wk == w:
                    return ("week", y, w)
            return ("week", 2025, w)

    # Format Mxx ou M xx
    if text.startswith("M"):
        num = text[1:].strip()
        if num.isdigit():
            m = int(num)
            for y, mo in reversed(months):
                if mo == m:
                    return ("month", y, m)
            return ("month", 2025, m)

    # Juste un nombre → semaine
    if text.isdigit():
        w = int(text)
        for y, wk in reversed(weeks):
            if wk == w:
                return ("week", y, w)
        return ("week", 2025, w)

    # Défaut
    if weeks:
        y, w = weeks[-1]
        return ("week", y, w)
    return ("week", 2025, 49)


async def send_long_message(update_or_chat_id, text: str, context: ContextTypes.DEFAULT_TYPE, parse_mode="HTML"):
    """Envoie un message long en le découpant si nécessaire (limite 4096 chars)."""
    MAX_LEN = 4000
    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > MAX_LEN:
            chunks.append(current)
            current = line
        else:
            current += ("\n" if current else "") + line
    if current:
        chunks.append(current)

    for chunk in chunks:
        if isinstance(update_or_chat_id, int):
            await context.bot.send_message(
                chat_id=update_or_chat_id, text=chunk, parse_mode=parse_mode,
            )
        else:
            await update_or_chat_id.message.reply_text(chunk, parse_mode=parse_mode)


# ════════════════════════════════════════════════════════════
#  COMMANDES
# ════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        await update.message.reply_text("⛔ Accès non autorisé.")
        return

    await update.message.reply_text(
        "🏭 <b>D-corp KPI Bot — Indicateurs Logistiques</b>\n\n"
        "Ce bot génère automatiquement les indicateurs logistiques "
        "pour les réunions Point 15' et Point 45'.\n\n"
        "Tapez /help pour voir les commandes disponibles.",
        parse_mode="HTML",
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    await update.message.reply_text(
        "📋 <b>Commandes disponibles</b>\n\n"
        "/kpi [S49|M12]    — Résumé rapide des KPIs\n"
        "/commandes [S49]  — Détail commandes par client/ref\n"
        "/delais [S49]     — Délais de traitement\n"
        "/qualite [S49]    — Taux transfert qualité\n"
        "/cadence [S49]    — Cadence par opérateur\n"
        "/charge [S49]     — Lissage de charge + graphique\n"
        "/rapport [S49]    — Rapport PDF complet\n"
        "/semaines         — Périodes disponibles\n"
        "/status           — État de la base\n"
        "/import           — Importer un CSV (envoyer le fichier)\n\n"
        "<i>Exemples : /kpi S49, /rapport M12, /kpi 50</i>",
        parse_mode="HTML",
    )


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    count = get_row_count()
    if count == 0:
        await update.message.reply_text(
            "📊 <b>Base de données vide.</b>\n\n"
            "Envoyez un fichier CSV pour importer des données,\n"
            "ou placez-le dans le dossier <code>data/</code>.",
            parse_mode="HTML",
        )
        return

    dmin, dmax = get_date_range()
    weeks = get_available_weeks()
    months = get_available_months()

    await update.message.reply_text(
        f"📊 <b>État de la base</b>\n\n"
        f"Lignes : <b>{count:,}</b>\n"
        f"Période : {dmin} → {dmax}\n"
        f"Semaines : {', '.join(f'S{w}' for _, w in weeks)}\n"
        f"Mois : {', '.join(f'M{m:02d}' for _, m in months)}",
        parse_mode="HTML",
    )


async def cmd_semaines(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    weeks = get_available_weeks()
    months = get_available_months()

    if not weeks:
        await update.message.reply_text("Aucune donnée disponible. Importez un CSV.")
        return

    lines = ["📅 <b>Périodes disponibles</b>\n"]
    lines.append("<b>Semaines :</b>")
    for y, w in weeks:
        lines.append(f"  S{w} ({y})")
    lines.append("\n<b>Mois :</b>")
    for y, m in months:
        mois_noms = ["", "Jan", "Fév", "Mar", "Avr", "Mai", "Jun",
                     "Jul", "Aoû", "Sep", "Oct", "Nov", "Déc"]
        lines.append(f"  M{m:02d} - {mois_noms[m]} {y}")

    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_kpi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    period_type, year, value = parse_period(context.args)
    await update.message.reply_text("⏳ Calcul des indicateurs en cours...")

    try:
        all_kpis = compute_all_kpis(period_type, year, value)
        text = format_summary(all_kpis)
        await send_long_message(update, text, context)
    except Exception as e:
        logger.error("Erreur KPI : %s", e, exc_info=True)
        await update.message.reply_text(f"❌ Erreur : {e}")


async def cmd_commandes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    period_type, year, value = parse_period(context.args)
    await update.message.reply_text("⏳ Calcul...")

    try:
        from kpi_engine import kpi_commandes
        data = kpi_commandes(period_type, year, value)
        text = format_commandes(data)
        await send_long_message(update, text, context)
    except Exception as e:
        logger.error("Erreur commandes : %s", e, exc_info=True)
        await update.message.reply_text(f"❌ Erreur : {e}")


async def cmd_delais(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    period_type, year, value = parse_period(context.args)
    await update.message.reply_text("⏳ Calcul...")

    try:
        from kpi_engine import kpi_delais
        data = kpi_delais(period_type, year, value)
        text = format_delais(data)
        await send_long_message(update, text, context)
    except Exception as e:
        logger.error("Erreur délais : %s", e, exc_info=True)
        await update.message.reply_text(f"❌ Erreur : {e}")


async def cmd_qualite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    period_type, year, value = parse_period(context.args)
    await update.message.reply_text("⏳ Calcul...")

    try:
        from kpi_engine import kpi_qualite
        data = kpi_qualite(period_type, year, value)
        text = format_qualite(data)
        await send_long_message(update, text, context)
    except Exception as e:
        logger.error("Erreur qualité : %s", e, exc_info=True)
        await update.message.reply_text(f"❌ Erreur : {e}")


async def cmd_cadence(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    period_type, year, value = parse_period(context.args)
    await update.message.reply_text("⏳ Calcul...")

    try:
        from kpi_engine import kpi_cadence
        data = kpi_cadence(period_type, year, value)
        text = format_cadence(data)
        await send_long_message(update, text, context)
    except Exception as e:
        logger.error("Erreur cadence : %s", e, exc_info=True)
        await update.message.reply_text(f"❌ Erreur : {e}")


async def cmd_charge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    period_type, year, value = parse_period(context.args)
    await update.message.reply_text("⏳ Calcul et génération du graphique...")

    try:
        from kpi_engine import kpi_charge
        from charts import chart_charge
        data = kpi_charge(period_type, year, value)

        # Texte
        text = format_charge(data)
        await send_long_message(update, text, context)

        # Graphique
        chart_path = chart_charge(data)
        if chart_path and os.path.exists(chart_path):
            with open(chart_path, "rb") as f:
                await update.message.reply_photo(photo=f)

    except Exception as e:
        logger.error("Erreur charge : %s", e, exc_info=True)
        await update.message.reply_text(f"❌ Erreur : {e}")


async def cmd_rapport(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_authorized(update.effective_user.id):
        return

    period_type, year, value = parse_period(context.args)
    msg = await update.message.reply_text(
        "⏳ Génération du rapport complet...\n"
        "Calcul des KPIs → Graphiques → PDF\n"
        "Cela peut prendre quelques secondes."
    )

    try:
        # 1. Calculer tous les KPIs
        all_kpis = compute_all_kpis(period_type, year, value)

        # 2. Générer les graphiques
        chart_paths = generate_all_charts(all_kpis)

        # 3. Générer le PDF
        pdf_path = generate_pdf_report(all_kpis, chart_paths)

        # 4. Envoyer le résumé texte
        text = format_summary(all_kpis)
        await send_long_message(update, text, context)

        # 5. Envoyer le dashboard en image
        for p in chart_paths:
            if "dashboard" in p and os.path.exists(p):
                with open(p, "rb") as f:
                    await update.message.reply_photo(photo=f, caption="📊 Dashboard")
                break

        # 6. Envoyer le PDF
        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename=os.path.basename(pdf_path),
                    caption=f"📄 Rapport {all_kpis['label']}",
                )

        await msg.edit_text("✅ Rapport généré et envoyé !")

    except Exception as e:
        logger.error("Erreur rapport : %s", e, exc_info=True)
        await msg.edit_text(f"❌ Erreur lors de la génération : {e}")


# ════════════════════════════════════════════════════════════
#  IMPORT CSV VIA TELEGRAM
# ════════════════════════════════════════════════════════════

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gère l'envoi de fichiers CSV via Telegram."""
    if not is_authorized(update.effective_user.id):
        return

    document = update.message.document
    if not document:
        return

    filename = document.file_name or "import.csv"
    if not filename.lower().endswith(".csv"):
        await update.message.reply_text("⚠️ Seuls les fichiers .csv sont acceptés.")
        return

    await update.message.reply_text(f"📥 Téléchargement de {filename}...")

    try:
        # Télécharger le fichier
        file = await context.bot.get_file(document.file_id)
        local_path = os.path.join(DATA_DIR, filename)
        await file.download_to_drive(local_path)

        # Importer
        count = import_csv(local_path, replace=True)
        await update.message.reply_text(
            f"✅ Import réussi !\n"
            f"Fichier : {filename}\n"
            f"Lignes importées : {count:,}\n\n"
            f"Utilisez /status pour vérifier, /kpi pour voir les indicateurs."
        )

    except Exception as e:
        logger.error("Erreur import : %s", e, exc_info=True)
        await update.message.reply_text(f"❌ Erreur d'import : {e}")


# ════════════════════════════════════════════════════════════
#  SCHEDULER (RAPPORTS AUTOMATIQUES)
# ════════════════════════════════════════════════════════════

async def scheduled_weekly_report(app: Application):
    """Envoie automatiquement le rapport hebdomadaire le lundi matin."""
    if AUTO_REPORT_CHAT_ID == 0:
        return

    logger.info("Envoi automatique du rapport hebdomadaire...")

    try:
        weeks = get_available_weeks()
        if not weeks:
            return

        year, week = weeks[-1]
        all_kpis = compute_all_kpis("week", year, week)
        chart_paths = generate_all_charts(all_kpis)
        pdf_path = generate_pdf_report(all_kpis, chart_paths)

        # Résumé texte
        text = f"🔔 <b>Rapport automatique — Point 15'</b>\n\n" + format_summary(all_kpis)
        await app.bot.send_message(
            chat_id=AUTO_REPORT_CHAT_ID, text=text, parse_mode="HTML",
        )

        # Dashboard
        for p in chart_paths:
            if "dashboard" in p and os.path.exists(p):
                with open(p, "rb") as f:
                    await app.bot.send_photo(chat_id=AUTO_REPORT_CHAT_ID, photo=f)
                break

        # PDF
        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                await app.bot.send_document(
                    chat_id=AUTO_REPORT_CHAT_ID,
                    document=f,
                    filename=os.path.basename(pdf_path),
                )

        logger.info("Rapport hebdomadaire envoyé.")

    except Exception as e:
        logger.error("Erreur rapport auto hebdo : %s", e, exc_info=True)


async def scheduled_monthly_report(app: Application):
    """Envoie automatiquement le rapport mensuel le 1er du mois."""
    if AUTO_REPORT_CHAT_ID == 0:
        return

    logger.info("Envoi automatique du rapport mensuel...")

    try:
        months = get_available_months()
        if not months:
            return

        year, month = months[-1]
        all_kpis = compute_all_kpis("month", year, month)
        chart_paths = generate_all_charts(all_kpis)
        pdf_path = generate_pdf_report(all_kpis, chart_paths)

        text = f"🔔 <b>Rapport automatique — Point 45'</b>\n\n" + format_summary(all_kpis)
        await app.bot.send_message(
            chat_id=AUTO_REPORT_CHAT_ID, text=text, parse_mode="HTML",
        )

        for p in chart_paths:
            if "dashboard" in p and os.path.exists(p):
                with open(p, "rb") as f:
                    await app.bot.send_photo(chat_id=AUTO_REPORT_CHAT_ID, photo=f)
                break

        if os.path.exists(pdf_path):
            with open(pdf_path, "rb") as f:
                await app.bot.send_document(
                    chat_id=AUTO_REPORT_CHAT_ID,
                    document=f,
                    filename=os.path.basename(pdf_path),
                )

        logger.info("Rapport mensuel envoyé.")

    except Exception as e:
        logger.error("Erreur rapport auto mensuel : %s", e, exc_info=True)


# ════════════════════════════════════════════════════════════
#  MAIN
# ════════════════════════════════════════════════════════════

def main():
    """Point d'entrée principal du bot."""
    if not acquire_single_instance_lock():
        print("⚠️ Une instance du bot est déjà active. Fermez-la avant de relancer bot.py.")
        return

    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN non défini dans .env")
        print("❌ Erreur : configurez TELEGRAM_TOKEN dans le fichier .env")
        print("   Copiez .env.example en .env et remplissez les valeurs.")
        return

    logger.info("Démarrage du bot D-corp KPI...")

    # Construire l'application Telegram
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # Enregistrer les commandes
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("semaines", cmd_semaines))
    app.add_handler(CommandHandler("kpi", cmd_kpi))
    app.add_handler(CommandHandler("commandes", cmd_commandes))
    app.add_handler(CommandHandler("delais", cmd_delais))
    app.add_handler(CommandHandler("qualite", cmd_qualite))
    app.add_handler(CommandHandler("cadence", cmd_cadence))
    app.add_handler(CommandHandler("charge", cmd_charge))
    app.add_handler(CommandHandler("rapport", cmd_rapport))

    # Handler pour les documents (import CSV)
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    # Scheduler pour les rapports automatiques
    if AUTO_REPORT_CHAT_ID != 0:
        scheduler = AsyncIOScheduler(timezone="Europe/Paris")

        # Point 15' : chaque lundi
        scheduler.add_job(
            scheduled_weekly_report,
            "cron",
            day_of_week=WEEKLY_REPORT_DAY,
            hour=WEEKLY_REPORT_HOUR,
            minute=WEEKLY_REPORT_MINUTE,
            args=[app],
            id="weekly_report",
        )

        # Point 45' : le 1er de chaque mois
        scheduler.add_job(
            scheduled_monthly_report,
            "cron",
            day=MONTHLY_REPORT_DAY,
            hour=MONTHLY_REPORT_HOUR,
            minute=MONTHLY_REPORT_MINUTE,
            args=[app],
            id="monthly_report",
        )

        scheduler.start()
        logger.info(
            "Scheduler activé : hebdo=%s %02d:%02d, mensuel=jour %d %02d:%02d",
            WEEKLY_REPORT_DAY, WEEKLY_REPORT_HOUR, WEEKLY_REPORT_MINUTE,
            MONTHLY_REPORT_DAY, MONTHLY_REPORT_HOUR, MONTHLY_REPORT_MINUTE,
        )

    logger.info("Bot prêt. Démarrage du polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
