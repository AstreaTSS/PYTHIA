import datetime
import importlib

import humanize
import interactions as ipy

import common.utils as utils


class OnCMDError(ipy.Extension):
    def __init__(self, bot):
        self.bot: ipy.Client = bot

    def error_embed_generate(self, error_msg):
        return ipy.Embed(color=ipy.MaterialColors.RED, description=error_msg)

    @ipy.listen(disable_default_listeners=True)
    async def on_command_error(
        self,
        event: ipy.events.CommandError,
    ):
        if not hasattr(event.ctx, "send"):
            return await utils.error_handle(self.bot, event.error)

        if isinstance(event.error, ipy.errors.CommandOnCooldown):
            delta_wait = datetime.timedelta(
                seconds=event.error.cooldown.get_cooldown_time()
            )
            await event.ctx.send(
                embeds=self.error_embed_generate(
                    "You're doing that command too fast! "
                    + "Try again in"
                    f" `{humanize.precisedelta(delta_wait, format='%0.0f')}`."
                )
            )
        elif isinstance(event.error, utils.CustomCheckFailure):
            await event.ctx.send(embeds=self.error_embed_generate(str(event.error)))
        elif isinstance(
            event.error,
            ipy.errors.BadArgument,
        ):
            await event.ctx.send(embeds=self.error_embed_generate(str(event.error)))
        elif isinstance(event.error, ipy.errors.CommandCheckFailure):
            if event.ctx.guild:
                await event.ctx.send(
                    embeds=self.error_embed_generate(
                        "You do not have the proper permissions to use that command."
                    )
                )
        else:
            await utils.error_handle(self.bot, event.error, event.ctx)


def setup(bot):
    importlib.reload(utils)
    OnCMDError(bot)
