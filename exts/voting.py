"""
Copyright 2021-2024 AstreaTSS.
This file is part of PYTHIA, formerly known as Ultimate Investigator.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

"""
Copyright 2020-2024 AstreaTSS.
This file is part of the Realms Playerlist Bot.

The Realms Playerlist Bot is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

The Realms Playerlist Bot is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with the Realms
Playerlist Bot. If not, see <https://www.gnu.org/licenses/>.
"""

import importlib
import os

import aiohttp
import attrs
import interactions as ipy
import typing_extensions as typing

import common.utils as utils


@attrs.define(kw_only=True)
class VoteHandler:
    name: str = attrs.field()
    base_url: str = attrs.field()
    headers: dict[str, str] = attrs.field()
    data_url: str = attrs.field()
    data_callback: typing.Callable[[int], dict[str, typing.Any]] = attrs.field()
    vote_url: typing.Optional[str] = attrs.field()


class Voting(ipy.Extension):
    session: aiohttp.ClientSession

    def __init__(self, bot: utils.THIABase) -> None:
        self.bot: utils.THIABase = bot
        self.name = "Voting"

        self.shard_count = 1

        self.handlers: list[VoteHandler] = []

        if os.environ.get("TOP_GG_TOKEN"):
            self.handlers.append(
                VoteHandler(
                    name="Top.gg",
                    base_url="https://top.gg/api",
                    headers={"Authorization": os.environ["TOP_GG_TOKEN"]},
                    data_url="/bots/{bot_id}/stats",
                    data_callback=lambda guild_count: {
                        "server_count": guild_count,
                        "shard_count": self.shard_count,
                    },
                    vote_url="https://top.gg/bot/{bot_id}/vote **(prefered)**",
                )
            )

        # TODO: how do renames work?
        # if os.environ.get("DBL_TOKEN"):
        #     self.handlers.append(
        #         VoteHandler(
        #             name="Discord Bot List",
        #             base_url="https://discordbotlist.com/api/v1",
        #             headers={"Authorization": os.environ["DBL_TOKEN"]},
        #             data_url="/bots/{bot_id}/stats",
        #             data_callback=lambda guild_count: {"guilds": guild_count},
        #             vote_url=(
        #                 "https://discordbotlist.com/bots/ultimate-investigator/upvote"
        #             ),
        #         )
        #     )

        if not self.handlers:
            raise ValueError("No voting handlers were configured.")

        self.autopost_guild_count.start()
        self.bot.create_task(self.establish_session())

    def drop(self) -> None:
        self.autopost_guild_count.stop()
        self.bot.create_task(self.close_session())
        super().drop()

    async def establish_session(self) -> None:
        self.session = aiohttp.ClientSession()

    async def close_session(self) -> None:
        await self.session.close()

    @ipy.Task.create(ipy.IntervalTrigger(minutes=30))
    async def autopost_guild_count(self) -> None:
        server_count = self.bot.guild_count

        for handler in self.handlers:
            async with self.session.post(
                f"{handler.base_url}{handler.data_url.format(bot_id=self.bot.user.id)}",
                json=handler.data_callback(server_count),
                headers=handler.headers,
            ) as r:
                try:
                    r.raise_for_status()
                except aiohttp.ClientResponseError as e:
                    await utils.error_handle(e)

    @ipy.slash_command(
        name="vote",
        description="Vote for the bot.",
    )
    async def vote(self, ctx: utils.THIASlashContext) -> None:
        website_votes: list[str] = [
            f"**{handler.name}** - {handler.vote_url.format(bot_id=self.bot.user.id)}"
            for handler in self.handlers
            if handler.vote_url
        ]
        await ctx.send(
            embeds=ipy.Embed(
                title="Vote for the bot",
                description="\n".join(website_votes),
                color=self.bot.color,
                timestamp=ctx.id.created_at,
            )
        )


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    Voting(bot)
