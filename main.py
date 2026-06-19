from fastapi import FastAPI
from pydantic import BaseModel
import psycopg2
import os

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")


class LicenseRequest(BaseModel):
    license_key: str
    account: str


def get_conn():
    return psycopg2.connect(DATABASE_URL, sslmode="require")


@app.get("/")
def home():
    return {"status": "ok"}


@app.post("/validate")
def validate(req: LicenseRequest):

    conn = get_conn()
    cur = conn.cursor()

    try:
        # 1. check license
        cur.execute("""
            SELECT max_accounts, status, expires_at
            FROM licenses
            WHERE license_key = %s
        """, (req.license_key,))

        data = cur.fetchone()

        if not data:
            return {"status": "invalid"}

        max_accounts, status, expires_at = data

        if status != "active":
            return {"status": "suspended"}

        # 2. check expiration
        if expires_at and str(expires_at) < "2026-01-01":
            return {"status": "expired"}

        # 3. check accounts
        cur.execute("""
            SELECT COUNT(*)
            FROM license_accounts
            WHERE license_key = %s
        """, (req.license_key,))

        count = cur.fetchone()[0]

        # 4. check if account exists
        cur.execute("""
            SELECT 1
            FROM license_accounts
            WHERE license_key = %s AND account = %s
        """, (req.license_key, req.account))

        exists = cur.fetchone()

        # 5. register account if new
        if not exists:
            if count >= max_accounts:
                return {"status": "max_accounts_reached"}

            cur.execute("""
                INSERT INTO license_accounts (license_key, account)
                VALUES (%s, %s)
            """, (req.license_key, req.account))

            conn.commit()

        return {"status": "active"}

    except Exception as e:
        return {"status": "error", "detail": str(e)}

    finally:
        conn.close()
