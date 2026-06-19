from fastapi import FastAPI
from pydantic import BaseModel
import psycopg2
import os

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")

class LicenseRequest(BaseModel):
    license_key: str
    account: str


def get_db():
    return psycopg2.connect(DATABASE_URL)


@app.get("/")
def home():
    return {"status": "ok"}


@app.post("/validate")
def validate_license(req: LicenseRequest):
    conn = get_db()
    cur = conn.cursor()

    # Check license
    cur.execute("""
        SELECT max_accounts, expires_at, status
        FROM licenses
        WHERE license_key = %s
    """, (req.license_key,))

    license_data = cur.fetchone()

    if not license_data:
        return {"status": "invalid"}

    max_accounts, expires_at, status = license_data

    if status != "active":
        return {"status": "suspended"}

    if expires_at and expires_at < '2026-01-01':
        return {"status": "expired"}

    # Check linked accounts
    cur.execute("""
        SELECT COUNT(*)
        FROM license_accounts
        WHERE license_key = %s
    """, (req.license_key,))

    count = cur.fetchone()[0]

    # Check if account already exists
    cur.execute("""
        SELECT 1
        FROM license_accounts
        WHERE license_key = %s AND account = %s
    """, (req.license_key, req.account))

    exists = cur.fetchone()

    if not exists:
        if count >= max_accounts:
            return {"status": "max_accounts_reached"}

        cur.execute("""
            INSERT INTO license_accounts (license_key, account)
            VALUES (%s, %s)
        """, (req.license_key, req.account))

        conn.commit()

    return {"status": "active"}
