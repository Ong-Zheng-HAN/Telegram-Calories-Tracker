import logging
from datetime import datetime

import pytz
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import MAX_PHOTOS_PER_MEAL, MAX_SINGLE_ITEM_CALORIES, USER_TIMEZONE
from handlers.command_handler import is_authorized, _detect_meal_type
from services import drive, sheets, vision

logger = logging.getLogger(__name__)

# Conversation states
COLLECTING_PHOTOS = 0
REVIEWING = 1
SHARED_COUNT = 2
SHARED_SPLIT = 3
SHARED_CUSTOM = 4
EDITING = 5


async def photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the first or additional photo in a meal."""
    if not is_authorized(update.effective_user.id):
        return ConversationHandler.END

    if "photos" not in context.user_data:
        context.user_data["photos"] = []

    photo = update.message.photo[-1]  # Highest resolution
    file = await photo.get_file()
    photo_bytes = await file.download_as_bytearray()
    context.user_data["photos"].append(bytes(photo_bytes))

    count = len(context.user_data["photos"])

    if count >= MAX_PHOTOS_PER_MEAL:
        await update.message.reply_text(
            f"Got {count} photos (max {MAX_PHOTOS_PER_MEAL}). Analysing now..."
        )
        return await _analyse_photos(update, context)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📸 Add more", callback_data="add_more"),
            InlineKeyboardButton("✅ That's all", callback_data="thats_all"),
        ]
    ])
    await update.message.reply_text(
        f"Got it! ({count} photo{'s' if count > 1 else ''}). Any more photos for this meal?",
        reply_markup=keyboard,
    )
    return COLLECTING_PHOTOS


async def collecting_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle button presses during photo collection."""
    query = update.callback_query
    await query.answer()

    if query.data == "add_more":
        await query.edit_message_text("Send me another photo!")
        return COLLECTING_PHOTOS
    elif query.data == "thats_all":
        await query.edit_message_text("Analysing your photos...")
        return await _analyse_photos(update, context)

    return COLLECTING_PHOTOS


async def _analyse_photos(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Send photos to Claude Vision and show results."""
    photos = context.user_data.get("photos", [])
    if not photos:
        msg = update.callback_query.message if update.callback_query else update.message
        await msg.reply_text("No photos to analyse.")
        return ConversationHandler.END

    result = vision.analyse_food_photos(photos)
    if not result:
        msg = update.callback_query.message if update.callback_query else update.message
        await msg.reply_text(
            "Couldn't analyse the photos. Please try again or use /log to enter manually."
        )
        _clear_session(context)
        return ConversationHandler.END

    context.user_data["analysis"] = result

    # Build response
    text = "I found:\n"
    warnings = []
    for i, item in enumerate(result.get("items", []), 1):
        text += f"  {i}. {item['food_name']} ({item.get('portion', 'N/A')}) — {item['calories']} kcal\n"
        if item.get("calories", 0) > MAX_SINGLE_ITEM_CALORIES:
            warnings.append(f"'{item['food_name']}' at {item['calories']} kcal seems high")

    text += f"\nTotal: {result.get('total_calories', 0)} kcal"
    text += f"\nProtein: {result.get('total_protein', 0)}g | Carbs: {result.get('total_carbs', 0)}g | Fat: {result.get('total_fat', 0)}g"

    if warnings:
        text += "\n\n⚠️ " + "\n⚠️ ".join(warnings)

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Log this", callback_data="log_confirm"),
            InlineKeyboardButton("✏️ Edit", callback_data="edit"),
        ],
        [
            InlineKeyboardButton("👥 Shared meal", callback_data="shared"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ],
    ])

    msg = update.callback_query.message if update.callback_query else update.message
    await msg.reply_text(text, reply_markup=keyboard)
    return REVIEWING


async def review_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle button presses on the review screen."""
    query = update.callback_query
    await query.answer()

    if query.data == "log_confirm":
        await query.edit_message_text(query.message.text + "\n\nSaving...")
        return await _save_meal(update, context)

    elif query.data == "cancel":
        await query.edit_message_text("Cancelled.")
        _clear_session(context)
        return ConversationHandler.END

    elif query.data == "shared":
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("2", callback_data="split_2"),
                InlineKeyboardButton("3", callback_data="split_3"),
                InlineKeyboardButton("4", callback_data="split_4"),
                InlineKeyboardButton("5", callback_data="split_5"),
            ],
            [InlineKeyboardButton("❌ Cancel", callback_data="cancel_shared")],
        ])
        await query.edit_message_text("How many people sharing?", reply_markup=keyboard)
        return SHARED_COUNT

    elif query.data == "edit":
        await query.edit_message_text(
            "Send me a corrected description of what you ate.\n"
            "Example: chicken rice (small portion), iced tea (no sugar)"
        )
        return EDITING

    return REVIEWING


