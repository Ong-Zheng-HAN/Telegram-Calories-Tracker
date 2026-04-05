# Telegram Calorie Tracker Bot — Technical Plan

## Overview

A personal Telegram bot that allows you to upload food photos, automatically identifies the food and estimates nutritional data using AI vision (Claude), stores all data in Google Sheets, and answers natural language questions about calorie intake and meal planning.

This project is designed for **personal use** but the repo is public so anyone can set up their own instance with their own API keys, Telegram bot, and Google account.

---

## Architecture

```
User (Telegram App)
        │
        ▼
Telegram Bot (Python) ─── receives photos & text messages
        │
        ├── Photo(s) uploaded ──► Collect all photos for the meal
        │                              │
        │                              ▼
        │                        Claude Vision API
        │                        (analyse all photos together)
        │                              │
        │                              ▼
        │                        Structured Data Extraction
        │                        (food name, calories, protein, carbs, fat)
        │                              │
        │                              ▼
        │                        User confirms / edits / cancels
        │                              │
        │                              ├──► Google Sheets (append row)
        │                              └──► Google Drive (save photo)
        │
        └── Text / command ──► Read Google Sheets data
                                   │
                                   ▼
                             LLM Analysis (Claude API)
                             (answer user's question using sheet data)
                                   │
                                   ▼
                             Bot replies to user
```

---

## Tech Stack

| Component              | Technology                                 |
| ---------------------- | ------------------------------------------ |
| Language               | Python 3.10+                               |
| Telegram bot framework | `python-telegram-bot` (v20+)               |
| AI vision & analysis   | Anthropic Claude API (`anthropic` SDK)     |
| Spreadsheet            | Google Sheets via `gspread`                |
| Photo storage          | Google Drive via `google-api-python-client` |
| Hosting                | Contabo VPS (future: Mac Studio via Docker) |

---

## Component Details

### 1. Telegram Bot Setup

