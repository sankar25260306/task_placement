"""Run once on a desktop to authorize Google Calendar event/Meet creation.
Create OAuth Desktop App credentials in Google Cloud Console and save as credentials.json.
"""
import os
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request

SCOPES=["https://www.googleapis.com/auth/calendar.events"]
credentials_path=Path(os.getenv("GOOGLE_CALENDAR_CREDENTIALS","credentials.json"))
token_path=Path(os.getenv("GOOGLE_CALENDAR_TOKEN","token.json"))
if not credentials_path.exists():
    raise SystemExit("Missing credentials.json. Create OAuth Client ID (Desktop app) in Google Cloud Console and download it to the project root.")
creds=None
if token_path.exists():
    creds=Credentials.from_authorized_user_file(str(token_path),SCOPES)
if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow=InstalledAppFlow.from_client_secrets_file(str(credentials_path),SCOPES)
        creds=flow.run_local_server(port=0)
    token_path.write_text(creds.to_json(),encoding="utf-8")
print(f"Google Calendar authorization saved to {token_path}. Keep this file private and out of GitHub.")
