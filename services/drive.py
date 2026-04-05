import io
import logging
import time

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

from config import GOOGLE_CREDENTIALS_PATH, GOOGLE_DRIVE_FOLDER_ID, MAX_RETRIES

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]


def _get_drive_service():
    creds = Credentials.from_service_account_file(GOOGLE_CREDENTIALS_PATH, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def upload_photo(photo_bytes: bytes, filename: str) -> str | None:
    """Upload a photo to Google Drive and return the file link. Returns None on failure."""
    for attempt in range(MAX_RETRIES):
        try:
            service = _get_drive_service()
            file_metadata = {
                "name": filename,
                "parents": [GOOGLE_DRIVE_FOLDER_ID],
            }
            media = MediaIoBaseUpload(
                io.BytesIO(photo_bytes),
                mimetype="image/jpeg",
                resumable=True,
            )
            file = service.files().create(
                body=file_metadata,
                media_body=media,
                fields="id",
                supportsAllDrives=True,
            ).execute()
            file_id = file.get("id")
            return f"https://drive.google.com/file/d/{file_id}/view"
        except Exception as e:
            logger.error("Drive upload attempt %d failed: %s", attempt + 1, e)
            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)
    return None
