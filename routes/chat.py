import os
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError
from sqlmodel import Session, select, or_

from src.database import engine, get_session
from src.auth import verify_api_key, ADMIN_KEY
from src.ws_chat import chat_manager
from models.user import (
    ChatSession,
    ChatMessage,
    IncomingChatPayload,
    SenderRole,
)

chat_router = APIRouter(prefix="/admin", tags=["Live Support Chat"])


# --- 1. VISITOR REST ENDPOINT: Verify Session & Load Chat History ---
@chat_router.get("/chat/user/history")
def get_user_chat_history(
    email: str = Query(..., description="Visitor's corporate email"),
    name: str = Query(..., description="Visitor's full name"),
    session_token: str = Query(...,
                               description="Visitor's localStorage UUID token"),
    session: Session = Depends(get_session),
):
    email = email.strip().lower()
    chat_sess = session.exec(
        select(ChatSession).where(ChatSession.corporate_email == email)
    ).first()

    # First time chatting -> Register their email + session_token
    if not chat_sess:
        chat_sess = ChatSession(
            corporate_email=email,
            full_name=name.strip(),
            session_token=session_token,
        )
        session.add(chat_sess)
        session.commit()
        session.refresh(chat_sess)
        print(f"📝 New user registered: {email}")

    else:
        # Returning user -> Verify their session_token matches so nobody can hijack their chat!
        if chat_sess.session_token != session_token:
            raise HTTPException(
                status_code=403,
                detail="This email is already registered in an active chat session on another device.",
            )
        chat_sess.last_active_at = datetime.now(timezone.utc)
        session.add(chat_sess)
        session.commit()

    # Fetch all messages for this user OR global admin broadcasts
    messages = session.exec(
        select(ChatMessage)
        .where(
            or_(
                ChatMessage.user_email == email,
                ChatMessage.is_broadcast == True,
            )
        )
        .order_by(ChatMessage.created_at.asc())
    ).all()

    return {
        "status": "success",
        "email": chat_sess.corporate_email,
        "full_name": chat_sess.full_name,
        "messages": messages,
    }


# --- 2. ADMIN REST ENDPOINT: Get All Threads & Messages ---
@chat_router.get("/chat/conversations")
def get_all_conversations(
    session: Session = Depends(get_session),
    admin_key: str = Depends(verify_api_key),
):
    sessions = session.exec(
        select(ChatSession).order_by(ChatSession.last_active_at.desc())
    ).all()
    all_messages = session.exec(
        select(ChatMessage).order_by(ChatMessage.created_at.asc())
    ).all()

    threads = []
    for s in sessions:
        user_msgs = [
            m for m in all_messages
            if m.user_email == s.corporate_email or m.is_broadcast
        ]
        unread_count = sum(
            1 for m in user_msgs
            if m.user_email == s.corporate_email
            and m.sender_role == SenderRole.USER
            and not m.is_read_by_admin
        )
        threads.append({
            "corporate_email": s.corporate_email,
            "full_name": s.full_name,
            "is_online": chat_manager.is_user_online(s.corporate_email),
            "last_active_at": s.last_active_at,
            "unread_count": unread_count,
            "messages": user_msgs,
        })

    return {
        "status": "success",
        "online_users": chat_manager.get_online_users(),
        "threads": threads,
    }


# --- 3. ADMIN REST ENDPOINT: Mark User Thread as Read ---
@chat_router.patch("/chat/read/{email}")
def mark_messages_read(
    email: str,
    session: Session = Depends(get_session),
    admin_key: str = Depends(verify_api_key),
):
    email = email.strip().lower()
    unread_msgs = session.exec(
        select(ChatMessage).where(
            ChatMessage.user_email == email,
            ChatMessage.is_read_by_admin == False,
        )
    ).all()

    for m in unread_msgs:
        m.is_read_by_admin = True
        session.add(m)
    session.commit()

    return {"status": "success", "marked_read": len(unread_msgs)}


