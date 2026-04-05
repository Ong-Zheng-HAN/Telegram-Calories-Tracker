import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_USER_IDS = [
    int(uid.strip())
    for uid in os.getenv("ALLOWED_USER_IDS", "").split(",")
    if uid.strip()
]

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-sonnet-4-20250514"
CLAUDE_TIMEOUT = 30

# Google
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")
GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "./credentials.json")
SHEET_NAME = "CalorieLog"

# User settings
USER_TIMEZONE = os.getenv("USER_TIMEZONE", "Asia/Singapore")

# Meal type detection by hour
MEAL_TIMES = {
    (0, 11): "Breakfast",
    (11, 14): "Lunch",
    (14, 17): "Snack",
    (17, 21): "Dinner",
    (21, 24): "Supper",
}

# Limits
MAX_PHOTOS_PER_MEAL = 3
MAX_SINGLE_ITEM_CALORIES = 3000
MAX_RETRIES = 3

# Vision prompt
VISION_SYSTEM_PROMPT = """You are a nutritionist AI. Analyse the food in these photos.
Multiple photos may show the same meal from different angles —
use all of them for a more accurate assessment.

For each unique food item visible, estimate:
- Food name
- Portion size (estimated)
- Calories (kcal)
- Protein (g)
- Carbohydrates (g)
- Fat (g)

Return your response as JSON only, no other text:
{
  "items": [
    {
      "food_name": "...",
      "portion": "...",
      "calories": 0,
      "protein": 0,
      "carbs": 0,
      "fat": 0
    }
  ],
  "total_calories": 0,
  "total_protein": 0,
  "total_carbs": 0,
  "total_fat": 0
}"""

# Analytics prompt
ANALYTICS_SYSTEM_PROMPT = """You are a nutrition analytics assistant. You have access to the user's
food log data below. Answer their question accurately based on this data.
Be conversational and helpful. If they ask for suggestions, provide
practical, actionable advice.

When calculating totals:
- "Today" means the current date.
- "This week" means the last 7 days.
- "This month" means the last 30 days.

Food log data:
{sheet_data}"""

# Manual log prompt
MANUAL_LOG_PROMPT = """You are a nutritionist AI. The user wants to log a meal manually.
They provided: {food_description}

Estimate the nutritional data for these food items.
Return your response as JSON only, no other text:
{{
  "items": [
    {{
      "food_name": "...",
      "portion": "...",
      "calories": 0,
      "protein": 0,
      "carbs": 0,
      "fat": 0
    }}
  ],
  "total_calories": 0,
  "total_protein": 0,
  "total_carbs": 0,
  "total_fat": 0
}}"""
