from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
from dateutil import parser
import sqlite3
import os
import requests

app = FastAPI()
print("🚨 USING NEW BACKEND WITHOUT PARTY SIZE 🚨")
from time import time

LAST_BOOKING_TIME = {}

# ==============================
# CONFIG
# ==============================
TOTAL_SEATS = 66
MAX_PARTY_SIZE = 10

CAL_API_KEY = os.getenv("CAL_API_KEY")
CAL_BASE_URL = "https://api.cal.com/v2"
EVENT_TYPE_ID = int(os.getenv("CAL_EVENT_TYPE_ID", "0"))

DB_PATH = "reservations.db"

# ==============================
# DATABASE
# ==============================
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

# ==============================
# HELPERS
# ==============================
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

# ==============================
# CAL.COM (CORRECT USAGE)
# ==============================
def create_cal_booking(time: str, email: str):
    if not CAL_API_KEY or EVENT_TYPE_ID == 0:
        raise HTTPException(
            status_code=500,
            detail="Cal.com configuration missing."
        )

    headers = {
        "Authorization": f"Bearer {CAL_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "eventTypeId": EVENT_TYPE_ID,
        "start": time,
        "responses": {
            "email": {
                "value": email
            }
        }
    }

    response = requests.post(
        f"{CAL_BASE_URL}/bookings",
        json=payload,
        headers=headers,
        timeout=15
    )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=500,
            detail=f"Error calling Cal Booking API: {response.text}"
        )

    return response.json()

# ==============================
# MODELS
# ==============================
class AvailabilityResponse(BaseModel):
    time: str
    remaining_seats: int

class ReservationRequest(BaseModel):
    time: str
    party_size: str  # comes from voice as string
    email: str

# ==============================
# ROUTES
# ==============================
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
now = time()
last = LAST_BOOKING_TIME.get(request.email)

if last and now - last < 30:
    raise HTTPException(
        status_code=429,
        detail="Please wait a moment before making another reservation."
    )

LAST_BOOKING_TIME[request.email] = now

    normalized_time = normalize_time(request.time)

    reserved = get_reserved_seats(normalized_time)
    remaining = TOTAL_SEATS - reserved

    if party_size > remaining:
        raise HTTPException(
            status_code=400,
            detail="Not enough seats available."
        )

    # ---- CREATE CAL BOOKING (NO PARTY SIZE) ----
    create_cal_booking(
        time=normalized_time,
        email=request.email
    )

    # ---- SAVE LOCALLY ----
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


