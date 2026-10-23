from dotenv import load_dotenv
from fastapi import Header, HTTPException, Query
import os

load_dotenv()

ADMIN_KEY = os.getenv("ADMIN_KEY")


def verify_api_key(
    x_api_key: str | None = Header(default=None),
    api_key: str | None = Query(default=None)
):
    # Check Header first, otherwise fallback to Query parameter
    key = x_api_key or api_key

    if key != ADMIN_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API Key"
        )

    return key


'''
The Real-World Backend Solution:
Update verify_api_key so it accepts x-api-key from the Header (for all your existing routes) OR 
from a Query Parameter (?api_key=...) for the SSE stream.

'''
