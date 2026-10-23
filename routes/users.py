from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from src.database import get_session
from src.auth import verify_api_key
from models.user import *

from fastapi.responses import StreamingResponse
import asyncio
from src.sse import sse_manager


router = APIRouter(prefix="/admin", tags=["Admin Dashboard"])


# SSE endpoint for user form submissions

@router.post(
    "/sse/user/submit",
    response_model=UserResponseModel,
    description="Submit a new user form.",
    response_description="Returns a success message upon successful form submission.",
    tags=["User Form Submission"]
)
async def submit_form_sse(
    user_data: UserRequestModel,
    session: Session = Depends(get_session)
):
    new_user = UserTable.model_validate(user_data)
    session.add(new_user)
    session.commit()
    # Loads auto-generated id & created_at from SQLite
    session.refresh(new_user)

    # Broadcast the newly saved user (as a JSON string) to all connected Admin tabs!
    await sse_manager.broadcast(new_user.model_dump_json())

    return {
        "message": f"Thank you, {new_user.full_name}! Your request for '{new_user.primary_interest}' has been received. Our HR Advisory specialist will contact you shortly."
    }


# SSE endpoint for Admin Dashboard to receive real-time updates
@router.get(
    "/sse/stream",
    description="Real-time SSE stream for new user enquiries.",
    response_description="Streams newly submitted enquiries as Server-Sent Events."
)
async def stream_enquiries(admin_key: str = Depends(verify_api_key)):
    # 1. Register this admin tab and get its dedicated queue
    queue = await sse_manager.connect()

    async def event_generator():
        try:
            while True:
                try:
                    # 2. Wait up to 15 seconds for new form submission JSON
                    data = await asyncio.wait_for(queue.get(), timeout=15.0)
                    yield f"event: new_enquiry\ndata: {data}\n\n"

                except asyncio.TimeoutError:
                    # 3. Send a silent heartbeat every 15s so proxies don't drop the connection
                    yield ": heartbeat\n\n"

        except asyncio.CancelledError:
            # 4. Clean up the queue when the admin closes the tab
            sse_manager.disconnect(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


# Normal endpoints (non-SSE)

@router.post(
    "/user/submit",
    response_model=UserResponseModel,
    description="Submit a new user form.",
    response_description="Returns a success message upon successful form submission.",
    tags=["User Form Submission"],
    deprecated=True
)
def submit_form(
    user_data: UserRequestModel,
    session: Session = Depends(get_session)
):

    new_user = UserTable.model_validate(user_data)

    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    return {
        "message": f"""Thank you, {new_user.full_name}! Your request for '{new_user.primary_interest}' has been received. Our HR Advisory specialist will contact you shortly."""
    }


# list all users
@router.get(
    "/list/users",
    response_model=ListUsers,
    description="List all users.",
    response_description="Returns a list of all users.",
)
def list_users(session: Session = Depends(get_session), admin_key: str = Depends(verify_api_key)):
    users = session.exec(select(UserTable)).all()
    return {
        "status": "success",
        "count": len(users),
        "users": users
    }


# list all companies
@router.get(
    "/list/companies",
    description="List all companies.",
    response_description="Returns a list of all companies.",
)
def list_companies(session: Session = Depends(get_session), admin_key: str = Depends(verify_api_key)):
    companies = session.exec(select(UserTable.company_name).distinct()).all()
    return {
        "status": "success",
        "count": len(companies),
        "companies": companies
    }


# list all corporate emails
@router.get(
    "/list/emails",
    description="List all corporate emails.",
    response_description="Returns a list of all corporate emails.",
)
def list_emails(session: Session = Depends(get_session), admin_key: str = Depends(verify_api_key)):
    emails = session.exec(select(UserTable.corporate_email).distinct()).all()
    return {
        "status": "success",
        "count": len(emails),
        "emails": emails
    }


# list all phone numbers
@router.get(
    "/list/numbers",
    description="List all phone numbers.",
    response_description="Returns a list of all phone numbers.",
)
def list_phones(session: Session = Depends(get_session), admin_key: str = Depends(verify_api_key)):
    phones = session.exec(select(UserTable.phone_number).distinct()).all()
    return {
        "status": "success",
        "count": len(phones),
        "phones": phones
    }


# list full names
@router.get(
    "/list/names",
    description="List all full names.",
    response_description="Returns a list of all full names.",
)
def list_names(session: Session = Depends(get_session), admin_key: str = Depends(verify_api_key)):

    names = session.exec(select(UserTable.full_name).distinct()).all()
    return {
        "status": "success",
        "count": len(names),
        "names": names
    }


# multi parameter filtering
@router.get(
    "/filter",
    description="Filter users based on multiple parameters.",
    response_description="Returns a list of users filtered by the provided parameters.",
)
def filter_users(
    full_name: str | None = Query(
        default=None, description="Filter by full name"
    ),
    corporate_email: str | None = Query(
        default=None, description="Filter by corporate email"
    ),
    phone_number: str | None = Query(
        default=None, description="Filter by phone number"
    ),
    company_name: str | None = Query(
        default=None, description="Filter by company name"
    ),
    primary_interest: str | None = Query(
        default=None, description="Filter by primary interest"
    ),
    status: EnquiryStatus | None = Query(
        default=None, description="Filter by enquiry status (pending or completed)"
    ),
    created_at: str | None = Query(
        default=None, description="Filter by creation date (YYYY-MM-DD)"
    ),

    # pagination parameters
    skip: int = Query(
        0, ge=0, description="Number of records to skip"
    ),
    limit: int = Query(
        10, ge=1, le=50, description="Max records to return"
    ),

    session: Session = Depends(get_session),
    admin_key: str = Depends(verify_api_key)
):

    # check if at least one filter parameter is provided
    if full_name is None and corporate_email is None and phone_number is None and company_name is None and primary_interest is None and status is None:
        raise HTTPException(
            status_code=400, detail="At least one filter parameter must be provided.")

    query = select(UserTable)

    # apply filters based on provided parameters
    query = query.where(UserTable.full_name ==
                        full_name) if full_name else query
    query = query.where(UserTable.corporate_email ==
                        corporate_email) if corporate_email else query
    query = query.where(UserTable.phone_number ==
                        phone_number) if phone_number else query
    query = query.where(UserTable.company_name ==
                        company_name) if company_name else query
    query = query.where(UserTable.primary_interest ==
                        primary_interest) if primary_interest else query
    query = query.where(UserTable.status ==
                        status) if status else query

    data = session.exec(query.offset(skip).limit(limit)).all()

    return {
        "status": "success",
        "count": len(data),
        "users": data
    }


# update enquiry status
@router.patch(
    "/update/status/{id}",
    response_model=UserTable,
    description="Update the status of a user enquiry.",
    response_description="Returns the updated user enquiry."
)
def update_enquiry_status(
    id: int,
    status_update: UpdateEnquiryStatus,
    session: Session = Depends(get_session),
    admin_key: str = Depends(verify_api_key)
):
    # find the user by id
    user = session.get(UserTable, id)
    if not user:
        raise HTTPException(
            status_code=404, detail=f"User with id {id} not found.")

    # update the status if provided
    if status_update.status is not None:
        user.status = status_update.status

    session.add(user)
    session.commit()
    session.refresh(user)

    return user


# delete user by id
@router.delete(
    "/delete/user/{id}",
    description="Delete a user by their ID.",
    response_description="Returns a success message if the user is deleted."
)
def delete_user(
    id: int,
    session: Session = Depends(get_session),
    admin_key: str = Depends(verify_api_key)
):
    user = session.get(UserTable, id)
    if not user:
        raise HTTPException(
            status_code=404, detail=f"User with id {id} not found.")

    session.delete(user)
    session.commit()

    return {
        "status": "success",
        "message": f"User with id {id} has been deleted."
    }