# --- 4. VISITOR WEBSOCKET ENDPOINT ---
@chat_router.websocket("/ws/user")
async def user_websocket_endpoint(
    websocket: WebSocket,
    email: str = Query(...),
    name: str = Query(...),
    session_token: str = Query(...),
):
    email = email.strip().lower()
    name = name.strip()

    # Verify or create ChatSession in SQLite before accepting WebSocket
    with Session(engine) as db:
        chat_sess = db.exec(
            select(ChatSession).where(ChatSession.corporate_email == email)
        ).first()

        if not chat_sess:
            chat_sess = ChatSession(
                corporate_email=email,
                full_name=name,
                session_token=session_token,
            )
            db.add(chat_sess)
            db.commit()

        elif chat_sess.session_token != session_token:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await chat_manager.connect_user(email, websocket)

    try:
        while True:
            raw_data = await websocket.receive_json()

            try:
                valid_msg = IncomingChatPayload.model_validate(raw_data)
            except ValidationError:
                await websocket.send_json({
                    "event": "error",
                    "message": "Message cannot be empty (1-2000 characters).",
                })
                continue

            # Save visitor's message to SQLite
            with Session(engine) as db:
                new_msg = ChatMessage(
                    user_email=email,
                    user_name=name,
                    sender_role=SenderRole.USER,
                    message=valid_msg.message,
                    is_broadcast=False,
                    is_read_by_admin=False,
                )
                db.add(new_msg)
                db.commit()
                db.refresh(new_msg)

                msg_dict = new_msg.model_dump(mode="json")

            event_payload = {
                "event": "chat_message",
                "data": msg_dict,
            }

            # 1. Echo back to all of this visitor's open tabs
            await chat_manager.send_to_user(email, event_payload)
            # 2. Push live to all connected Admin Dashboard tabs!
            await chat_manager.send_to_admins(event_payload)

    except WebSocketDisconnect:
        await chat_manager.disconnect_user(email, websocket)


# --- 5. ADMIN WEBSOCKET ENDPOINT ---
@chat_router.websocket("/ws/admin")
async def admin_websocket_endpoint(
    websocket: WebSocket,
    token: str | None = Query(default=None),
):
    # Verify Admin API Key before accepting connection
    header_key = websocket.headers.get("x-api-key")
    key = header_key or token
    if key != ADMIN_KEY:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await chat_manager.connect_admin(websocket)

    try:
        while True:
            raw_data = await websocket.receive_json()

            try:
                valid_msg = IncomingChatPayload.model_validate(raw_data)
            except ValidationError:
                await websocket.send_json({
                    "event": "error",
                    "message": "Message cannot be empty (1-2000 characters).",
                })
                continue

            target_email = valid_msg.to_email.strip().lower() if valid_msg.to_email else None
            is_broadcast = target_email is None

            # Look up user's name if sending a 1-on-1 reply
            target_name = "All Visitors"
            with Session(engine) as db:
                if target_email:
                    sess = db.exec(
                        select(ChatSession).where(
                            ChatSession.corporate_email == target_email)
                    ).first()
                    target_name = sess.full_name if sess else target_email

                new_msg = ChatMessage(
                    user_email=target_email if target_email else "ALL",
                    user_name=target_name,
                    sender_role=SenderRole.ADMIN,
                    message=valid_msg.message,
                    is_broadcast=is_broadcast,
                    is_read_by_admin=True,
                )
                db.add(new_msg)
                db.commit()
                db.refresh(new_msg)
                msg_dict = new_msg.model_dump(mode="json")

            event_payload = {
                "event": "chat_message",
                "data": msg_dict,
            }

            # Route message: 1-on-1 DM vs. Global Broadcast to ALL visitors!
            if is_broadcast:
                await chat_manager.broadcast_to_all_users(event_payload)
            else:
                await chat_manager.send_to_user(target_email, event_payload)

            # Sync across all open Admin tabs
            await chat_manager.send_to_admins(event_payload)

    except WebSocketDisconnect:
        chat_manager.disconnect_admin(websocket)
