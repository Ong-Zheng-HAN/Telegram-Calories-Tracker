# Telegram Calorie Tracker Bot

A personal Telegram bot that tracks your calorie intake from food photos using AI vision (Claude). Send a photo of your meal, and the bot identifies the food, estimates nutritional data, and logs everything to Google Sheets. You can also ask natural language questions about your eating habits.

## Features

- **Photo analysis** — Send 1-3 photos of your meal. Claude Vision identifies each dish and estimates calories, protein, carbs, and fat.
- **Confirmation flow** — Review, edit, or cancel before anything is logged.
- **Shared meals** — Split calories equally or by custom portions when eating with others.
- **Manual entry** — Log meals via text with `/log chicken rice, iced tea`.
- **Q&A** — Ask questions like "How many calories did I eat today?" and get answers based on your logged data.
- **Quick summary** — `/summary` shows today's totals instantly without an API call.
- **Delete entries** — `/delete` removes the last logged entry.
- **Timezone support** — Meal type (breakfast/lunch/dinner/snack/supper) auto-detected based on your timezone.
- **Access control** — Restrict the bot to your Telegram user ID only.

## How It Works

```
You send a food photo on Telegram
        |
Bot asks: "Any more photos for this meal?"
        |
You tap "That's all"
        |
Claude Vision analyses all photos together
        |
Bot shows: "Chicken rice - 550 kcal, Iced tea - 100 kcal. Log this?"
        |
You confirm --> Saved to Google Sheets
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.10+ |
| Telegram bot | `python-telegram-bot` (v20+) |
| AI vision & Q&A | Anthropic Claude API |
| Data storage | Google Sheets via `gspread` |
| Photo storage | Telegram (unlimited, free) |

## Project Structure

```
├── bot.py                      # Main entry point
├── config.py                   # Configuration and prompts
├── requirements.txt            # Python dependencies
├── handlers/
│   ├── photo_handler.py        # Photo upload flow with multi-photo support
│   ├── text_handler.py         # Q&A via Claude + Sheet data
│   └── command_handler.py      # /start, /log, /summary, /delete, /timezone
├── services/
│   ├── vision.py               # Claude Vision API integration
│   ├── sheets.py               # Google Sheets read/write
│   ├── drive.py                # Google Drive (optional, unused by default)
│   └── analytics.py            # Claude Q&A on food log data
```

## Setup

### Prerequisites

- Python 3.10+
- A Telegram account
- An Anthropic API key ([console.anthropic.com](https://console.anthropic.com/))
- A Google Cloud service account with Sheets API enabled

### 1. Create a Telegram Bot

1. Open Telegram and search for `@BotFather`.
2. Send `/newbot` and follow the prompts.
3. Save the bot token.

### 2. Get Your Telegram User ID

1. Search for `@userinfobot` on Telegram.
2. It will reply with your user ID.

### 3. Set Up Google Cloud

1. Go to [Google Cloud Console](https://console.cloud.google.com/).
2. Create a project and enable the **Google Sheets API**.
3. Create a **Service Account** and download the JSON key.
4. Copy the service account email.

### 4. Set Up Google Sheets

1. Create a new Google Sheet.
2. Rename the first tab to `CalorieLog`.
3. Add headers in row 1: `Date | Time | Meal Type | Food Items | Calories | Protein (g) | Carbs (g) | Fat (g) | Photo Link`
4. Share the sheet with your service account email (Editor access).
5. Copy the Sheet ID from the URL.

### 5. Configure Environment

Copy `.env.example` to `.env` and fill in your values:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
ANTHROPIC_API_KEY=your_anthropic_api_key
GOOGLE_SHEETS_ID=your_sheet_id
GOOGLE_DRIVE_FOLDER_ID=your_drive_folder_id
GOOGLE_CREDENTIALS_PATH=./credentials.json
ALLOWED_USER_IDS=your_telegram_user_id
USER_TIMEZONE=Asia/Singapore
```

### 6. Install and Run

```bash
git clone https://github.com/Ong-Zheng-HAN/Telegram-Calories-Tracker.git
cd Telegram-Calories-Tracker
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 bot.py
```

### 7. Run as a Service (Optional)

To keep the bot running 24/7 on a VPS, create a systemd service:

```bash
sudo nano /etc/systemd/system/caloriebot.service
```

```ini
[Unit]
Description=Telegram Calorie Tracker Bot
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/home/your_username/Telegram-Calories-Tracker
ExecStart=/home/your_username/Telegram-Calories-Tracker/venv/bin/python3 bot.py
Restart=always
RestartSec=10
EnvironmentFile=/home/your_username/Telegram-Calories-Tracker/.env

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable caloriebot
sudo systemctl start caloriebot
```

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Welcome message and instructions |
| `/log <food>` | Log a meal manually (e.g. `/log chicken rice, iced tea`) |
| `/summary` | Today's calorie and macro totals |
| `/delete` | Remove the last logged entry |
| `/timezone <tz>` | Set your timezone (e.g. `/timezone Asia/Singapore`) |
| `/help` | Show available commands |

## License

MIT
