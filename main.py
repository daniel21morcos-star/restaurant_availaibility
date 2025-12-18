from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict
from datetime import datetime
from dateutil import parser
import os
import requests

app = FastAPI()

# --------------------
# CONFIG
# --------------------
TOTAL_SEATS = 66            # 76 total - 10 bar seats
MAX_PARTY_SIZE = 10

CAL_API_KEY = os.getenv("CAL_API_KEY")
CAL_BASE_URL = "https://api.cal.com/v2"

# --------------------
# IN-MEMORY STORAGE
# --------------------
# { "YYYY-MM-DD HH:MM": seats_reserved }
reservations: Dict[str, int] = {}

# --------------------
# HELPERS
# --------------------
def normalize_time(raw_time: str) -> str:
    """
    Accepts natural language time and normalizes it
    to YYYY-MM-DD HH:MM (24h)
    """
    try:
        dt = parser.parse(raw_time)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Could not understand the provided time."
        )


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
    "start": time,
    "responses": {
        "email": {
            "value": email
        },
        "partysize": {
            "value": int(party_size)
        }
    }
}


    response = requests.post(
        f"{CAL_BASE_URL}/bookings",
        json=payload,
        headers=headers,
        timeout=10
    )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=500,
            detail=f"Error calling Cal Booking API: {response.text}"
        )

    return response.json()

# --------------------
# MODELS
# --------------------
class AvailabilityResponse(BaseModel):
    time: str
    remaining_seats: int


class ReservationRequest(BaseModel):
    time: str
    party_size: str   # comes from Retell as string
    email: str

# --------------------
# ROUTES
# --------------------
@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/availability", response_model=AvailabilityResponse)
def get_availability(time: str):
    normalized_time = normalize_time(time)

    reserved = reservations.get(normalized_time, 0)
    remaining = TOTAL_SEATS - reserved

    return {
        "time": normalized_time,
        "remaining_seats": max(remaining, 0)
    }


@app.post("/reserve")
def reserve_table(request: ReservationRequest):
    # Convert party size safely
    try:
        party_size = int(request.party_size)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Invalid party size."
        )

    if party_size <= 0:
        raise HTTPException(
            status_code=400,
            detail="Invalid party size."
        )

    if party_size > MAX_PARTY_SIZE:
        raise HTTPException(
            status_code=400,
            detail="Party size exceeds maximum. Call transfer required."
        )

    normalized_time = normalize_time(request.time)

    reserved = reservations.get(normalized_time, 0)
    remaining = TOTAL_SEATS - reserved

    if party_size > remaining:
        raise HTTPException(
            status_code=400,
            detail="Not enough seats available for this time."
        )

    # ---- CREATE CAL.COM BOOKING ----
    create_cal_booking(
        time=normalized_time,
        party_size=party_size,
        email=request.email
    )

    # ---- UPDATE LOCAL AVAILABILITY ----
    reservations[normalized_time] = reserved + party_size

    return {
        "message": "Reservation confirmed",
        "time": normalized_time,
        "party_size": party_size,
        "remaining_seats": TOTAL_SEATS - reservations[normalized_time]
    }