async def editing_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle corrected food description during edit."""
    if not is_authorized(update.effective_user.id):
        return ConversationHandler.END

    msg = await update.message.reply_text("Re-analysing...")
    result = vision.analyse_manual_entry(update.message.text)

    if not result:
        await msg.edit_text("Couldn't parse that. Please try again or /cancel.")
        return EDITING

    context.user_data["analysis"] = result

    text = "Updated:\n"
    for i, item in enumerate(result.get("items", []), 1):
        text += f"  {i}. {item['food_name']} — {item['calories']} kcal\n"
    text += f"\nTotal: {result.get('total_calories', 0)} kcal"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Log this", callback_data="log_confirm"),
            InlineKeyboardButton("✏️ Edit again", callback_data="edit"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ])
    await msg.edit_text(text, reply_markup=keyboard)
    return REVIEWING


async def shared_count_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle number of people sharing selection."""
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_shared":
        # Go back to review
        return await _show_review_again(update, context)

    num_people = int(query.data.split("_")[1])
    context.user_data["shared_count"] = num_people

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"Equal split (1/{num_people} each)", callback_data="equal_split")],
        [InlineKeyboardButton("✏️ Custom portions", callback_data="custom_split")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_shared_split")],
    ])
    await query.edit_message_text(
        f"Sharing between {num_people} people. What's your share?",
        reply_markup=keyboard,
    )
    return SHARED_SPLIT


async def shared_split_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle split type selection."""
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_shared_split":
        return await _show_review_again(update, context)

    result = context.user_data.get("analysis", {})
    num_people = context.user_data.get("shared_count", 1)

    if query.data == "equal_split":
        # Divide everything equally
        split_result = {
            "items": [],
            "total_calories": round(result.get("total_calories", 0) / num_people),
            "total_protein": round(result.get("total_protein", 0) / num_people, 1),
            "total_carbs": round(result.get("total_carbs", 0) / num_people, 1),
            "total_fat": round(result.get("total_fat", 0) / num_people, 1),
        }
        for item in result.get("items", []):
            split_result["items"].append({
                **item,
                "calories": round(item["calories"] / num_people),
                "protein": round(item.get("protein", 0) / num_people, 1),
                "carbs": round(item.get("carbs", 0) / num_people, 1),
                "fat": round(item.get("fat", 0) / num_people, 1),
            })
        context.user_data["analysis"] = split_result

        text = f"Your share (1/{num_people}):\n"
        for i, item in enumerate(split_result["items"], 1):
            text += f"  {i}. {item['food_name']} — {item['calories']} kcal\n"
        text += f"\nTotal: {split_result['total_calories']} kcal"
        text += f"\nProtein: {split_result['total_protein']}g | Carbs: {split_result['total_carbs']}g | Fat: {split_result['total_fat']}g"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Log this", callback_data="log_confirm"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
            ]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
        return REVIEWING

    elif query.data == "custom_split":
        await query.edit_message_text(
            "Describe your portion.\n"
            "Example: I had 2 slices of pizza, no salad, 1 garlic bread"
        )
        return SHARED_CUSTOM


async def shared_custom_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle custom portion description for shared meals."""
    if not is_authorized(update.effective_user.id):
        return ConversationHandler.END

    msg = await update.message.reply_text("Calculating your portion...")
    result = vision.analyse_manual_entry(update.message.text)

    if not result:
        await msg.edit_text("Couldn't parse that. Please describe your portion again.")
        return SHARED_CUSTOM

    context.user_data["analysis"] = result

    text = "Your portion:\n"
    for i, item in enumerate(result.get("items", []), 1):
        text += f"  {i}. {item['food_name']} — {item['calories']} kcal\n"
    text += f"\nTotal: {result.get('total_calories', 0)} kcal"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Log this", callback_data="log_confirm"),
            InlineKeyboardButton("✏️ Edit", callback_data="edit"),
        ],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel")],
    ])
    await msg.edit_text(text, reply_markup=keyboard)
    return REVIEWING


