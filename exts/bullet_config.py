import importlib
import typing

import interactions as ipy
import tansy

import common.models as models
import common.utils as utils


class BulletConfigCMDs(utils.Extension):
    """Commands for using and modifying Truth Bullet server settings."""

    def __init__(self, bot):
        self.name = "Bullet Config"
        self.bot = bot

    config = tansy.SlashCommand(
        name="config",
        description="Handles configuration of the bot.",  # type: ignore
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @config.subcommand(
        sub_cmd_name="info",
        sub_cmd_description=(
            "Lists out the Truth Bullet configuration settings for the server."
        ),
    )
    async def bullet_config(self, ctx: utils.UIInteractionContext):
        guild_config = await ctx.fetch_config()

        str_builder = [
            f"Truth Bullets: {utils.toggle_friendly_str(guild_config.bullets_enabled)}",
            (
                "Truth Bullet channel:"
                f" {f'<#{guild_config.bullet_chan_id}>' if guild_config.bullet_chan_id else 'N/A'}"
            ),
            "",
        ]

        str_builder.extend(
            (
                (
                    "Player role:"
                    f" {f'<@&{guild_config.player_role}>' if guild_config.player_role else 'N/A'}"
                ),
                (
                    "Best Detective role:"
                    f" {f'<@&{guild_config.ult_detective_role}>' if guild_config.ult_detective_role else 'N/A'}"
                ),
            )
        )
        embed = ipy.Embed(
            title=f"Server config for {ctx.guild.name}",
            description="\n".join(str_builder),
            color=ctx.bot.color,
            timestamp=ipy.Timestamp.utcnow(),
        )
        await ctx.send(embed=embed)

    @config.subcommand(
        sub_cmd_name="bullet-channel",
        sub_cmd_description="Sets (or unsets) where all Truth Bullets are sent to.",
    )
    async def set_bullet_channel(
        self,
        ctx: utils.UIInteractionContext,
        channel: typing.Optional[ipy.GuildText] = tansy.Option(
            "The channel to send Truth Bullets to.", default=None
        ),
        unset: bool = tansy.Option(
            "Should the Truth Bullet channel be unset?", default=False
        ),
    ):
        if not (bool(channel) ^ unset):
            raise ipy.errors.BadArgument(
                "You must set a Truth Bullet channel or specify to unset it."
            )

        guild_config = await ctx.fetch_config()

        guild_config.bullet_chan_id = channel.id if channel else None
        await guild_config.save()

        if channel:
            await ctx.send(f"Truth Bullet channel set to {channel.mention}!")
        else:
            await ctx.send("Truth Bullet channel unset.")

    @config.subcommand(
        sub_cmd_name="best-detective",
        sub_cmd_description="Sets (or unsets) the Best Detective role.",
    )
    async def set_best_detective_role(
        self,
        ctx: utils.UIInteractionContext,
        role: typing.Optional[ipy.Role] = tansy.Option(
            "The Best Detective role to use.",
            converter=utils.ValidRoleConverter,
            default=None,
        ),
        unset: bool = tansy.Option("Should the role be unset?", default=False),
    ):
        if not (bool(role) ^ unset):
            raise ipy.errors.BadArgument(
                "You must either specify a role or specify to unset the role."
            )

        guild_config = await ctx.fetch_config()
        guild_config.ult_detective_role = role.id if role else None
        await guild_config.save()

        if role:
            await ctx.send(
                f"Best Detective role set to {role.mention}!",
                allowed_mentions=utils.deny_mentions(ctx.author),
            )
        else:
            await ctx.send("Best Detective role unset.")

    @config.subcommand(
        sub_cmd_name="player",
        sub_cmd_description=(
            "Sets (or unsets) the Player role, the role that can find Truth Bullets."
        ),
    )
    async def set_player_role(
        self,
        ctx: utils.UIInteractionContext,
        role: typing.Optional[ipy.Role] = tansy.Option(
            "The Player role to use.",
            converter=utils.ValidRoleConverter,
            default=None,
        ),
        unset: bool = tansy.Option("Should the role be unset?", default=False),
    ):
        if not (bool(role) ^ unset):
            raise ipy.errors.BadArgument(
                "You must either specify a role or specify to unset the role."
            )

        guild_config = await ctx.fetch_config()
        guild_config.player_role = role.id if role else None
        await guild_config.save()

        if role:
            await ctx.send(
                f"Player role set to {role.mention}!",
                allowed_mentions=utils.deny_mentions(ctx.author),
            )
        else:
            await ctx.send("Player role unset.")

    def enable_check(self, config: models.Config):
        if not config.player_role:
            raise utils.CustomCheckFailure(
                "You still need to set the Player role for this server!"
            )
        elif not config.bullet_chan_id:
            raise utils.CustomCheckFailure(
                "You still need to set a Truth Bullets channel!"
            )

    @config.subcommand(
        sub_cmd_name="toggle",
        sub_cmd_description="Turns on or off the Truth Bullets.",
    )
    async def toggle_bullets(
        self,
        ctx: utils.UIInteractionContext,
        toggle: bool = tansy.Option(
            "Should the Truth Bullets be on (true) or off (false)?"
        ),
    ):
        guild_config = await ctx.fetch_config()
        if (
            not guild_config.bullets_enabled and toggle
        ):  # if truth bullets will be enabled by this
            self.enable_check(guild_config)

        guild_config.bullets_enabled = toggle
        await guild_config.save()

        await ctx.send(
            "Truth Bullets turned"
            f" {utils.toggle_friendly_str(guild_config.bullets_enabled)}!"
        )


def setup(bot):
    importlib.reload(utils)
    BulletConfigCMDs(bot)
