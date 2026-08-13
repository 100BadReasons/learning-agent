"""
Sends the daily brief by email via the Gmail API.

Reuses the OAuth pattern and the token from bwr-pipeline unchanged. The
gmail.compose scope covers messages.send as well as drafts, so no new consent
is needed — but do not widen GMAIL_SCOPES in config.py, or the token stops
matching the requested scopes and Google forces a fresh browser flow that
cannot run in CI.

This stage fails LOUDLY on purpose. A brief that publishes but never reaches
you is the exact failure mode that let bwr-pipeline sit broken unnoticed: the
site looked fine, so nobody checked. A red X on the Actions run is the only
signal that the delivery half is down.
"""

import base64
import os
from email.mime.text import MIMEText

from google.auth.exceptions import RefreshError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials as UserCredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

import config
import render_email


def get_gmail_service():
    creds = None
    if os.path.exists(config.GMAIL_TOKEN_FILE):
        creds = UserCredentials.from_authorized_user_file(
            config.GMAIL_TOKEN_FILE, config.GMAIL_SCOPES)

    needs_save = False

    if creds and not creds.valid and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            needs_save = True
        except RefreshError as e:
            print(f"Gmail token could not be refreshed ({e}).")
            creds = None

    if not creds or not creds.valid:
        if os.environ.get("LEARNING_NON_INTERACTIVE"):
            # run_local_server() waits for a browser redirect that will never
            # come in CI — an invisible hang until the job timeout. Fail now.
            raise RuntimeError(
                "Gmail credentials are missing or unrefreshable, and the interactive "
                "OAuth flow cannot run unattended.\n"
                "Fix: run `python notify.py` locally to complete the browser flow, "
                "then refresh the secret with:\n"
                "  base64 -i gmail_token.json | gh secret set GMAIL_TOKEN_JSON "
                "--repo 100BadReasons/learning-agent\n"
                "If this recurs every ~7 days, the Google OAuth app is still in "
                "'Testing' status — publish it to 'In production' so refresh tokens "
                "stop expiring."
            )
        flow = InstalledAppFlow.from_client_secrets_file(
            config.GMAIL_CREDENTIALS_FILE, config.GMAIL_SCOPES)
        creds = flow.run_local_server(port=0)
        needs_save = True

    if needs_save:
        with open(config.GMAIL_TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def send(service, to_email, subject, html_body):
    message = MIMEText(html_body, "html")
    message["to"] = to_email
    message["subject"] = subject
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return service.users().messages().send(userId="me", body={"raw": raw}).execute()


def main():
    brief, private = render_email.latest_brief()
    body = render_email.build(brief, private)

    counts = brief.get("counts", {})
    total = counts.get("agentic", 0) + counts.get("banking", 0)
    if total:
        subject = f"Learning Brief — {brief['date']} ({total} new)"
    else:
        # Say so in the subject line rather than sending a cheerful header over
        # an empty page. A quiet day is information; a silent day is a bug.
        subject = f"Learning Brief — {brief['date']} (quiet day, terms only)"

    service = get_gmail_service()
    sent = send(service, config.NOTIFY_EMAIL, subject, body)
    print(f"[notify] sent to {config.NOTIFY_EMAIL} (message id {sent.get('id')}).")
    print(f"[notify] site: {config.SITE_URL}")


if __name__ == "__main__":
    main()