async def _show_review_again(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Re-show the review screen (used when cancelling shared meal flow)."""
    query = update.callback_query
    result = context.user_data.get("analysis", {})

    text = "I found:\n"
    for i, item in enumerate(result.get("items", []), 1):
        text += f"  {i}. {item['food_name']} — {item['calories']} kcal\n"
    text += f"\nTotal: {result.get('total_calories', 0)} kcal"

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Log this", callback_data="log_confirm"),
            InlineKeyboardButton("✏️ Edit", callback_data="edit"),
        ],
        [
            InlineKeyboardButton("👥 Shared meal", callback_data="shared"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel"),
        ],
    ])
    await query.edit_message_text(text, reply_markup=keyboard)
    return REVIEWING


async def _save_meal(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save the analysed meal to Google Sheets and Drive."""
    query = update.callback_query
    result = context.user_data.get("analysis", {})
    photos = context.user_data.get("photos", [])

    tz = pytz.timezone(context.user_data.get("timezone", USER_TIMEZONE))
    now = datetime.now(tz)
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H:%M")
    meal_type = _detect_meal_type(now.hour)
    food_names = ", ".join(item["food_name"] for item in result.get("items", []))

    # Upload first photo to Drive
    photo_link = ""
    if photos:
        filename = now.strftime("%Y-%m-%d_%H%M%S.jpg")
        photo_link = drive.upload_photo(photos[0], filename) or ""

    success = sheets.append_row(
        date=date_str,
        time_str=time_str,
        meal_type=meal_type,
        food_items=food_names,
        calories=result.get("total_calories", 0),
        protein=result.get("total_protein", 0),
        carbs=result.get("total_carbs", 0),
        fat=result.get("total_fat", 0),
        photo_link=photo_link,
    )

    if success:
        await query.edit_message_text(
            f"✅ Logged ({meal_type}):\n"
            f"{food_names}\n"
            f"Total: {result.get('total_calories', 0)} kcal"
        )
    else:
        await query.edit_message_text(
            "Analysed the food but couldn't save to sheet. Please try again."
        )

    _clear_session(context)
    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the current conversation."""
    _clear_session(context)
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END


def _clear_session(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Clear photo session data while preserving user settings."""
    context.user_data.pop("photos", None)
    context.user_data.pop("analysis", None)
    context.user_data.pop("shared_count", None)


def get_conversation_handler() -> ConversationHandler:
    """Build and return the photo conversation handler."""
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.PHOTO, photo_received),
        ],
        states={
            COLLECTING_PHOTOS: [
                MessageHandler(filters.PHOTO, photo_received),
                CallbackQueryHandler(collecting_callback, pattern="^(add_more|thats_all)$"),
            ],
            REVIEWING: [
                CallbackQueryHandler(review_callback, pattern="^(log_confirm|cancel|shared|edit)$"),
            ],
            EDITING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, editing_text),
            ],
            SHARED_COUNT: [
                CallbackQueryHandler(shared_count_callback, pattern="^(split_\\d+|cancel_shared)$"),
            ],
            SHARED_SPLIT: [
                CallbackQueryHandler(shared_split_callback, pattern="^(equal_split|custom_split|cancel_shared_split)$"),
            ],
            SHARED_CUSTOM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, shared_custom_text),
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
        ],
        per_user=True,
        per_chat=True,
    )
