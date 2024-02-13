"""
Copyright 2022-2024 AstreaTSS.
This file is part of Ultimate Investigator.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import datetime
import importlib

import humanize
import interactions as ipy

import common.utils as utils


class OnCMDError(ipy.Extension):
    def __init__(self, bot: ipy.Client) -> None:
        self.bot: ipy.Client = bot

    @ipy.listen(disable_default_listeners=True)
    async def on_command_error(
        self,
        event: ipy.events.CommandError,
    ) -> None:
        if not hasattr(event.ctx, "send"):
            return await utils.error_handle(event.error)

        if isinstance(event.error, ipy.errors.CommandOnCooldown):
            delta_wait = datetime.timedelta(
                seconds=event.error.cooldown.get_cooldown_time()
            )
            await event.ctx.send(
                embeds=utils.error_embed_generate(
                    f"You're doing that command too fast! Try again in `{humanize.precisedelta(delta_wait, format='%0.0f')}`."
                )
            )
        elif isinstance(event.error, utils.CustomCheckFailure):
            await event.ctx.send(embeds=utils.error_embed_generate(str(event.error)))
        elif isinstance(
            event.error,
            ipy.errors.BadArgument,
        ):
            await event.ctx.send(embeds=utils.error_embed_generate(str(event.error)))
        elif isinstance(event.error, ipy.errors.CommandCheckFailure):
            if event.ctx.guild:
                await event.ctx.send(
                    embeds=utils.error_embed_generate(
                        "You do not have the proper permissions to use that command."
                    )
                )
        else:
            await utils.error_handle(event.error, ctx=event.ctx)


def setup(bot: ipy.Client) -> None:
    importlib.reload(utils)
    OnCMDError(bot)
