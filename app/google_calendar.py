"""Optional Google Calendar/Meet integration for autonomous task reviews.

OAuth is authorized once by scripts/google_calendar_setup.py. Never commit token.json
or credentials.json. Calendar API creates the event and conference link; it does not
join an AI bot to the call.
"""
import os
from datetime import datetime
from pathlib import Path

def create_meet_event(summary: str, description: str, attendee_email: str,
                      start_at: datetime, end_at: datetime,
                      timezone_name: str = "Asia/Kolkata") -> str | None:
    if os.getenv("GOOGLE_CALENDAR_ENABLED", "false").lower() != "true":
        return None
    credentials_path=Path(os.getenv("GOOGLE_CALENDAR_CREDENTIALS", "credentials.json"))
    token_path=Path(os.getenv("GOOGLE_CALENDAR_TOKEN", "token.json"))
    if not credentials_path.exists() or not token_path.exists():
        return None
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    creds=Credentials.from_authorized_user_file(str(token_path), ["https://www.googleapis.com/auth/calendar.events"])
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_path.write_text(creds.to_json(),encoding="utf-8")
    service=build("calendar","v3",credentials=creds,cache_discovery=False)
    event={
        "summary":summary,
        "description":description,
        "start":{"dateTime":start_at.isoformat(),"timeZone":timezone_name},
        "end":{"dateTime":end_at.isoformat(),"timeZone":timezone_name},
        "attendees":[{"email":attendee_email}],
        "conferenceData":{"createRequest":{"requestId":os.urandom(12).hex(),"conferenceSolutionKey":{"type":"hangoutsMeet"}}},
        "reminders":{"useDefault":True},
    }
    created=service.events().insert(calendarId=os.getenv("GOOGLE_CALENDAR_ID","primary"),body=event,conferenceDataVersion=1,sendUpdates="all").execute()
    return created.get("hangoutLink") or created.get("conferenceData",{}).get("entryPoints",[{}])[0].get("uri")
