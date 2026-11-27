# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {
# META     "lakehouse": {
# META       "default_lakehouse": "381f57db-79ac-4c76-8ad3-61256c09907f",
# META       "default_lakehouse_name": "lh_bronze",
# META       "default_lakehouse_workspace_id": "79583ae2-ec4b-440f-a2e1-673ae384a224"
# META     }
# META   }
# META }

# CELL ********************

import hashlib
import json
import os
import tempfile
import urllib.request

import notebookutils

# One entry per public file. Each release has its own folder under Files/public/<source>/, so a landed
# file is never replaced: a publisher's new file needs a new release folder here.
SOURCES = [
    {"source": "deprivation_lad", "release": "2025-11-17",
     "url": "https://assets.publishing.service.gov.uk/media/6917412ebc34c86ce4e6e7fc/File_10_-_IoD2025_Local_Authority_District_Summaries__lower-tier__v2.xlsx",
     "file": "File_10_-_IoD2025_Local_Authority_District_Summaries__lower-tier__v2.xlsx"},
    # The ONS link points at "current", so after the next release it serves a different file. The sha256
    # check below then stops the run instead of loading the new file under this release.
    {"source": "drug_poisoning_deaths_lad", "release": "2026-11-04",
     "url": "https://www.ons.gov.uk/file?uri=/peoplepopulationandcommunity/birthsdeathsandmarriages/deaths/datasets/drugmisusedeathsbylocalauthority/current/2025localauthorities.xlsx",
     "file": "2025localauthorities.xlsx"},
    {"source": "local_authority", "release": "2024-11-28",
     "url": "https://geoportal.statistics.gov.uk/api/download/v1/items/3959874c514b470e9dd160acdc00c97a/csv?layers=0",
     "file": "Local_Authority_District_to_Region_(December_2024)_Lookup_in_EN.csv"},
]


def download(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; data-loader)"})
    with urllib.request.urlopen(request, timeout=300) as response:
        return response.read()


def landed_bytes(path):
    """The file already landed at path, or None. Copied to a local temp file, because Files has no local mount here."""
    if not notebookutils.fs.exists(path):
        return None
    local = os.path.join(tempfile.mkdtemp(), "landed")
    notebookutils.fs.cp(path, "file:" + local)
    with open(local, "rb") as f:
        return f.read()

# CELL ********************

# Every file is downloaded and checked before any is written, so a failed check leaves Landing as it was.
checked = []
for s in SOURCES:
    body = download(s["url"])
    # An error page can come back with status 200; an Excel file is a zip, which starts with PK.
    if s["file"].endswith(".xlsx") and not body.startswith(b"PK"):
        raise ValueError(f"{s['url']} did not return an Excel file. It starts with {body[:60]!r}.")
    path = f"Files/public/{s['source']}/{s['release']}/{s['file']}"
    sha256 = hashlib.sha256(body).hexdigest()
    old = landed_bytes(path)
    if old is not None and hashlib.sha256(old).hexdigest() != sha256:
        raise ValueError(f"{path} is landed with sha256 {hashlib.sha256(old).hexdigest()}, but the file downloaded now "
                         f"for the same release has sha256 {sha256}. A changed file needs a new release folder. "
                         "Nothing was written.")
    checked.append((s, path, body, sha256, old is None))

landed = []
for s, path, body, sha256, is_new in checked:
    if is_new:
        local = os.path.join(tempfile.mkdtemp(), s["file"])
        with open(local, "wb") as f:
            f.write(body)
        notebookutils.fs.cp("file:" + local, path)
    print(f"{path}: {len(body)} bytes, sha256 {sha256}, {'landed' if is_new else 'already landed and unchanged'}")
    landed.append({"source": s["source"], "release": s["release"], "file": path, "url": s["url"], "sha256": sha256})

# nb_load_public_data takes this list as its landed parameter.
notebookutils.notebook.exit(json.dumps(landed))
