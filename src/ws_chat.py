from fastapi import WebSocket


class ChatConnectionManager:
    def __init__(self):

        # 1. Visitor Pool: maps corporate_email -> list of WebSocket tabs
        self.user_connections: dict[str, list[WebSocket]] = {}

        # 2. Admin Pool: list of connected Admin Dashboard WebSocket tabs
        self.admin_connections: list[WebSocket] = []

    # --- VISITOR CONNECTION METHODS ---

    # 1. Connect a visitor's chat widget to the WebSocket server

    async def connect_user(self, email: str, websocket: WebSocket):
        await websocket.accept()

        if email not in self.user_connections:
            self.user_connections[email] = []

        self.user_connections[email].append(websocket)
        print(
            f"🟢 Visitor connected: {email} (Tabs: {len(self.user_connections[email])})")

        # Notify all open Admin tabs that this user is now ONLINE!
        await self.send_to_admins({
            "event": "user_presence",
            "user_email": email,
            "is_online": True,
            "online_users": self.get_online_users()
        })

    # 2. Disconnect a visitor's chat widget from the WebSocket server
    async def disconnect_user(self, email: str, websocket: WebSocket):
        if email in self.user_connections:
            if websocket in self.user_connections[email]:
                self.user_connections[email].remove(websocket)
                print(f"⚪ Visitor tab closed: {email}")

            # Only mark offline if ALL tabs for this email are closed
            if not self.user_connections[email]:
                del self.user_connections[email]
                print(f"⚪ Visitor offline: {email}")

                # Notify all open Admin tabs that this user is now OFFLINE!
                await self.send_to_admins({
                    "event": "user_presence",
                    "user_email": email,
                    "is_online": False,
                    "online_users": self.get_online_users()
                })

    # --- ADMIN CONNECTION METHODS ---

    # 1. Connect an Admin Dashboard tab to the WebSocket server

    async def connect_admin(self, websocket: WebSocket):
        await websocket.accept()
        self.admin_connections.append(websocket)
        print(
            f"🛡️ Admin connected to Live Chat! (Total Admin tabs: {len(self.admin_connections)})")

    # 2. Disconnect an Admin Dashboard tab from the WebSocket server
    def disconnect_admin(self, websocket: WebSocket):
        if websocket in self.admin_connections:
            self.admin_connections.remove(websocket)
        print(
            f"🛡️ Admin disconnected from Live Chat. (Remaining: {len(self.admin_connections)})")

    # --- ROUTING & MESSAGING METHODS ---

    # 1. Get a list of all currently online visitor emails

    def get_online_users(self) -> list[str]:
        """Returns a list of all currently online visitor emails."""
        return list(self.user_connections.keys())

    # 2. Check if a specific visitor is online
    def is_user_online(self, email: str) -> bool:
        return email in self.user_connections

    # 3. Send a JSON message to all connected Admin Dashboard tabs
    async def send_to_admins(self, payload: dict):
        """Sends a JSON event to ALL open Admin Dashboard tabs."""
        for admin_ws in list(self.admin_connections):
            try:
                await admin_ws.send_json(payload)
            except Exception:
                self.disconnect_admin(admin_ws)

    # 4. Send a JSON message to a specific visitor's open chat widget(s)
    async def send_to_user(self, email: str, payload: dict) -> bool:
        """Sends a JSON message to a SPECIFIC user's open chat widget(s)."""
        sockets = self.user_connections.get(email)
        if not sockets:
            return False
        for ws in list(sockets):
            try:
                await ws.send_json(payload)
            except Exception:
                pass
        return True

    # 5. Broadcast a JSON message to all connected visitors
    async def broadcast_to_all_users(self, payload: dict):
        """Admin Global Broadcast: Sends a JSON message to EVERY connected visitor on the website!"""
        for email, sockets in list(self.user_connections.items()):
            for ws in list(sockets):
                try:
                    await ws.send_json(payload)
                except Exception:
                    pass


# Single global instance to import in routes/chat.py
chat_manager = ChatConnectionManager()
