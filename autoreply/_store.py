from typing import List, Optional, Tuple

from mautrix.types import RoomID
from mautrix.util.async_db import Connection, Database, UpgradeTable

upgrade_table = UpgradeTable()


@upgrade_table.register(description="Set up initial database schema")
async def schema_v1(conn: Connection) -> None:
    """Set up the database schema as of v1.0"""
    # Create a table to track management rooms.
    await conn.execute(
        """CREATE TABLE autoreply_management_rooms (
            user_id   TEXT PRIMARY KEY,
            room_id   TEXT NOT NULL
        )"""
    )

    # Create a table to track messages we've auto-replied to.
    await conn.execute(
        """CREATE TABLE autoreply_messages (
            room_id  TEXT PRIMARY KEY,
            event_id TEXT NOT NULL,
            user_id TEXT NOT NULL
        )
        """
    )

    # Create a table to track the user's away state.
    await conn.execute(
        """CREATE TABLE autoreply_user_away (
            user_id TEXT PRIMARY KEY,
            is_away BOOLEAN NOT NULL
        )
        """
    )


class AutoReplyBotStore:
    def __init__(self, database: Database, user_id: str) -> None:
        self.database = database

        # The Matrix user ID associated with the current instance.
        self.user_id = user_id

    async def get_management_room(self) -> Optional[str]:
        """Retrieve the ID of the management room for the current user, if any.

        Returns:
            The room ID of the management room if one exists, None otherwise.
        """
        sql = "SELECT room_id FROM autoreply_management_rooms WHERE user_id = $1"
        return await self.database.fetchval(sql, self.user_id)

    async def store_management_room(self, room_id: RoomID) -> None:
        """Store the given room ID as the management room for the current user.

        Args:
            room_id: The room ID to store.
        """
        sql = "INSERT INTO autoreply_management_rooms(user_id, room_id) VALUES($1, $2)"
        await self.database.execute(sql, self.user_id, room_id)

    async def get_message_id_in_room(self, room_id: RoomID) -> Optional[str]:
        """Retrieve the ID of the first missed event in the given room, if any.

        Args:
            room_id: The ID of the room to check.

        Returns:
            The ID of the first missed event in the room if any, None otherwise.
        """
        sql = """
            SELECT event_id FROM autoreply_messages WHERE room_id = $1 AND user_id = $2
        """
        return await self.database.fetchval(sql, room_id, self.user_id)

    async def store_message(self, event_id: str, room_id: str) -> None:
        """Stores the given event ID as the first missed event in the given room.

        Args:
            event_id: The event ID to store.
            room_id: The ID of the room the event was sent into.
        """
        sql = """
            INSERT INTO autoreply_messages(event_id, room_id, user_id) VALUES($1, $2, $3)
        """
        await self.database.execute(sql, event_id, room_id, self.user_id)

    async def clear_messages(self) -> None:
        """Remove all missed messages for the current user."""
        sql = "DELETE FROM autoreply_messages WHERE user_id = $1"
        await self.database.execute(sql, self.user_id)

    async def get_missed_messages(self) -> List[Tuple[str, str]]:
        """Retrieve a summary of missed messages.

        Returns:
            A list of rooms containing missed messages. Each room is represented by a
            tuple where the first element is the room's ID, and the second element is the
            event ID of the first missed message in the room.
        """
        sql = "SELECT room_id, event_id FROM autoreply_messages WHERE user_id = $1"
        rows = await self.database.fetch(sql, self.user_id)
        return [(row["room_id"], row["event_id"]) for row in rows]

    async def update_away_state(self, is_away: bool) -> None:
        """Update the away state (away/back) of the current user.

        Args:
            is_away: A boolean indicating whether the user is away (True = away,
                False = not away).
        """
        sql = """
            INSERT INTO autoreply_user_away(user_id, is_away)
            VALUES($1, $2)
            ON CONFLICT(user_id) DO
                UPDATE SET is_away = EXCLUDED.is_away
                WHERE autoreply_user_away.user_id = EXCLUDED.user_id
        """
        await self.database.execute(sql, self.user_id, is_away)

    async def is_away(self) -> bool:
        """Check if the user is currently marked as away.

        If the user has no state set, we consider them as not away.

        Returns:
            True if the user is away, False otherwise.
        """
        sql = "SELECT is_away FROM autoreply_user_away WHERE user_id = $1"
        ret = await self.database.fetchval(sql, self.user_id)
        if ret is None:
            return False

        return ret
