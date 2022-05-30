import importlib
import typing

import naff

import common.models as models
import common.utils as utils


class BulletConfigCMDs(utils.Extension):
    """Commands for using and modifying Truth Bullet server settings."""

    def __init__(self, bot):
        self.name = "Bullet Config"
        self.bot = bot

    config = naff.SlashCommand(
        name="config",  # type: ignore
        description="Handles configuration of the bot.",  # type: ignore
        default_member_permissions=naff.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @config.subcommand(
        sub_cmd_name="info",
        sub_cmd_description=(
            "Lists out the Truth Bullet configuration settings for the server."
        ),
    )
    async def bullet_config(self, ctx: utils.InvestigatorContext):
        await ctx.defer()

        guild_config = await ctx.fetch_config()

        str_builder = [
            f"Truth Bullets: {utils.toggle_friendly_str(guild_config.bullets_enabled)}",
            "Truth Bullet channel:"
            f" {f'<#{guild_config.bullet_chan_id}>' if guild_config.bullet_chan_id > 0 else 'None'}",
            "",
        ]

        str_builder.append(
            "Player role:"
            f" {f'<@&{guild_config.player_role}>' if guild_config.player_role > 0 else 'None'}"
        )
        str_builder.append(
            "Best Detective role:"
            f" {f'<@&{guild_config.ult_detective_role}>' if guild_config.ult_detective_role > 0 else 'None'}"
        )

        embed = naff.Embed(
            title=f"Server config for {ctx.guild.name}",
            description="\n".join(str_builder),
            color=14232643,
        )
        await ctx.send(embed=embed)

    @config.subcommand(
        sub_cmd_name="bullet-channel",
        sub_cmd_description="Sets where all Truth Bullets are sent to.",
    )
    @naff.slash_option(
        "channel",
        "The channel to send Truth Bullets to.",
        naff.OptionTypes.CHANNEL,
        required=True,
        channel_types=[
            naff.ChannelTypes.GUILD_TEXT,
            naff.ChannelTypes.GUILD_PUBLIC_THREAD,
        ],
    )
    async def set_bullet_channel(
        self,
        ctx: utils.InvestigatorContext,
        channel: typing.Annotated[naff.GuildText, utils.ValidChannelConverter],
    ):
        await ctx.defer()

        guild_config = await ctx.fetch_config()
        guild_config.bullet_chan_id = channel.id
        await guild_config.save()

        await ctx.send(f"Truth Bullet channel set to {channel.mention}!")

    @config.subcommand(
        sub_cmd_name="best-detective-role",
        sub_cmd_description="Sets (or unsets) the Best Detective role.",
    )
    @naff.slash_option(
        "role", "The Best Detective role to use.", naff.OptionTypes.ROLE, required=False
    )
    @naff.slash_option(
        "unset", "Should the role be unset?", naff.OptionTypes.BOOLEAN, required=False
    )
    async def set_best_detective_role(
        self,
        ctx: utils.InvestigatorContext,
        role: typing.Annotated[
            typing.Optional[naff.Role], utils.ValidRoleSlashConverter
        ] = None,
        unset: typing.Optional[bool] = None,
    ):
        if not role and not unset:
            raise naff.errors.BadArgument(
                "You must either specify a role or pick to unset the role."
            )

        if role and unset:
            raise naff.errors.BadArgument(
                "You cannot set both a role and unset the role."
            )

        await ctx.defer()

        guild_config = await ctx.fetch_config()
        guild_config.ult_detective_role = role.id if role else 0
        await guild_config.save()

        if role:
            await ctx.send(
                f"Best Detective role set to {role.mention}!",
                allowed_mentions=utils.deny_mentions(ctx.author),
            )
        else:
            await ctx.send("Best Detective role unset!")

    @config.subcommand(
        sub_cmd_name="player",
        sub_cmd_description=(
            "Sets the Player role, the role that can find Truth Bullets."
        ),
    )
    @naff.slash_option(
        "role", "The Player role to use.", naff.OptionTypes.ROLE, required=True
    )
    async def set_player_role(self, ctx: utils.InvestigatorContext, role: naff.Role):
        await ctx.defer()

        guild_config = await ctx.fetch_config()
        guild_config.player_role = role.id
        await guild_config.save()

        await ctx.send(
            f"Player role set to {role.mention}!",
            allowed_mentions=utils.deny_mentions(ctx.author),
        )

    def enable_check(self, config: models.Config):
        if config.player_role <= 0:
            raise utils.CustomCheckFailure(
                "You still need to set the Player role for this server!"
            )
        elif config.bullet_chan_id <= 0:
            raise utils.CustomCheckFailure(
                "You still need to set a Truth Bullets channel!"
            )

    @config.subcommand(
        sub_cmd_name="toggle", sub_cmd_description="Turns on or off the Truth Bullets."
    )
    @naff.slash_option(
        "toggle",
        "Should the Truth Bullets be on or off?",
        naff.OptionTypes.INTEGER,
        required=True,
        choices=[naff.SlashCommandChoice("off", 0), naff.SlashCommandChoice("on", 1)],  # type: ignore
    )
    async def toggle_bullets(
        self,
        ctx: utils.InvestigatorContext,
        toggle: typing.Annotated[bool, lambda ctx, arg: arg == 1],
    ):
        await ctx.defer()

        guild_config = await ctx.fetch_config()
        if (
            not guild_config.bullets_enabled and toggle
        ):  # if truth bullets will be enabled by this
            self.enable_check(guild_config)

        guild_config.bullets_enabled = toggle
        await guild_config.save()

        await ctx.message.reply(
            "Truth Bullets turned"
            f" {utils.toggle_friendly_str(guild_config.bullets_enabled)}!"
        )


def setup(bot):
    importlib.reload(utils)
    BulletConfigCMDs(bot)
