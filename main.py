from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
import httpx
import os

app = FastAPI()

git init
 = os.getenv("cal_live_652fd485631163ae724f1621c62f2335")

TOTAL_CAPACITY = 76
MAX_BOOKABLE = 72
TIME_WINDOW_MINUTES = 90


class AvailabilityRequest(BaseModel):
    date: str
    time: str
    requestedPartySize: int


class AvailabilityResponse(BaseModel):
    totalCapacity: int
    bookedSeats: int
    remainingSeats: int
    canAccept: bool


def within_time_window(booking_time, target_time):
    delta = abs((booking_time - target_time).total_seconds())
    return delta <= TIME_WINDOW_MINUTES * 60


@app.post("/check-availability", response_model=AvailabilityResponse)
async def check_availability(req: AvailabilityRequest):
    if not CAL_API_KEY:
        raise HTTPException(status_code=500, detail="Missing Cal API key")

    if req.requestedPartySize < 1 or req.requestedPartySize > TOTAL_CAPACITY:
        return AvailabilityResponse(
            totalCapacity=TOTAL_CAPACITY,
            bookedSeats=0,
            remainingSeats=0,
            canAccept=False
        )

    target_time = datetime.fromisoformat(f"{req.date}T{req.time}")

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "https://api.cal.com/v1/bookings",
            headers={"Authorization": f"Bearer {CAL_API_KEY}"},
            params={"date": req.date}
        )

    if response.status_code != 200:
        raise HTTPException(status_code=500, detail="Cal.com API error")

    bookings = response.json().get("bookings", [])
    booked_seats = 0

    for booking in bookings:
        start_time = datetime.fromisoformat(booking["startTime"])
        if within_time_window(start_time, target_time):
            booked_seats += booking.get("responses", {}).get("partySize", 0)

    remaining = max(0, MAX_BOOKABLE - booked_seats)

    return AvailabilityResponse(
        totalCapacity=TOTAL_CAPACITY,
        bookedSeats=booked_seats,
        remainingSeats=remaining,
        canAccept=remaining >= req.requestedPartySize
    )

