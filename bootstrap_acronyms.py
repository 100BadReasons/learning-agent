"""
One-time setup: turn Acronym_Soup.xlsx into acronyms.json, then into the
base64 blob that becomes the ACRONYMS_JSON GitHub Actions secret.

Run this again whenever you add terms to the spreadsheet — then update the
secret with the new blob.

  python bootstrap_acronyms.py ~/Downloads/Acronym_Soup.xlsx

Parses the .xlsx with stdlib zipfile + ElementTree rather than openpyxl: this
runs once on your Mac, never in CI, and doesn't justify a dependency the
pipeline would then carry forever.

The output file is gitignored. It must stay that way — this repo is public.
"""

import base64
import json
import os
import sys
import xml.etree.ElementTree as ET
import zipfile

import config

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


def read_xlsx_rows(path):
    z = zipfile.ZipFile(path)

    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        root = ET.fromstring(z.read("xl/sharedStrings.xml"))
        for si in root.findall(NS + "si"):
            shared.append("".join(t.text or "" for t in si.iter(NS + "t")))

    sheets = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet"))
    root = ET.fromstring(z.read(sheets[0]))

    rows = []
    for row in root.iter(NS + "row"):
        values = []
        for cell in row.findall(NS + "c"):
            kind, v = cell.get("t"), cell.find(NS + "v")
            if kind == "inlineStr":
                el = cell.find(NS + "is")
                text = "".join(x.text or "" for x in el.iter(NS + "t")) if el is not None else ""
            elif v is None:
                text = ""
            elif kind == "s":
                text = shared[int(v.text)]
            else:
                text = v.text or ""
            values.append(text)
        rows.append(values)
    return rows


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit("usage: python bootstrap_acronyms.py <Acronym_Soup.xlsx> [--print-secret]")

    # With --print-secret the blob is the ONLY thing on stdout, so the output
    # can be piped straight into `gh secret set` without the base64 ever
    # landing on disk. Commentary goes to stderr, where the pipe won't eat it.
    secret_mode = "--print-secret" in sys.argv
    log = (lambda *a: print(*a, file=sys.stderr)) if secret_mode else print

    rows = read_xlsx_rows(os.path.expanduser(args[0]))
    header, body = rows[0], rows[1:]
    log(f"Header row: {header}")

    terms = []
    for row in body:
        if len(row) < 2:
            continue
        acronym, definition = row[0].strip(), row[1].strip()
        if acronym and definition:
            terms.append({"acronym": acronym, "definition": definition})

    with open(config.ACRONYMS_FILE, "w") as f:
        json.dump(terms, f, indent=2, ensure_ascii=False)
        f.write("\n")

    blob = base64.b64encode(json.dumps(terms, ensure_ascii=False).encode()).decode()

    log(f"\nWrote {len(terms)} terms to {config.ACRONYMS_FILE} (gitignored).")
    log(f"At {config.TERMS_PER_DAY} terms/day that's a full pass every "
        f"{-(-len(terms) // config.TERMS_PER_DAY)} days.")
    log(f"Base64 blob is {len(blob)} bytes (GitHub's secret limit is 48KB).")

    if secret_mode:
        sys.stdout.write(blob)
    else:
        log("\nLoad it into the secret without the base64 ever touching disk:\n")
        log("  python bootstrap_acronyms.py ~/Downloads/Acronym_Soup.xlsx --print-secret \\")
        log("    | gh secret set ACRONYMS_JSON --repo 100BadReasons/learning-agent")


if __name__ == "__main__":
    main()
