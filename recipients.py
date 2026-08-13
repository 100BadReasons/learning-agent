"""
Extra email recipients.

The primary recipient (NOTIFY_EMAIL) gets the full brief, glossary included.
Everyone added here gets a RESEARCH-ONLY edition: the two research sections
and the site link, with no term lessons and no cross-links. Adding a
colleague therefore can never forward internal terminology.

The list lives in recipients.json, which is gitignored and loaded at runtime
from the RECIPIENTS_JSON secret — same pattern as the glossary. Email
addresses are personal data and this repo is public, so the list must never
be committed.

Usage:
  python recipients.py list
  python recipients.py add someone@example.com
  python recipients.py remove someone@example.com
  python recipients.py push          # sync the list to the GitHub secret
"""

import json
import os
import re
import subprocess
import sys

import config

RECIPIENTS_FILE = os.path.join(config.ROOT, "recipients.json")
REPO = "100BadReasons/learning-agent"

# Deliberately loose. The authority on whether an address is deliverable is
# the mail server, not a regex; this only catches typos like a missing @.
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def load():
    """Research-only recipients. Missing file means none, which is normal."""
    if not os.path.exists(RECIPIENTS_FILE):
        return []
    with open(RECIPIENTS_FILE) as f:
        data = json.load(f)
    # Tolerate a bare list or a wrapped object, so hand-editing the file the
    # obvious way doesn't break the run.
    if isinstance(data, dict):
        data = data.get("recipients", [])
    return [str(e).strip() for e in data if str(e).strip()]


def save(emails):
    with open(RECIPIENTS_FILE, "w") as f:
        json.dump(sorted(set(emails)), f, indent=2)
        f.write("\n")


def add(email):
    email = email.strip()
    if not EMAIL_RE.match(email):
        sys.exit(f"'{email}' doesn't look like an email address.")
    if email.lower() == config.NOTIFY_EMAIL.lower():
        sys.exit(f"{email} is already the primary recipient — it would get two "
                 f"copies. The primary is set by the NOTIFY_EMAIL secret.")
    emails = load()
    if email.lower() in {e.lower() for e in emails}:
        print(f"{email} is already on the list.")
        return emails
    emails.append(email)
    save(emails)
    print(f"Added {email}. {len(emails)} extra recipient(s).")
    return emails


def remove(email):
    emails = load()
    kept = [e for e in emails if e.lower() != email.strip().lower()]
    if len(kept) == len(emails):
        print(f"{email} wasn't on the list.")
        return emails
    save(kept)
    print(f"Removed {email}. {len(kept)} extra recipient(s).")
    return kept


def push():
    """Sync the local list into the RECIPIENTS_JSON secret.

    Secrets are write-only — there is no way to read the current value back —
    so the local file is the source of truth and this overwrites the secret
    with all of it. Always `list` before you `push`.
    """
    import base64
    emails = load()
    blob = base64.b64encode(json.dumps(emails).encode()).decode()
    result = subprocess.run(
        ["gh", "secret", "set", "RECIPIENTS_JSON", "--repo", REPO],
        input=blob, text=True,
    )
    if result.returncode != 0:
        sys.exit("Failed to set the secret — is `gh` authenticated?")
    print(f"Pushed {len(emails)} recipient(s) to the RECIPIENTS_JSON secret.")
    if not emails:
        print("Note: the list is empty, so only the primary recipient will be mailed.")


def main():
    args = sys.argv[1:]
    command = args[0] if args else "list"

    if command == "list":
        emails = load()
        print(f"Primary (full brief, glossary included): {config.NOTIFY_EMAIL}")
        if emails:
            print(f"Research-only ({len(emails)}):")
            for e in emails:
                print(f"  {e}")
        else:
            print("Research-only: none yet.")
    elif command == "add" and len(args) > 1:
        add(args[1])
        print("Run `python recipients.py push` to apply this to the daily run.")
    elif command == "remove" and len(args) > 1:
        remove(args[1])
        print("Run `python recipients.py push` to apply this to the daily run.")
    elif command == "push":
        push()
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
