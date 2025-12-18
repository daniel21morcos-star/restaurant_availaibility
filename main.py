from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict

app = FastAPI()

# ---- CONSTANTS ----
TOTAL_SEATS = 66          # 76 total - 10 bar seats
MAX_PARTY_SIZE = 10

# ---- IN-MEMORY STORAGE (can be replaced by Cal.com later) ----
# Example structure:
# {
#   "2025-01-20 19:00": 24,   # seats already reserved
# }
reservations: Dict[str, int] = {}


# ---- MODELS ----
class AvailabilityResponse(BaseModel):
    time: str
    remaining_seats: int


class ReservationRequest(BaseModel):
    time: str
    party_size: int
    email: str


# ---- ENDPOINTS ----

@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/availability", response_model=AvailabilityResponse)
def get_availability(time: str):
    reserved = reservations.get(time, 0)
    remaining = TOTAL_SEATS - reserved

    return {
        "time": time,
        "remaining_seats": max(remaining, 0)
    }


@app.post("/reserve")
def reserve_table(request: ReservationRequest):
    # Party size rules
    if request.party_size > MAX_PARTY_SIZE:
        raise HTTPException(
            status_code=400,
            detail="Party size exceeds maximum. Call transfer required."
        )

    if request.party_size <= 0:
        raise HTTPException(
            status_code=400,
            detail="Invalid party size."
        )

    reserved = reservations.get(request.time, 0)
    remaining = TOTAL_SEATS - reserved

    if request.party_size > remaining:
        raise HTTPException(
            status_code=400,
            detail="Not enough seats available for this time."
        )

    # Reserve seats
    reservations[request.time] = reserved + request.party_size

    return {
        "message": "Reservation confirmed",
        "time": request.time,
        "party_size": request.party_size,
        "remaining_seats": TOTAL_SEATS - reservations[request.time]
    }
