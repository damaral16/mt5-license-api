from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import psycopg2
import os

app = FastAPI()

# =========================
# DATABASE CONNECTION
# =========================

DATABASE_URL = os.getenv("DATABASE_URL")

def get_conn():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL not set")

    return psycopg2.connect(DATABASE_URL)

# =========================
# MODELS
# =========================

class LicenseRequest(BaseModel):
    license_key: str
    account: str

# =========================
# HEALTH CHECK
# =========================

@app.get("/")
def home():
    return {"status": "ok"}

# =========================
# VALIDATE LICENSE
# =========================

@app.post("/validate")
def validate_license(data: LicenseRequest):

    conn = get_conn()
    cur = conn.cursor()

    try:
        # 1. check license
        cur.execute("""
            SELECT max_accounts, status
            FROM licenses
            WHERE license_key = %s
        """, (data.license_key,))

        license_row = cur.fetchone()

        if not license_row:
            return {"status": "invalid"}

        max_accounts, status = license_row

        if status != "active":
            return {"status": "inactive"}

        # 2. check accounts already linked
        cur.execute("""
            SELECT COUNT(*)
            FROM license_accounts
            WHERE license_key = %s
        """, (data.license_key,))

        count = cur.fetchone()[0]

        # 3. check if account already exists
        cur.execute("""
            SELECT 1
            FROM license_accounts
            WHERE license_key = %s AND account = %s
        """, (data.license_key, data.account))

        already_linked = cur.fetchone()

        if not already_linked:
            if count >= max_accounts:
                return {"status": "limit_reached"}

            cur.execute("""
                INSERT INTO license_accounts (license_key, account)
                VALUES (%s, %s)
            """, (data.license_key, data.account))

            conn.commit()

        return {"status": "active"}

    except Exception as e:
        conn.rollback()
        return {"status": "error", "detail": str(e)}

    finally:
        cur.close()
        conn.close()

# =========================
# DEBUG ROUTE (IMPORTANT)
# =========================

@app.get("/debug")
def debug():

    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT table_schema, table_name
        FROM information_schema.tables
        ORDER BY table_schema, table_name;
    """)

    tables = cur.fetchall()

    cur.close()
    conn.close()

    return {"tables": tables}
