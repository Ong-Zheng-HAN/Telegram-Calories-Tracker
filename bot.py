import logging

from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters

from config import TELEGRAM_BOT_TOKEN
from handlers.command_handler import start, help_command, summary, delete, log_meal, set_timezone
from handlers.photo_handler import get_conversation_handler
from handlers.text_handler import handle_text

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set. Check your .env file.")
        return

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Photo conversation handler (must be added before the text handler)
    app.add_handler(get_conversation_handler())

    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("summary", summary))
    app.add_handler(CommandHandler("delete", delete))
    app.add_handler(CommandHandler("log", log_meal))
    app.add_handler(CommandHandler("timezone", set_timezone))

    # Text message handler (Q&A) — catches all non-command text
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    logger.info("Bot starting...")
    app.run_polling()


if __name__ == "__main__":
    main()
