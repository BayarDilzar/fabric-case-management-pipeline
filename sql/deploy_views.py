"""Deploys the views in sql/reporting/ to the SQL analytics endpoint of a lakehouse.

Usage: python sql/deploy_views.py <workspace name> [<lakehouse name>, default lh_gold]

Needs an Azure CLI sign-in (az login) and the mssql-python package. The endpoint is looked up by name
through the Fabric API, so no server name or ID is kept in the repo. Each file holds one
CREATE OR ALTER VIEW statement for the view named after the file.
"""

import json
import re
import struct
import subprocess
import sys
import urllib.request
from pathlib import Path

FOLDER = Path(__file__).parent / "reporting"
API = "https://api.fabric.microsoft.com/v1"
# The connection attribute that takes an Entra access token instead of a password.
SQL_COPT_SS_ACCESS_TOKEN = 1256


def view_name(sql):
    """The view a file creates, from its CREATE OR ALTER VIEW line."""
    match = re.search(r"^CREATE OR ALTER VIEW (reporting\.\w+) AS$", sql, re.MULTILINE)
    return match.group(1) if match else None


def view_files():
    files = sorted(FOLDER.glob("*.sql"))
    for path in files:
        if view_name(path.read_text(encoding="utf-8")) != f"reporting.{path.stem}":
            raise ValueError(f"{path.name} must create the view reporting.{path.stem}")
    return files


def token(resource):
    return subprocess.run(["az", "account", "get-access-token", "--resource", resource, "--query", "accessToken", "-o", "tsv"],
                          capture_output=True, text=True, check=True, shell=sys.platform == "win32").stdout.strip()


def find(url, bearer, name):
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {bearer}"})
    with urllib.request.urlopen(request, timeout=60) as response:
        items = json.load(response)["value"]
    matches = [item for item in items if item["displayName"] == name]
    if len(matches) != 1:
        raise ValueError(f"expected one item named {name}, found {len(matches)}")
    return matches[0]


def connect(workspace, lakehouse):
    fabric = token("https://api.fabric.microsoft.com")
    workspace_id = find(f"{API}/workspaces", fabric, workspace)["id"]
    lakehouse_id = find(f"{API}/workspaces/{workspace_id}/lakehouses", fabric, lakehouse)["id"]
    request = urllib.request.Request(f"{API}/workspaces/{workspace_id}/lakehouses/{lakehouse_id}",
                                     headers={"Authorization": f"Bearer {fabric}"})
    with urllib.request.urlopen(request, timeout=60) as response:
        server = json.load(response)["properties"]["sqlEndpointProperties"]["connectionString"]

    import mssql_python  # imported here so the tests can load this file without the driver

    sql_token = token("https://database.windows.net/").encode("utf-16-le")
    return mssql_python.connect(f"Server={server},1433;Database={lakehouse};Encrypt=yes;",
                                attrs_before={SQL_COPT_SS_ACCESS_TOKEN: struct.pack(f"<I{len(sql_token)}s", len(sql_token), sql_token)},
                                autocommit=True)


def main(workspace, lakehouse="lh_gold"):
    files = view_files()
    connection = connect(workspace, lakehouse)
    cursor = connection.cursor()
    cursor.execute("IF SCHEMA_ID('reporting') IS NULL EXEC('CREATE SCHEMA reporting')")
    for path in files:
        cursor.execute(path.read_text(encoding="utf-8"))
        print(f"deployed reporting.{path.stem}")
    cursor.execute("SELECT name FROM sys.views WHERE schema_id = SCHEMA_ID('reporting') ORDER BY name")
    print("views in reporting:", ", ".join(row[0] for row in cursor.fetchall()))
    connection.close()


if __name__ == "__main__":
    if not 2 <= len(sys.argv) <= 3:
        sys.exit(__doc__)
    main(*sys.argv[1:])
