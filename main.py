from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
from dateutil import parser
import sqlite3
import os
import requests

app = FastAPI()

# ======================================================
# CONFIG
# ======================================================
TOTAL_SEATS = 66
MAX_PARTY_SIZE = 10

CAL_API_KEY = os.getenv("CAL_API_KEY")
CAL_BASE_URL = "https://api.cal.com/v2"

DB_PATH = "reservations.db"

# ======================================================
# DATABASE
# ======================================================
def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS reservations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            time TEXT NOT NULL,
            party_size INTEGER NOT NULL,
            email TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ======================================================
# HELPERS
# ======================================================
def normalize_time(raw_time: str) -> str:
    try:
        dt = parser.parse(raw_time)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Could not understand the provided time."
        )

def get_reserved_seats(time: str) -> int:
    conn = get_db()
    cursor = conn.execute(
        "SELECT COALESCE(SUM(party_size), 0) FROM reservations WHERE time = ?",
        (time,)
    )
    reserved = cursor.fetchone()[0]
    conn.close()
    return reserved

# ======================================================
# CAL.COM INTEGRATION (FULLY LOGGED)
# ======================================================
def create_cal_booking(time: str, party_size: int, email: str):
    if not CAL_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Cal.com API key not configured."
        )

    headers = {
        "Authorization": f"Bearer {CAL_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
    "eventTypeId": 4165145,  # ← REPLACE WITH YOUR REAL ID
    "start": time,
    "responses": {
        "email": {
            "value": email
        },
        "guests": {          # ← your correct identifier
            "value": int(party_size)
        }
    }
}

    # 🔍 LOG EXACT PAYLOAD
    print("==== CAL PAYLOAD SENT ====")
    print(payload)

    response = requests.post(
        f"{CAL_BASE_URL}/bookings",
        headers=headers,
        json=payload,
        timeout=15
    )

    # 🔍 LOG EXACT RESPONSE
    print("==== CAL RESPONSE ====")
    print(response.status_code)
    print(response.text)

    if response.status_code >= 400:
        raise HTTPException(
            status_code=500,
            detail=f"Error calling Cal Booking API: {response.text}"
        )

    return response.json()

# ======================================================
# MODELS
# ======================================================
class AvailabilityResponse(BaseModel):
    time: str
    remaining_seats: int

class ReservationRequest(BaseModel):
    time: str
    party_size: str  # comes from Retell as string
    email: str

# ======================================================
# ROUTES
# ======================================================
@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/availability", response_model=AvailabilityResponse)
def availability(time: str):
    normalized_time = normalize_time(time)
    reserved = get_reserved_seats(normalized_time)
    remaining = TOTAL_SEATS - reserved

    return {
        "time": normalized_time,
        "remaining_seats": max(remaining, 0)
    }

@app.post("/reserve")
def reserve(request: ReservationRequest):
    # Convert party size
    try:
        party_size = int(request.party_size)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid party size.")

    if party_size <= 0:
        raise HTTPException(status_code=400, detail="Invalid party size.")

    if party_size > MAX_PARTY_SIZE:
        raise HTTPException(
            status_code=400,
            detail="Party size exceeds maximum. Call transfer required."
        )

    normalized_time = normalize_time(request.time)

    reserved = get_reserved_seats(normalized_time)
    remaining = TOTAL_SEATS - reserved

    if party_size > remaining:
        raise HTTPException(
            status_code=400,
            detail="Not enough seats available."
        )

    # ==================================================
    # CREATE CAL.COM BOOKING (FIRST)
    # ==================================================
    create_cal_booking(
        time=normalized_time,
        party_size=party_size,
        email=request.email
    )

    # ==================================================
    # PERSIST LOCALLY
    # ==================================================
    conn = get_db()
    conn.execute(
        """
        INSERT INTO reservations (time, party_size, email, created_at)
        VALUES (?, ?, ?, ?)
        """,
        (
            normalized_time,
            party_size,
            request.email,
            datetime.utcnow().isoformat()
        )
    )
    conn.commit()
    conn.close()

    return {
        "message": "Reservation confirmed",
        "time": normalized_time,
        "party_size": party_size,
        "remaining_seats": TOTAL_SEATS - (reserved + party_size)
    }

