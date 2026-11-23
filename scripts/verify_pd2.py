"""Run checks in a fresh PostgreSQL test database and save private evidence.

The application database is never selected as the test database. With Supabase's
session pooler, a released backend can remain connected, so only the database
created by this invocation is dropped with FORCE after Django closes its clients.
"""
import json
import argparse
import os
import secrets
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument("labels", nargs="*", default=["accounts", "core", "visits"])
parser.add_argument("--result-file", default="pd2-test-results.json")
args = parser.parse_args()
if Path(args.result_file).name != args.result_file:
    raise ValueError("Result filename must be a plain filename inside .local.")
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()
import psycopg
from psycopg import sql
from django.conf import settings

db = settings.DATABASES["default"]
test_name = "test_visita_pd2_" + secrets.token_hex(6)
assert test_name != db["NAME"] and test_name.startswith("test_visita_pd2_")
env = dict(os.environ, DB_TEST_NAME=test_name, PYTHONIOENCODING="utf-8")
out = ROOT / ".local"
out.mkdir(exist_ok=True)
results = []
with psycopg.connect(dbname=db["NAME"], user=db["USER"], password=db["PASSWORD"], host=db["HOST"], port=db["PORT"], sslmode=db["OPTIONS"]["sslmode"], autocommit=True) as control:
    if control.execute("SELECT 1 FROM pg_database WHERE datname=%s", [test_name]).fetchone():
        raise RuntimeError("Refusing to reuse an existing test database.")
    try:
        for command_args in [["check"], ["makemigrations", "--check", "--dry-run"], ["test", *args.labels, "--noinput", "--keepdb", "--verbosity", "1"]]:
            print("Running manage.py " + " ".join(command_args), flush=True)
            result = subprocess.run([sys.executable, "-B", "manage.py", *command_args], cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
            print(result.stdout, flush=True)
            results.append({"command": "manage.py " + " ".join(command_args), "returncode": result.returncode, "output": result.stdout})
            if result.returncode:
                break
    finally:
        # This target was generated and checked absent above; never drop a
        # configured application DB or an existing user-selected test DB.
        control.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(test_name)))
        (out / args.result_file).write_text(json.dumps({"date": datetime.now(timezone.utc).isoformat(), "database": test_name, "database_removed": True, "results": results}, indent=2), encoding="utf-8")
sys.exit(0 if len(results) == 3 and all(r["returncode"] == 0 for r in results) else 1)
