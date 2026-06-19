from fastapi import FastAPI
from pydantic import BaseModel
import psycopg2
import os

app = FastAPI()

DATABASE_URL = os.getenv("DATABASE_URL")

def get_conn():
    return psycopg2.connect(DATABASE_URL)

class LicenseRequest(BaseModel):
    license_key: str
    account: str

@app.get("/")
def home():
    return {"status": "ok"}

@app.post("/validate")
def validate(data: LicenseRequest):

    conn = get_conn()
    cur = conn.cursor()

    try:
        cur.execute("""
            SELECT max_accounts, status
            FROM licenses
            WHERE license_key = %s
        """, (data.license_key,))

        lic = cur.fetchone()

        if not lic:
            return {"status": "invalid"}

        max_accounts, status = lic

        if status != "active":
            return {"status": "inactive"}

        cur.execute("""
            SELECT COUNT(*)
            FROM license_accounts
            WHERE license_key = %s
        """, (data.license_key,))

        count = cur.fetchone()[0]

        cur.execute("""
            SELECT 1
            FROM license_accounts
            WHERE license_key = %s AND account = %s
        """, (data.license_key, data.account))

        exists = cur.fetchone()

        if not exists:
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
