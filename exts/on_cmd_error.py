"""
Copyright 2021-2025 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import datetime
import importlib

import humanize
import interactions as ipy
from interactions.ext import hybrid_commands as hybrid
from interactions.ext import prefixed_commands as prefixed

import common.utils as utils

ValidContexts = prefixed.PrefixedContext | ipy.InteractionContext | hybrid.HybridContext


class OnCMDError(utils.Extension):
    def __init__(self, bot: utils.THIABase) -> None:
        self.bot: utils.THIABase = bot

    @staticmethod
    async def handle_send(ctx: ValidContexts, content: str) -> None:
        embed = utils.error_embed_generate(content)
        if isinstance(ctx, prefixed.PrefixedContext):
            await ctx.reply(embeds=embed)
        else:
            await ctx.send(
                embeds=embed,
                ephemeral=(not ctx.responded and not ctx.deferred) or ctx.ephemeral,
            )

    @ipy.listen(disable_default_listeners=True)
    async def on_command_error(
        self,
        event: ipy.events.CommandError,
    ) -> None:
        if not isinstance(event.ctx, ValidContexts):
            return await utils.error_handle(event.error)

        if isinstance(event.error, ipy.errors.CommandOnCooldown):
            delta_wait = datetime.timedelta(
                seconds=event.error.cooldown.get_cooldown_time()
            )
            await self.handle_send(
                event.ctx,
                "You're doing that command too fast! "
                + "Try again in"
                f" `{humanize.precisedelta(delta_wait, format='%0.1f')}`.",
            )

        elif isinstance(event.error, utils.CustomCheckFailure | ipy.errors.BadArgument):
            await self.handle_send(event.ctx, str(event.error))
        elif isinstance(event.error, ipy.errors.CommandCheckFailure):
            if event.ctx.guild_id:
                await self.handle_send(
                    event.ctx,
                    "You do not have the proper permissions to use that command.",
                )
        else:
            await utils.error_handle(event.error, ctx=event.ctx)

    @ipy.listen(ipy.events.ModalError, disable_default_listeners=True)
    async def on_modal_error(self, event: ipy.events.ModalError) -> None:
        await self.on_command_error.callback(self, event)

    @ipy.listen(ipy.events.ComponentError, disable_default_listeners=True)
    async def on_component_error(self, event: ipy.events.ComponentError) -> None:
        await self.on_command_error.callback(self, event)


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    OnCMDError(bot)