- Create a bot via Telegram's **BotFather** (`/newbot` command).
- Save the bot token securely (environment variable).
- Use `python-telegram-bot` library (async, v20+).
- Register handlers for:
  - `/start` — welcome message and instructions.
  - `/timezone` — set user's timezone for accurate meal type detection.
  - `/log` — manual food entry (fallback when photos aren't available).
  - `/summary` — quick daily totals without going through the LLM.
  - `/delete` — remove the last logged entry.
  - **Photo messages** — trigger the food recognition pipeline.
  - **Text messages** — trigger the Q&A / analytics pipeline.

### 2. Food Photo Recognition Pipeline

**Trigger:** User sends one or more photos in the Telegram chat.

**Flow:**

1. Bot receives the first photo and prompts:
   ```
   Got it! Any more photos for this meal?
   [📸 Add more] [✅ That's all]
   ```
2. If **Add more** — bot waits for additional photos (up to 3 total for token efficiency). Each additional photo prompts the same question.
3. If the user sends more than 3 photos, the bot replies:
   ```
   That's a lot of photos! For best results, pick the 3 best
   shots that show all your dishes clearly.
   [📸 Send again] [✅ Use first 3]
   ```
4. Once the user taps **That's all**, the bot:
   - Downloads all photos from Telegram servers.
   - Converts images to base64.
   - Sends all photos to Claude Vision API in a single request with the following system prompt:

   ```
   You are a nutritionist AI. Analyse the food in these photos.
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
   }
   ```

5. Parse the JSON response (with retry on malformed JSON — see Error Handling).
6. Validate calorie estimates (sanity check — see Error Handling).
7. Present results to user with inline keyboard:
   ```
   I found:
    1. Chicken rice — 550 kcal
    2. Grilled fish — 400 kcal
    3. Soup — 80 kcal
    4. Iced tea — 100 kcal
    Total: 1130 kcal

    [✅ Log this] [✏️ Edit] [👥 Shared meal] [❌ Cancel]
   ```

8. **If Log this** — save to Google Sheets and upload photos to Google Drive.
9. **If Edit** — user can correct food names, portions, or calorie values via text, then confirm.
10. **If Shared meal** — trigger the shared meal flow (see below).
11. **If Cancel** — discard everything.

**Note:** A single photo can capture multiple dishes (e.g., a whole table spread). Users don't need to take one photo per dish — one good shot of the full meal is usually enough, with optional close-ups for hard-to-identify items.

### 3. Shared Meal Flow

When the user taps **Shared meal** after analysis:

1. Bot asks:
   ```
   How many people sharing?
   [2] [3] [4] [5] [Custom]
   ```
2. Bot asks about portion:
   ```
   What's your share?
   [Equal split — 1/N each] [✏️ Custom portions]
   ```
3. **Equal split** — divides all items by N and shows updated totals for confirmation.
4. **Custom portions** — user describes their share via text (e.g., "I had 2 slices of pizza, no salad, 1 garlic bread"), Claude interprets and adjusts.
5. Final confirmation before logging.

### 4. Google Sheets Structure

**Sheet name:** `CalorieLog`

| Column | Field       | Example                      |
| ------ | ----------- | ---------------------------- |
| A      | Date        | 2026-04-05                   |
| B      | Time        | 12:35                        |
| C      | Meal Type   | Lunch                        |
| D      | Food Items  | Chicken rice, Iced tea       |
| E      | Calories    | 650                          |
| F      | Protein (g) | 35                           |
| G      | Carbs (g)   | 80                           |
| H      | Fat (g)     | 18                           |
| I      | Photo Link  | https://drive.google.com/... |

**Meal type** is auto-detected based on the user's configured timezone:
- Before 11:00 → Breakfast
- 11:00–14:00 → Lunch
- 14:00–17:00 → Snack
- 17:00–21:00 → Dinner
- After 21:00 → Supper

**Authentication:** Use a Google Cloud service account with a JSON key file. Share the Google Sheet and a Google Drive folder with the service account email.

### 5. Google Drive Photo Storage

- Create a dedicated folder in Google Drive (e.g. `CalorieTracker_Photos`).
- Upload each food photo with a filename format: `YYYY-MM-DD_HHMMSS.jpg`.
- Keep files restricted to the service account (do not set public access).
- Store the Drive file link in the Google Sheet row for personal reference.

**Note:** The Drive photos are only for your own records. Claude analyses the photo at upload time directly from Telegram — it never reads from Drive later.

### 6. Manual Entry (`/log` command)

For meals without a photo (e.g., eating out, forgot to take a photo):

```
/log chicken rice 550cal 35p 80c 18f
```

Or a simpler format that Claude can parse:

```
/log chicken rice, iced tea
```

If only food names are provided (no macros), Claude estimates the nutritional data based on the food names alone.

### 7. Quick Summary (`/summary` command)

Returns today's totals directly from the Sheet without an LLM call:

```
/summary

📊 Today (5 Apr 2026):
 Meals logged: 3
 Calories: 1,450 / day
 Protein: 85g | Carbs: 160g | Fat: 45g
```

### 8. Delete Entry (`/delete` command)

Removes the most recent logged entry:

```
/delete

Deleted last entry:
 12:35 — Chicken rice, Iced tea (650 kcal)
```

### 9. Q&A / Analytics Pipeline

**Trigger:** User sends a text message (not a photo, not a command).

**Steps:**

1. Bot reads all data from the Google Sheet using `gspread`.
2. Format the data as a structured context string (e.g. CSV or JSON).
3. Send to Claude API with a system prompt:

```
You are a nutrition analytics assistant. You have access to the user's
food log data below. Answer their question accurately based on this data.
Be conversational and helpful. If they ask for suggestions, provide
practical, actionable advice.

When calculating totals:
- "Today" means the current date.
- "This week" means the last 7 days.
- "This month" means the last 30 days.

Food log data:
{sheet_data}
```

4. The user's text message is sent as the user message.
5. Return Claude's response to the user via Telegram.

**Example questions the bot can handle:**

- "How many calories did I eat today?"
- "What's my average daily calorie intake this week?"
- "Which meal had the most calories yesterday?"
- "Show me my protein intake trend for the past week."
- "Suggest lower calorie alternatives for my usual lunch."

---

## Security

Since this is a personal bot with a public repo, the following measures apply:

### Credential Protection
- `.env` and `credentials.json` are **gitignored** — never committed to the repo.
- A `.env.example` file with placeholder values is provided for reference.
- Store `credentials.json` outside the project directory. Use the `GOOGLE_CREDENTIALS_PATH` environment variable to point to its location.

### Bot Access Control
- Add an `ALLOWED_USER_IDS` environment variable containing your Telegram user ID.
- The bot checks every incoming message against this allowlist and ignores unauthorised users.
- This prevents strangers from discovering your bot and consuming your API credits.

### Data Privacy
- Google Drive photos are kept restricted to the service account (no public links).
- Sheet data stays in your own Google account.

---

## Error Handling

### Claude Vision — Malformed JSON
- Wrap JSON parsing in try/except.
- On failure, retry once with a stricter prompt ("You must respond with valid JSON only").
- After 2 failures, reply to user: "Couldn't analyse this photo. Try again or use /log to enter manually."

### Claude Vision — Unreasonable Estimates
- If any single item exceeds 3,000 kcal, flag it to the user before logging:
  ```
  ⚠️ "Chicken rice" was estimated at 5,000 kcal — that seems high.
  Please confirm or edit before logging.
  ```

### Google Sheets / Drive API Failures
- Retry with exponential backoff (up to 3 attempts).
- If all retries fail, notify the user: "Couldn't save to your sheet. I'll try again shortly."

### Claude API Timeout
- Set a 30-second timeout on all Claude API calls.
- On timeout, notify user and suggest retrying.

### Photo Download Failures
- If Telegram photo download fails, retry once.
- On second failure, ask user to resend the photo.

---

## Project File Structure

```
telegram-calorie-tracker/
├── .env.example                 # Environment variable template
├── .gitignore                   # Ignore .env, credentials, __pycache__
├── requirements.txt             # Python dependencies
├── bot.py                       # Main bot entry point
├── handlers/
│   ├── __init__.py
│   ├── photo_handler.py         # Photo upload and food recognition flow
│   ├── text_handler.py          # Q&A and analytics
│   └── command_handler.py       # /start, /log, /summary, /delete, /timezone
├── services/
│   ├── __init__.py
│   ├── vision.py                # Claude Vision API integration
│   ├── sheets.py                # Google Sheets read/write
│   ├── drive.py                 # Google Drive photo upload
│   └── analytics.py             # Claude LLM for Q&A
├── config.py                    # Configuration and constants
└── credentials.json             # Google service account key (gitignored)
```

---

## Environment Variables

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ANTHROPIC_API_KEY=your_anthropic_api_key
GOOGLE_SHEETS_ID=your_google_sheet_id
GOOGLE_DRIVE_FOLDER_ID=your_drive_folder_id
GOOGLE_CREDENTIALS_PATH=./credentials.json
ALLOWED_USER_IDS=123456789
USER_TIMEZONE=Asia/Singapore
```

---

## Dependencies

```txt
python-telegram-bot>=20.0
anthropic>=0.40.0
gspread>=6.0.0
google-auth>=2.0.0
google-api-python-client>=2.0.0
python-dotenv>=1.0.0
Pillow>=10.0.0
pytz>=2024.1
```

---

## Setup Instructions

### Step 1: Create Telegram Bot

1. Open Telegram and search for `@BotFather`.
2. Send `/newbot` and follow the prompts to name your bot.
3. Copy the bot token and save it as `TELEGRAM_BOT_TOKEN`.

### Step 2: Get Your Telegram User ID

1. Search for `@userinfobot` on Telegram and start a chat.
2. It will reply with your user ID.
3. Save it as `ALLOWED_USER_IDS` in your `.env` file.

### Step 3: Set Up Google Cloud Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a new project (or use an existing one).
3. Enable the **Google Sheets API** and **Google Drive API**.
4. Create a **Service Account** under IAM & Admin > Service Accounts.
5. Generate a JSON key and save it as `credentials.json` (outside the project directory for safety).
6. Copy the service account email (e.g. `bot@project.iam.gserviceaccount.com`).

### Step 4: Set Up Google Sheets

1. Create a new Google Sheet.
2. Name the first sheet tab `CalorieLog`.
3. Add headers in row 1: `Date | Time | Meal Type | Food Items | Calories | Protein | Carbs | Fat | Photo Link`.
4. Share the sheet with your service account email (Editor access).
5. Copy the sheet ID from the URL and save as `GOOGLE_SHEETS_ID`.

### Step 5: Set Up Google Drive Folder

1. Create a folder in Google Drive called `CalorieTracker_Photos`.
2. Share it with the service account email (Editor access).
3. Copy the folder ID from the URL and save as `GOOGLE_DRIVE_FOLDER_ID`.

### Step 6: Get Anthropic API Key

1. Sign up at [console.anthropic.com](https://console.anthropic.com/).
2. Generate an API key.
3. Save it as `ANTHROPIC_API_KEY`.

### Step 7: Deploy

1. Clone the repo to your Contabo VPS.
2. Install dependencies: `pip install -r requirements.txt`.
3. Create a `.env` file with all environment variables.
4. Run the bot: `python bot.py`.
5. (Recommended) Use `systemd` to keep the bot running as a service.

---

## Hosting & Migration

### Current: Contabo VPS
- Affordable, always-on server for running the bot.
- Use `systemd` to manage the bot process.

### Future: Mac Studio
- Containerise the project with Docker for easy migration.
- Create a `Dockerfile` and `docker-compose.yml`.
- All dependencies are ARM64 compatible (Apple Silicon).
- For external access from Mac Studio, use Cloudflare Tunnel or Tailscale.

---

## Future Enhancements

- **Meal type override:** Let user specify meal type via inline keyboard buttons after uploading a photo.
- **Weekly reports:** Scheduled message every Sunday with weekly summary.
- **Goal setting:** Let user set daily calorie/macro targets and get alerts when approaching limits.
- **Barcode scanning:** Add support for scanning packaged food barcodes via a nutrition API (e.g. OpenFoodFacts).
- **Export:** Generate a PDF or CSV report on demand.
- **Conversation context:** Keep short conversation history (last 2-3 messages) for follow-up questions in Q&A.
- **Health check:** Set up UptimeRobot or similar to monitor bot uptime and alert if it goes down.

---

*Plan created: April 2026*
