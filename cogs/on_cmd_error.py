#!/usr/bin/env python3.8
import datetime
import importlib

import dis_snek
import humanize
import molter

import common.utils as utils


class OnCMDError(dis_snek.Scale):
    def __init__(self, bot):
        self.bot: dis_snek.Snake = bot
        self.bot.on_command_error = self.on_command_error

    def error_embed_generate(self, error_msg):
        return dis_snek.Embed(color=dis_snek.MaterialColors.RED, description=error_msg)

    async def on_command_error(
        self, ctx: dis_snek.Context, error: Exception, *args, **kwargs
    ):
        if not ctx.bot.is_ready or not isinstance(ctx, dis_snek.MessageContext):
            return

        if isinstance(error, dis_snek.errors.CommandOnCooldown):
            delta_wait = datetime.timedelta(seconds=error.cooldown.get_cooldown_time())
            await ctx.reply(
                embed=self.error_embed_generate(
                    "You're doing that command too fast! "
                    + "Try again in"
                    f" `{humanize.precisedelta(delta_wait, format='%0.0f')}`."
                )
            )
        elif isinstance(
            error,
            molter.BadArgument,
        ):
            await ctx.reply(embed=self.error_embed_generate(str(error)))
        elif isinstance(error, utils.CustomCheckFailure):
            await ctx.reply(embed=self.error_embed_generate(str(error)))
        elif isinstance(error, dis_snek.errors.CommandCheckFailure):
            if ctx.guild:
                await ctx.reply(
                    embed=self.error_embed_generate(
                        "You do not have the proper permissions to use that command."
                    )
                )
        else:
            await utils.error_handle(self.bot, error, ctx)


def setup(bot):
    importlib.reload(utils)
    OnCMDError(bot)
