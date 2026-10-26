"""Create a demo project with 100 synthetic interns, tasks, and assignments.

Safety: the workbook uses example.com addresses. This script refuses to run when
SMTP_HOST is configured so demo notifications are not sent externally.
Run from the project root after starting the backend and keeping SMTP unset.
"""
import argparse
import csv
import json
import os
import secrets
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
API = os.getenv("INTERNMIND_API", "http://127.0.0.1:8000")


def read_env_value(name):
    env_path = ROOT / ".env"
    if not env_path.exists():
        return ""
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and line.startswith(name + "="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def request(path, token=None, method="GET", data=None, content_type="application/json"):
    body = None if data is None else (data if isinstance(data, bytes) else json.dumps(data).encode())
    headers = {"Content-Type": content_type}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {path} failed ({e.code}): {detail}") from e


def upload_csv(path, token, file_path):
    boundary = "----InternMindBoundary" + secrets.token_hex(12)
    payload = file_path.read_bytes()
    filename = file_path.name
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        "Content-Type: text/csv\r\n\r\n"
    ).encode() + payload + f"\r\n--{boundary}--\r\n".encode()
    return request(path, token, "POST", body, f"multipart/form-data; boundary={boundary}")


def main():
    parser = argparse.ArgumentParser(description="Seed InternMind with 100 synthetic demo candidates and tasks")
    parser.add_argument("--email", default="admin@example.com")
    parser.add_argument("--password", default="ChangeThisPassword123!")
    parser.add_argument("--project-name", default="InternMind AI — 100 Intern Demo")
    args = parser.parse_args()

    smtp_host = read_env_value("SMTP_HOST")
    if smtp_host:
        raise SystemExit("Safety stop: SMTP_HOST is configured in .env. These demo emails use example.com. Clear SMTP_HOST before seeding demo data.")

    candidate_file = ROOT / "data" / "candidates_import.csv"
    task_file = ROOT / "data" / "tasks_assignments.csv"
    if not candidate_file.exists() or not task_file.exists():
        raise SystemExit("Missing demo CSV files in data/.")

    print("This creates a new demo project, 100 synthetic intern records, 100 tasks, and assignments.")
    print("All emails use example.com; email notifications will be previewed in the backend terminal, not sent.")
    if input("Type CREATE DEMO to continue: ").strip() != "CREATE DEMO":
        raise SystemExit("Cancelled.")

    auth = request("/auth/login", method="POST", data={"email": args.email, "password": args.password})
    token = auth["access_token"]
    project = request("/projects", token, "POST", {
        "name": args.project_name,
        "client_name": "Thozhil",
        "description": "Demo project with 100 synthetic candidate records and task work packages."
    })
    pid = project["id"]
    print(f"Created project ID {pid}.")

    imported = upload_csv(f"/projects/{pid}/interns/import", token, candidate_file)
    print(f"Intern import: {len(imported.get('created', []))} created; {len(imported.get('skipped', []))} skipped.")
    intern_rows = request(f"/projects/{pid}/interns", token)
    by_email = {row["email"].lower(): row for row in intern_rows}

    with task_file.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    made = 0
    skipped = 0
    for row in rows:
        email = row["candidate_email"].strip().lower()
        intern = by_email.get(email)
        if not intern:
            print(f"SKIP {row['task_id']}: intern not found for {email}")
            skipped += 1
            continue
        task = request(f"/projects/{pid}/tasks", token, "POST", {
            "title": row["title"],
            "description": row["description"],
            "acceptance_criteria": [x.strip() for x in row["acceptance_criteria"].split(";") if x.strip()],
            "requirement_codes": [],
            "depends_on_task_ids": []
        })
        request(f"/tasks/{task['id']}/assign", token, "POST", {
            "intern_id": intern["id"],
            "due_at": row["due_at"],
            "review_at": row["review_at"],
            "meet_url": ""
        })
        made += 1
        if made % 10 == 0:
            print(f"Created and assigned {made}/{len(rows)} tasks...")

    print("\nDemo seed complete.")
    print(f"Project ID: {pid}")
    print(f"Tasks assigned: {made}; skipped: {skipped}")
    print("Review links are not real Google Meet links; configure Calendar OAuth separately.")
    print("Next: open the frontend, select this project, and test the AI Interviews page.")


if __name__ == "__main__":
    main()
