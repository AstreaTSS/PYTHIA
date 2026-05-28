"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import dataclasses
import importlib
import os

import aiohttp
import discord
import typing_extensions as typing
from discord.ext import tasks

import common.utils as utils


@dataclasses.dataclass(kw_only=True)
class VoteHandler:
    name: str
    base_url: str
    headers: dict[str, str]
    data_url: str
    data_callback: typing.Callable[[int, int], dict[str, typing.Any]]
    vote_url: str | None


class Voting(utils.Cog):
    session: aiohttp.ClientSession

    def __init__(self, bot: utils.THIABase) -> None:
        self.bot = bot
        self.__cog_name__ = "Voting"

        self.handlers: list[VoteHandler] = []

        if os.environ.get("TOP_GG_TOKEN"):
            self.handlers.append(
                VoteHandler(
                    name="Top.gg",
                    base_url="https://top.gg/api",
                    headers={"Authorization": os.environ["TOP_GG_TOKEN"]},
                    data_url="/bots/{bot_id}/stats",
                    data_callback=lambda guild_count, shard_count: {
                        "server_count": guild_count,
                        "shard_count": shard_count,
                    },
                    vote_url="https://top.gg/bot/{bot_id}/vote **(prefered)**",
                )
            )

        if not self.handlers:
            raise ValueError("No voting handlers were configured.")

        self.autopost_guild_count.start()
        self.bot.create_task(self.establish_session())

    def cog_unload(self) -> None:
        self.autopost_guild_count.cancel()
        self.bot.create_task(self.close_session())

    async def establish_session(self) -> None:
        self.session = aiohttp.ClientSession()

    async def close_session(self) -> None:
        await self.session.close()

    @tasks.loop(minutes=30)
    async def autopost_guild_count(self) -> None:
        server_count = self.bot.guild_count
        shard_count = len(self.bot.shards)

        for handler in self.handlers:
            async with self.session.post(
                f"{handler.base_url}{handler.data_url.format(bot_id=self.bot.user.id)}",
                json=handler.data_callback(server_count, shard_count),
                headers=handler.headers,
            ) as r:
                try:
                    r.raise_for_status()
                except aiohttp.ClientResponseError as e:
                    await utils.error_handle(e)

    @discord.slash_command(
        name="vote",
        description="Vote for the bot.",
        integration_types={
            discord.IntegrationType.guild_install,
            discord.IntegrationType.user_install,
        },
        contexts={
            discord.InteractionContextType.guild,
            discord.InteractionContextType.bot_dm,
            discord.InteractionContextType.private_channel,
        },
    )
    async def vote(self, ctx: utils.THIASlashContext) -> None:
        website_votes: list[str] = [
            f"**{handler.name}** - {handler.vote_url.format(bot_id=self.bot.user.id)}"
            for handler in self.handlers
            if handler.vote_url
        ]
        await ctx.respond(
            view=utils.make_view(
                title="Vote for the bot", description="\n".join(website_votes)
            )
        )


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    bot.add_cog(Voting(bot))
