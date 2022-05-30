import datetime
import importlib

import humanize
import naff

import common.utils as utils


class OnCMDError(naff.Extension):
    def __init__(self, bot):
        self.bot: naff.Client = bot
        self.bot.on_command_error = self.on_command_error

    def error_embed_generate(self, error_msg):
        return naff.Embed(color=naff.MaterialColors.RED, description=error_msg)

    async def on_command_error(
        self,
        ctx: naff.PrefixedContext | utils.InvestigatorContext,
        error: Exception,
        *args,
        **kwargs,
    ):
        if not ctx.bot.is_ready:
            return

        if not isinstance(ctx, (naff.PrefixedContext, utils.InvestigatorContext)):
            return await utils.error_handle(self.bot, error)

        if isinstance(error, naff.errors.CommandOnCooldown):
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
            naff.errors.BadArgument,
        ):
            await ctx.reply(embed=self.error_embed_generate(str(error)))
        elif isinstance(error, utils.CustomCheckFailure):
            await ctx.reply(embed=self.error_embed_generate(str(error)))
        elif isinstance(error, naff.errors.CommandCheckFailure):
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
