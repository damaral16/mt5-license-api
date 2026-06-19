from fastapi import FastAPI
from pydantic import BaseModel
import psycopg2
import os

app = FastAPI()

# =========================
# DATABASE
# =========================

DATABASE_URL = os.getenv("DATABASE_URL")

def get_conn():
    if not DATABASE_URL:
        raise Exception("DATABASE_URL not set")

    return psycopg2.connect(DATABASE_URL)

# =========================
# REQUEST MODEL
# =========================

class LicenseRequest(BaseModel):
    license_key: str
    account: str

# =========================
# ROOT TEST
# =========================

@app.get("/")
def home():
    return {"status": "ok"}

# =========================
# VALIDATE LICENSE
# =========================

@app.post("/validate")
def validate(data: LicenseRequest):

    conn = get_conn()
    cur = conn.cursor()

    try:
        # 1. CHECK LICENSE
        cur.execute("""
            SELECT max_accounts, status
            FROM "Licences"
            WHERE license_key = %s
        """, (data.license_key,))

        license_row = cur.fetchone()

        if not license_row:
            return {"status": "invalid"}

        max_accounts, status = license_row

        if status != "active":
            return {"status": "inactive"}

        # 2. COUNT ACCOUNTS
        cur.execute("""
            SELECT COUNT(*)
            FROM "Licence_accounts"
            WHERE license_key = %s
        """, (data.license_key,))

        count = cur.fetchone()[0]

        # 3. CHECK IF ACCOUNT EXISTS
        cur.execute("""
            SELECT 1
            FROM "Licence_accounts"
            WHERE license_key = %s AND account = %s
        """, (data.license_key, data.account))

        exists = cur.fetchone()

        # 4. INSERT IF NEW
        if not exists:
            if count >= max_accounts:
                return {"status": "limit_reached"}

            cur.execute("""
                INSERT INTO "Licence_accounts" (license_key, account)
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
# DEBUG TABLES
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
