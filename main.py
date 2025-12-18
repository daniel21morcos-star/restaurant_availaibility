from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict
from datetime import datetime

app = FastAPI()

# ---- CONSTANTS ----
TOTAL_SEATS = 66
MAX_PARTY_SIZE = 10

# ---- IN-MEMORY STORAGE ----
reservations: Dict[str, int] = {}

from dateutil import parser
def normalize_time(raw_time: str) -> str:
    try:
        dt = parser.parse(raw_time)
        return dt.strftime("%Y-%m-%d %H:%M")
    except Exception:
        raise HTTPException(
            status_code=400,
            detail="Could not understand the provided time."
        )



# ---- MODELS ----
class AvailabilityResponse(BaseModel):
    time: str
    remaining_seats: int


class ReservationRequest(BaseModel):
    time: str
    party_size: str
    email: str


# ---- ROUTES ----

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
    try:
        party_size = int(party_size)
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

    reserved = reservations.get(normalized_time, 0)
    remaining = TOTAL_SEATS - reserved

    if party_size > remaining:
        raise HTTPException(
            status_code=400,
            detail="Not enough seats available for this time."
        )

    reservations[normalized_time] = reserved + party_size

    return {
        "message": "Reservation confirmed",
        "time": normalized_time,
        "party_size": party_size,
        "remaining_seats": TOTAL_SEATS - reservations[normalized_time]
    }

