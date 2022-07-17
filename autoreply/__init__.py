# Copyright 2022 Brendan Abolivier
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from typing import Dict, List, Type

from maubot import MessageEvent, Plugin
from maubot.handlers import event
from mautrix.types import EventType, RoomID
from mautrix.util.async_db import UpgradeTable
from mautrix.util.config import BaseProxyConfig

from autoreply._config import AutoReplyBotConfig
from autoreply._store import AutoReplyBotStore, upgrade_table


class AutoReplyBot(Plugin):
    # The ID of the room to expect commands into.
    management_room: RoomID
    # The class to use for interacting with the database.
    store: AutoReplyBotStore

    async def start(self) -> None:
        """Set up the bot. This method is called by maubot at instance startup."""
        # Load the config.
        self.config.load_and_update()

        # Set up the store.
        self.store = AutoReplyBotStore(
            database=self.database,
            user_id=self.client.mxid,
        )

        # Look for an ID for the management room, or create it if it doesn't already
        # exist.
        management_room = await self.store.get_management_room()
        if management_room is None:
            self.management_room = await self._create_management_room()
        else:
            self.management_room = RoomID(management_room)

    @classmethod
    def get_config_class(cls) -> Type[BaseProxyConfig]:
        """Returns the class to use to handle hot reloads of the configuration."""
        return AutoReplyBotConfig

    @classmethod
    def get_db_upgrade_table(cls) -> UpgradeTable:
        """Returns the UpgradeTable instance to use to set up and update the database
        schema.
        """
        return upgrade_table

    async def _create_management_room(self) -> RoomID:
        """Create the management room for the current user, with the configured avatar
        and name, and end-to-end encryption enabled.

        Returns:
            The ID of the room that's been created.
        """
        room_id = await self.client.create_room(
            name=self.config["room"]["name"],
            initial_state=[
                {
                    "type": "m.room.avatar",
                    "content": {
                        "url": self.config["room"]["icon"],
                    },
                },
                {
                    "type": "m.room.encryption",
                    "content": {
                        "algorithm": "m.megolm.v1.aes-sha2",
                    },
                },
            ],
        )

        await self.store.store_management_room(room_id)

        return room_id

    @event.on(EventType.ROOM_MESSAGE)
    async def handle_message(self, evt: MessageEvent) -> None:
        """Handle an incoming m.room.message event.

        Args:
            evt: The event to handle.
        """
        # If the message has been sent to the management room, check if this is a command
        # we might know. Otherwise, send an automated reply if needed.
        if evt.room_id == self.management_room:
            await self._handle_management_command(evt)
        else:
            await self._auto_reply(evt)

    async def _is_direct(self, room_id: RoomID) -> bool:
        """Look through the current user's account data to check if the given room is a
        DM.

        TODO: Maybe we can cache this information and manage the invalidation by
            registering a handler for account data events.

        Args:
            room_id: The room ID to check.

        Returns:
            True if the room is a DM, False otherwise.
        """
        data: Dict[str, List[str]] = await self.client.get_account_data("m.direct")
        for _, rooms in data.items():
            for room in rooms:
                if room == room_id:
                    return True

        return False

    async def _auto_reply(self, evt: MessageEvent) -> None:
        """Check if we want to auto-reply to the given message event, and send an
        automated message if so.

        Args:
            evt: The event to maybe reply to.
        """
        if (
            # We don't want to reply to messages we sent.
            evt.sender != self.client.mxid
            # We only want to auto-reply if the user is away.
            and await self.store.is_away()
            # We only want to auto-reply once per room.
            and await self.store.get_message_id_in_room(evt.room_id) is None
            # We only want to auto-reply in DMs.
            and await self._is_direct(evt.room_id)
        ):
            # Send the reply.
            await evt.reply(
                content=self.config["message"],
            )

            # Store that we've replied to a message in this room, so we don't do it again
            # until the user comes back.
            await self.store.store_message(
                event_id=evt.event_id,
                room_id=evt.room_id,
            )

    async def _handle_management_command(self, evt: MessageEvent) -> None:
        """Handles commands in the management room.

        Args:
            evt: The event to check for a command and reply to.
        """
        if evt.content.body.startswith("!clear"):
            # !clear is meant as a development tool to clear the database tracking
            # messages we've reacted to (and thus preventing multiple auto-replies to be
            # sent into the same room).
            await self.store.clear_messages()
            await evt.reply("Cleared messages")
        if evt.content.body.startswith("!away"):
            # !away is the command the user uses to mark themselves as away, which turns
            # on auto-reply.
            await self.store.update_away_state(is_away=True)
            await evt.reply("Your status has been updated. Have a nice break!")
        if evt.content.body.startswith("!back"):
            # !back is the command the user uses to mark themselves as back/not away. This
            # generates and sends a summary of all the messages they've missed while away,
            # and also clears them from the database (so that the database is clean when
            # the user goes away again).
            await self.store.update_away_state(is_away=False)
            reply_content = "Your status has been updated. Welcome back!\n\n"
            # Send a summary of the messages the user has missed, if any.
            reply_content += await self._generate_missed_messages_summary()
            await evt.reply(
                content=reply_content,
                markdown=True,
            )
            # Clear the list of outstanding missed messages.
            await self.store.clear_messages()

    async def _generate_missed_messages_summary(self) -> str:
        """Generates a summary of the messages the user has missed, if any.

        Returns:
            The text summary to send back to the user.
        """
        messages = await self.store.get_missed_messages()
        if len(messages) == 0:
            # If there isn't any missed message, just return now.
            return "You haven't missed any message while you were away."

        # If there are messages to report, iterate over them to format them nicely.
        summary = (
            "While you were away, you have missed messages in the following DM(s):\n"
        )
        for room_id, event_id in messages:
            summary += f"\n* {self._generate_room_entry(room_id, event_id)}"

        return summary

    def _generate_room_entry(self, room_id: str, event_id: str) -> str:
        """Generates the entry for a given room in the missed messages summary.

        The entry consists in the room ID (with a matrix.to link to pillify it) and a
        link to view the first missed message.

        Args:
            room_id: The ID of the room.
            event_id: The event ID of the first message missed in the room.
        """
        # We make a link of the room ID so that compatible clients can pillify it. We
        # don't need to provide `via` parameters since the user is already in these rooms.
        entry = f"[{room_id}](https://matrix.to/#/{room_id})"
        entry += f" ([view message](https://matrix.to/#/{room_id}/{event_id}))"
        return entry
