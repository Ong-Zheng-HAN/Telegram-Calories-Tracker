import logging

from telegram import Update
from telegram.ext import ContextTypes

from handlers.command_handler import is_authorized
from services import analytics, sheets

logger = logging.getLogger(__name__)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id):
        return

    question = update.message.text
    msg = await update.message.reply_text("Thinking...")

    all_data = sheets.get_all_data()
    answer = analytics.answer_question(question, all_data)
    await msg.edit_text(answer)
