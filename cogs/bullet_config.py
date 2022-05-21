import importlib
import typing

import dis_snek
import molter

import common.models as models
import common.utils as utils


class BulletConfigCMDs(utils.Scale):
    """Commands for using and modifying Truth Bullet server settings."""

    def __init__(self, bot):
        self.display_name = "Bullet Config"
        self.bot = bot

    def truth_bullet_managers(self, guild_config: models.Config):
        role_str_builder = []
        if guild_config.bullet_default_perms_check:
            role_str_builder.append("Members with `Manage Server` permissions")

        role_str_builder.extend(
            f"<@&{role_id}>" for role_id in guild_config.bullet_custom_perm_roles
        )

        return f"Can Manage Truth Bullets: {', '.join(role_str_builder)}"

    @molter.msg_command(aliases=["bull_config", "bullconfig"])
    @utils.bullet_proper_perms()
    async def bullet_config(self, ctx: dis_snek.MessageContext):
        """Lists out the Truth Bullet configuration settings for the server.
        Requires being able to Manage Truth Bullets."""
        # sourcery skip: merge-list-append

        await ctx.channel.trigger_typing()

        guild_config = await utils.create_and_or_get(
            ctx.bot, ctx.guild.id, ctx.message.id
        )

        str_builder = list(
            (
                "Truth Bullets:"
                f" {utils.toggle_friendly_str(guild_config.bullets_enabled)}",
                "Truth Bullet channel:"
                f" {f'<#{guild_config.bullet_chan_id}>' if guild_config.bullet_chan_id > 0 else 'None'}",
            )
        )

        str_builder.append("")
        str_builder.append(
            "Player role:"
            f" {f'<@&{guild_config.player_role}>' if guild_config.player_role > 0 else 'None'}"
        )
        str_builder.append(
            "Best Detective role:"
            f" {f'<@&{guild_config.ult_detective_role}>' if guild_config.ult_detective_role > 0 else 'None'}"
        )

        str_builder.append(self.truth_bullet_managers(guild_config))

        embed = dis_snek.Embed(
            title=f"Server config for {ctx.guild.name}",
            description="\n".join(str_builder),
            color=14232643,
        )
        await ctx.message.reply(embed=embed)

    @molter.msg_command(aliases=["set_bull_chan", "set_bullets_channel"])
    @utils.bullet_proper_perms()
    async def set_bullet_channel(
        self,
        ctx: dis_snek.MessageContext,
        channel: typing.Annotated[dis_snek.GuildText, utils.ValidChannelConverter],
    ):
        """Sets where all Truth Bullets are sent to (alongside the channel they were found in).
        The channel could be its mention, its ID, or its name.
        Requires being able to Manage Truth Bullets."""

        await ctx.channel.trigger_typing()

        guild_config = await utils.create_and_or_get(
            ctx.bot, ctx.guild.id, ctx.message.id
        )
        guild_config.bullet_chan_id = channel.id
        await guild_config.save()

        await ctx.message.reply(f"Truth Bullet channel set to {channel.mention}!")

    class CheckForNone(molter.Converter):
        async def convert(self, ctx: dis_snek.MessageContext, argument: str):
            if argument.lower() == "none":
                return dis_snek.SnowflakeObject(  # type: ignore
                    0
                )  # little hack so we don't have to do as much instance checking
            raise molter.BadArgument("Not 'none'!")

    @molter.msg_command(
        aliases=[
            "set_ult_detect_role",
            "set_ult_detective_role",
            "set_ult_detect",
            "set_ult_detective",
            "set_ultimate_detective_role",
            "set_best_detect_role",
            "set_best_detect",
        ]
    )
    @utils.bullet_proper_perms()
    async def set_best_detective_role(
        self,
        ctx: dis_snek.MessageContext,
        role: typing.Union[dis_snek.Role, CheckForNone],
    ):
        """Sets (or unsets) the Best Detective role.
        The 'Best Detective' is the person who found the most Truth Bullets during an investigation.
        Either specify a role (mention/ID/name in quotes) to set it, or 'none' to unset it.
        The role must be one the bot can edit.
        Requires being able to Manage Truth Bullets."""

        # we do this because union error messages are vague and wouldn't work
        if isinstance(role, dis_snek.Role):
            utils.role_check(ctx, role)

        await ctx.channel.trigger_typing()

        guild_config = await utils.create_and_or_get(
            ctx.bot, ctx.guild.id, ctx.message.id
        )
        guild_config.ult_detective_role = role.id
        await guild_config.save()

        if isinstance(role, dis_snek.Role):
            await ctx.message.reply(
                f"Best Detective role set to {role.mention}!",
                allowed_mentions=utils.deny_mentions(ctx.author),
            )
        else:
            await ctx.message.reply("Best Detective role unset!")

    @molter.msg_command()
    @utils.bullet_proper_perms()
    async def set_player_role(self, ctx: dis_snek.MessageContext, role: dis_snek.Role):
        """Sets the Player role.
        The Player role can actually find the Truth Bullets themself.
        The role could be its mention, its ID, or its name in quotes.
        Requires being able to Manage Truth Bullets."""

        await ctx.channel.trigger_typing()

        guild_config = await utils.create_and_or_get(
            ctx.bot, ctx.guild.id, ctx.message.id
        )
        guild_config.player_role = role.id
        await guild_config.save()

        await ctx.message.reply(
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

    @molter.msg_command(aliases=["toggle_bullet"])
    @utils.bullet_proper_perms()
    async def toggle_bullets(self, ctx: dis_snek.MessageContext):
        """Turns on or off the Truth Bullets, depending on what it was earlier.
        It will turn the Truth Bullets off if they're on, or on if they're off.
        To turn on Truth Bullets, you need to set the Player role and the Truth Bullets channel.
        Requires being able to Manage Truth Bullets."""

        await ctx.channel.trigger_typing()

        guild_config = await utils.create_and_or_get(
            ctx.bot, ctx.guild.id, ctx.message.id
        )
        if not guild_config.bullets_enabled:  # if truth bullets will be enabled by this
            self.enable_check(guild_config)
        guild_config.bullets_enabled = not guild_config.bullets_enabled
        await guild_config.save()

        await ctx.message.reply(
            "Truth Bullets turned"
            f" {utils.toggle_friendly_str(guild_config.bullets_enabled)}!"
        )

    @molter.msg_command(aliases=["enable_bullet"])
    @utils.bullet_proper_perms()
    async def enable_bullets(self, ctx: dis_snek.MessageContext):
        """Turns on the Truth Bullets.
        Kept around to match up with the old YAGPDB system.
        To turn on Truth Bullets, you need to set the Player role and the Truth Bullets channel.
        Requires being able to Manage Truth Bullets."""

        await ctx.channel.trigger_typing()

        guild_config = await utils.create_and_or_get(
            ctx.bot, ctx.guild.id, ctx.message.id
        )
        self.enable_check(guild_config)
        guild_config.bullets_enabled = True
        await guild_config.save()

        await ctx.message.reply("Truth Bullets enabled!")

    @molter.msg_command(aliases=["disable_bullet"])
    @utils.bullet_proper_perms()
    async def disable_bullets(self, ctx: dis_snek.MessageContext):
        """Turns off the Truth Bullets.
        Kept around to match up with the old YAGPDB system.
        This is automatically done after all Truth Bullets have been found.
        Requires being able to Manage Truth Bullets."""

        await ctx.channel.trigger_typing()

        guild_config = await utils.create_and_or_get(
            ctx.bot, ctx.guild.id, ctx.message.id
        )
        guild_config.bullets_enabled = False
        await guild_config.save()

        await ctx.message.reply("Truth Bullets disabled!")

    @molter.msg_command(
        aliases=["bull_perms", "bullet_perms", "bull_perm", "bullet_perm"],
        ignore_extra=False,
    )
    @utils.proper_permissions()
    async def bullet_permissions(self, ctx: dis_snek.MessageContext):
        """The base command for determining who can Manage Truth Bullets.
        Use the help command on this in order to see your options.
        All commands here require Manage Guild permissions."""

        await ctx.channel.trigger_typing()
        guild_config = await utils.create_and_or_get(
            ctx.bot, ctx.guild.id, ctx.message.id
        )

        await ctx.reply(
            self.truth_bullet_managers(guild_config),
            allowed_mentions=utils.deny_mentions(ctx.author),
        )

    @bullet_permissions.subcommand()
    @utils.proper_permissions()
    async def default(self, ctx: dis_snek.MessageContext, toggle: bool):
        """Allows you to toggle if people with Manage Guild permissions can Manage Truth Bullets.
        Technically pointless as someone with Manage Guild perms could just toggle this back on, \
        but this will be useful later.
        Requires Manage Guild permissions."""

        await ctx.channel.trigger_typing()
        guild_config = await utils.create_and_or_get(
            ctx.bot, ctx.guild.id, ctx.message.id
        )
        guild_config.bullet_default_perms_check = toggle
        await guild_config.save()

        toggle_str = "can" if toggle else "cannot"
        await ctx.reply(
            f"People with Manage Server permissions now {toggle_str} use Truth Bullet"
            " commands."
        )

    @bullet_permissions.subcommand()
    @utils.proper_permissions()
    async def add(self, ctx: dis_snek.MessageContext, role: dis_snek.Role):
        """Adds a role to the roles that can Manage Truth Bullets.
        Requires Manage Guild permissions."""

        await ctx.channel.trigger_typing()
        guild_config = await utils.create_and_or_get(
            ctx.bot, ctx.guild.id, ctx.message.id
        )

        if role.id in guild_config.bullet_custom_perm_roles:
            raise molter.BadArgument(
                "This role is already allowed to Manage Truth Bullets!"
            )

        guild_config.bullet_custom_perm_roles.add(role.id)
        await guild_config.save()

        await ctx.reply(
            f"{role.mention} can now Manage Truth Bullets.",
            allowed_mentions=utils.deny_mentions(ctx.author),
        )

    @bullet_permissions.subcommand()
    @utils.proper_permissions()
    async def remove(self, ctx: dis_snek.MessageContext, role: dis_snek.Role):
        """Removes a role from the roles that can Manage Truth Bullets.
        Requires Manage Guild permissions."""

        await ctx.channel.trigger_typing()
        guild_config = await utils.create_and_or_get(
            ctx.bot, ctx.guild.id, ctx.message.id
        )

        try:
            guild_config.bullet_custom_perm_roles.remove(role.id)
            await guild_config.save()
        except KeyError:
            raise molter.BadArgument(
                "This role is already not allowed to Manage Truth Bullets!"
            )

        await ctx.reply(
            f"{role.mention} can no longer Manage Truth Bullets.",
            allowed_mentions=utils.deny_mentions(ctx.author),
        )


def setup(bot):
    importlib.reload(utils)
    BulletConfigCMDs(bot)
