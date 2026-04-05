import logging
from datetime import datetime

import pytz
from telegram import Update
from telegram.ext import ContextTypes

from config import ALLOWED_USER_IDS, USER_TIMEZONE, MAX_SINGLE_ITEM_CALORIES
from services import sheets, vision

logger = logging.getLogger(__name__)


def is_authorized(user_id: int) -> bool:
    if not ALLOWED_USER_IDS:
        return True
    return user_id in ALLOWED_USER_IDS


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id):
        return
    await update.message.reply_text(
        "Welcome to Calorie Tracker!\n\n"
        "Send me a photo of your food and I'll estimate the calories and macros.\n\n"
        "Commands:\n"
        "/log <food> — Log a meal manually\n"
        "/summary — Today's calorie summary\n"
        "/delete — Remove the last entry\n"
        "/timezone <tz> — Set your timezone\n"
        "/help — Show this message"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id):
        return
    await start(update, context)


async def summary(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id):
        return

    tz = pytz.timezone(context.user_data.get("timezone", USER_TIMEZONE))
    today_str = datetime.now(tz).strftime("%Y-%m-%d")
    today_data = sheets.get_today_data(today_str)

    if not today_data:
        await update.message.reply_text(f"No meals logged today ({today_str}).")
        return

    total_cal = sum(int(row.get("Calories", 0)) for row in today_data)
    total_protein = sum(float(row.get("Protein (g)", 0)) for row in today_data)
    total_carbs = sum(float(row.get("Carbs (g)", 0)) for row in today_data)
    total_fat = sum(float(row.get("Fat (g)", 0)) for row in today_data)

    await update.message.reply_text(
        f"Today ({today_str}):\n"
        f"Meals logged: {len(today_data)}\n"
        f"Calories: {total_cal} kcal\n"
        f"Protein: {total_protein:.1f}g | Carbs: {total_carbs:.1f}g | Fat: {total_fat:.1f}g"
    )


async def delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id):
        return

    deleted = sheets.delete_last_row()
    if deleted:
        await update.message.reply_text(
            f"Deleted last entry:\n"
            f"{deleted['time']} — {deleted['food_items']} ({deleted['calories']} kcal)"
        )
    else:
        await update.message.reply_text("No entries to delete.")


async def log_meal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id):
        return

    if not context.args:
        await update.message.reply_text("Usage: /log <food description>\nExample: /log chicken rice, iced tea")
        return

    food_description = " ".join(context.args)
    msg = await update.message.reply_text("Estimating nutritional data...")

    result = vision.analyse_manual_entry(food_description)
    if not result:
        await msg.edit_text("Couldn't estimate nutritional data. Please try again.")
        return

    # Check for unreasonable estimates
    warnings = []
    for item in result.get("items", []):
        if item.get("calories", 0) > MAX_SINGLE_ITEM_CALORIES:
            warnings.append(f"'{item['food_name']}' estimated at {item['calories']} kcal — seems high")

    tz = pytz.timezone(context.user_data.get("timezone", USER_TIMEZONE))
    now = datetime.now(tz)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    meal_type = _detect_meal_type(now.hour)
    food_names = ", ".join(item["food_name"] for item in result.get("items", []))

    success = sheets.append_row(
        date=date_str,
        time_str=time_str,
        meal_type=meal_type,
        food_items=food_names,
        calories=result.get("total_calories", 0),
        protein=result.get("total_protein", 0),
        carbs=result.get("total_carbs", 0),
        fat=result.get("total_fat", 0),
    )

    if not success:
        await msg.edit_text("Analysed the food but couldn't save to sheet. Please try again.")
        return

    text = f"Logged ({meal_type}):\n"
    for item in result.get("items", []):
        text += f"  • {item['food_name']} — {item['calories']} kcal\n"
    text += f"\nTotal: {result.get('total_calories', 0)} kcal"
    text += f"\nProtein: {result.get('total_protein', 0)}g | Carbs: {result.get('total_carbs', 0)}g | Fat: {result.get('total_fat', 0)}g"

    if warnings:
        text += "\n\n⚠️ " + "\n⚠️ ".join(warnings)

    await msg.edit_text(text)


async def set_timezone(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_authorized(update.effective_user.id):
        return

    if not context.args:
        current = context.user_data.get("timezone", USER_TIMEZONE)
        await update.message.reply_text(
            f"Current timezone: {current}\n"
            f"Usage: /timezone <timezone>\n"
            f"Example: /timezone Asia/Singapore"
        )
        return

    tz_name = context.args[0]
    try:
        pytz.timezone(tz_name)
        context.user_data["timezone"] = tz_name
        await update.message.reply_text(f"Timezone set to {tz_name}.")
    except pytz.exceptions.UnknownTimeZoneError:
        await update.message.reply_text(f"Unknown timezone: {tz_name}\nExample: Asia/Singapore, US/Eastern, Europe/London")


def _detect_meal_type(hour: int) -> str:
    if hour < 11:
        return "Breakfast"
    elif hour < 14:
        return "Lunch"
    elif hour < 17:
        return "Snack"
    elif hour < 21:
        return "Dinner"
    else:
        return "Supper"
