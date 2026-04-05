import logging
import time

import gspread
from google.oauth2.service_account import Credentials

from config import GOOGLE_CREDENTIALS_PATH, GOOGLE_SHEETS_ID, SHEET_NAME, MAX_RETRIES

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _get_worksheet() -> gspread.Worksheet:
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_PATH, scopes=SCOPES)
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(GOOGLE_SHEETS_ID)
    return sh.worksheet(SHEET_NAME)


def append_row(date: str, time_str: str, meal_type: str, food_items: str,
               calories: int, protein: float, carbs: float, fat: float,
               photo_link: str = "") -> bool:
    """Append a meal entry row to the sheet. Returns True on success."""
    row = [date, time_str, meal_type, food_items, calories, protein, carbs, fat, photo_link]
    for attempt in range(MAX_RETRIES):
        try:
            ws = _get_worksheet()
            ws.append_row(row, value_input_option="USER_ENTERED")
            return True
        except Exception as e:
            logger.error("Sheets append attempt %d failed: %s", attempt + 1, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
    return False


def delete_last_row() -> dict | None:
    """Delete the last data row and return its contents. Returns None on failure."""
    for attempt in range(MAX_RETRIES):
        try:
            ws = _get_worksheet()
            all_rows = ws.get_all_values()
            if len(all_rows) <= 1:
                return None
            last_row = all_rows[-1]
            ws.delete_rows(len(all_rows))
            return {
                "date": last_row[0],
                "time": last_row[1],
                "meal_type": last_row[2],
                "food_items": last_row[3],
                "calories": last_row[4],
                "protein": last_row[5],
                "carbs": last_row[6],
                "fat": last_row[7],
            }
        except Exception as e:
            logger.error("Sheets delete attempt %d failed: %s", attempt + 1, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
    return None


def get_all_data() -> list[dict]:
    """Read all rows from the sheet as a list of dicts."""
    for attempt in range(MAX_RETRIES):
        try:
            ws = _get_worksheet()
            return ws.get_all_records()
        except Exception as e:
            logger.error("Sheets read attempt %d failed: %s", attempt + 1, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
    return []


def get_today_data(today_str: str) -> list[dict]:
    """Get all entries for a specific date."""
    all_data = get_all_data()
    return [row for row in all_data if row.get("Date") == today_str]
