"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import importlib

import discord
import ragwort
import typing_extensions as typing

import common.models as models
import common.utils as utils


class EditBulletNamesModal(discord.ui.DesignerModal):
    def __init__(self, names: models.Names) -> None:
        super().__init__(
            discord.ui.Label(
                label="Singular Bullet Name",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="singular_name",
                    value=names.singular_bullet,
                    max_length=40,
                ),
            ),
            discord.ui.Label(
                label="Plural Bullet Name",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="plural_name",
                    value=names.plural_bullet,
                    max_length=40,
                ),
            ),
            title="Edit Truth Bullet Names",
            custom_id="bullet_names",
        )

    async def callback(self, inter: utils.Interaction) -> None:
        await inter.response.defer()

        config = await models.GuildConfig.fetch_create(inter.guild_id, {"names": True})
        if typing.TYPE_CHECKING:
            assert config.names and isinstance(config.names, models.Names)
        names = config.names

        names.singular_bullet = self.children[0].item.value
        names.plural_bullet = self.children[1].item.value
        await names.save()

        await inter.respond(
            view=utils.make_view(
                "Updated! Please note this will only affect public-facing aspects - IE"
                f" finding items.\nSingular: {names.singular_bullet}\nPlural:"
                f" {names.plural_bullet}"
            )
        )


class EditBulletFinderNamesModal(discord.ui.DesignerModal):
    def __init__(self, names: models.Names) -> None:
        super().__init__(
            discord.ui.Label(
                label="Singular Truth Bullet Finder",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="singular_truth_bullet_finder",
                    value=names.singular_truth_bullet_finder,
                    max_length=70,
                ),
            ),
            discord.ui.Label(
                label="Plural Truth Bullet Finder",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="plural_truth_bullet_finder",
                    value=names.plural_truth_bullet_finder,
                    max_length=70,
                ),
            ),
            discord.ui.Label(
                label="Best Bullet Finder Name",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="best_bullet_finder",
                    value=names.best_bullet_finder,
                    max_length=70,
                ),
            ),
            title="Edit Truth Bullet Finder Names",
            custom_id="bullet_finders",
        )

    async def callback(self, inter: utils.Interaction) -> None:
        await inter.response.defer()

        config = await models.GuildConfig.fetch_create(inter.guild_id, {"names": True})
        if typing.TYPE_CHECKING:
            assert config.names and isinstance(config.names, models.Names)
        names = config.names

        singular_truth_bullet_finder: str = self.children[0].item.value
        plural_truth_bullet_finder: str = self.children[1].item.value
        best_bullet_finder: str = self.children[2].item.value

        if (
            var_name := models.TEMPLATE_MARKDOWN.search(singular_truth_bullet_finder)
        ) and var_name.group(2) != "bullet_name":
            raise utils.BadArgument(
                "Invalid variable name in Singular Truth Bullet Finder. Only"
                " `{{bullet_name}}`, the Truth Bullet name, is allowed."
            )

        if (
            var_name := models.TEMPLATE_MARKDOWN.search(plural_truth_bullet_finder)
        ) and var_name.group(2) != "bullet_name":
            raise utils.BadArgument(
                "Invalid variable name in Plural Truth Bullet Finder. Only"
                " `{{bullet_name}}`, the Truth Bullet name, is allowed."
            )

        if (
            var_name := models.TEMPLATE_MARKDOWN.search(best_bullet_finder)
        ) and var_name.group(2) != "bullet_finder":
            raise utils.BadArgument(
                "Invalid variable name in Best Truth Bullet Finder. Only"
                " `{{bullet_finder}}`, the Truth Bullet Finder name, is allowed."
            )

        names.singular_truth_bullet_finder = singular_truth_bullet_finder
        names.plural_truth_bullet_finder = plural_truth_bullet_finder
        names.best_bullet_finder = best_bullet_finder
        await names.save()

        await inter.respond(
            view=utils.make_view(
                "Updated! Please note this will only affect public-facing aspects - IE"
                " finding all items.\nSingular Finder:"
                f" {models.code_template(names.singular_truth_bullet_finder)}\nPlural"
                " Finders:"
                f" {models.code_template(names.plural_truth_bullet_finder)}\nBest"
                f" Finder: {models.code_template(names.best_bullet_finder)}\n\n*Note:"
                " anything in `{}` is a field to be replaced dynamically by the"
                " appropriate value.*",
            )
        )


class BulletConfigCMDs(utils.Cog):
    """Commands for using and modifying BDA investigation server settings."""

    def __init__(self, bot: utils.THIABase) -> None:
        self.bot = bot
        self.__cog_name__ = "BDA Investigation Config"

    config = ragwort.SlashCommandGroup(
        name="bullet-config",
        description="Handles configuration of BDA investigation.",
        default_member_permissions=discord.Permissions(manage_guild=True),
        contexts={
            discord.InteractionContextType.guild,
        },
    )

    @config.command(
        name="info",
        description=(
            "Lists out the BDA investigation configuration settings for the server."
        ),
    )
    async def bullet_config(self, ctx: utils.THIASlashContext) -> None:
        config = await ctx.fetch_config({"bullets": True, "names": True})
        if typing.TYPE_CHECKING:
            assert config.bullets and isinstance(config.bullets, models.BulletConfig)
            assert config.names and isinstance(config.names, models.Names)

        str_builder = [
            (
                "Player role:"
                f" {f'<@&{config.player_role}>' if config.player_role else 'N/A'}"
            ),
            (
                "Truth Bullets active:"
                f" {utils.yesno_friendly_str(config.bullets.bullets_enabled)}"
            ),
            (
                "Truth Bullet channel:"
                f" {f'<#{config.bullets.bullet_chan_id}>' if config.bullets.bullet_chan_id else 'N/A'}"
            ),
            (
                "BDA Investigation mode:"
                f" {config.bullets.investigation_type_enum.name.replace('_', ' ').title()}"
            ),
            f"Thread behavior: {config.bullets.thread_behavior_desc}",
            (
                "Best Truth Bullet Finder role:"
                f" {f'<@&{config.bullets.best_bullet_finder_role}>' if config.bullets.best_bullet_finder_role else 'N/A'}"
            ),
            (
                "Announce Best Truth Bullet Finders at end:"
                f" {utils.yesno_friendly_str(config.bullets.show_best_finders)}"
            ),
        ]

        embed = discord.Embed(
            description=f"# BDA investigation config for {ctx.guild.name}"
            + "\n".join(str_builder),
            color=utils.BOT_COLOR,
        )

        names_builder: list[str] = [
            (
                f"Singular Truth Bullet: {config.names.singular_bullet}\nPlural Truth"
                f" Bullet: {config.names.plural_bullet}\nSingular Truth Bullet Finder:"
                f" {models.code_template(config.names.singular_truth_bullet_finder)}\nPlural"
                " Truth Bullet Finder:"
                f" {models.code_template(config.names.plural_truth_bullet_finder)}\nBest"
                " Truth Bullet Finder:"
                f" {models.code_template(config.names.best_bullet_finder)}"
            ),
            (
                "*Note: anything in `{{}}` is a field to be replaced dynamically by the"
                " appropriate value.*"
            ),
        ]
        embed.add_field(name="Names", value="\n".join(names_builder), inline=True)
        await ctx.respond(embed=embed)

    channel_config = config.create_subgroup(
        name="channel",
        description="Commands for configuring BDA investigation channel settings.",
    )

    @channel_config.command(
        name="set",
        description="Sets the channel where all Truth Bullets are sent to.",
    )
    async def set_bullet_channel(
        self,
        ctx: utils.THIASlashContext,
        channel: discord.TextChannel | discord.Thread = ragwort.Option(
            "The channel to send Truth Bullets to.",
            channel_types=[
                discord.ChannelType.text,
                discord.ChannelType.public_thread,
                discord.ChannelType.private_thread,
            ],
        ),
    ) -> None:
        channel = utils.valid_channel_check(
            channel, channel.permissions_for(ctx.guild.me)
        )

        config = await ctx.fetch_config({"bullets": True})
        if typing.TYPE_CHECKING:
            assert config.bullets and isinstance(config.bullets, models.BulletConfig)

        config.bullets.bullet_chan_id = channel.id
        await config.bullets.save()

        await ctx.respond(
            view=utils.make_view(f"Truth Bullet channel set to {channel.mention}!")
        )

    @channel_config.command(
        name="unset",
        description="Unsets the channel where all Truth Bullets are sent to.",
    )
    async def unset_bullet_channel(self, ctx: utils.THIASlashContext) -> None:
        config = await ctx.fetch_config({"bullets": True})
        if typing.TYPE_CHECKING:
            assert config.bullets and isinstance(config.bullets, models.BulletConfig)

        config.bullets.bullet_chan_id = None
        await config.bullets.save()

        await ctx.respond(view=utils.make_view("Truth Bullet channel unset."))

    best_finder_config = config.create_subgroup(
        name="best-finder",
        description="Commands for configuring the Best Truth Bullet Finder role.",
    )

    @best_finder_config.command(
        name="set",
        description="Sets the Best Truth Bullet Finder role.",
    )
    async def set_best_truth_bullet_finder_role(
        self,
        ctx: utils.THIASlashContext,
        role: discord.Role = ragwort.Option(
            "The Best Detective role to use.",
        ),
    ) -> None:
        role = utils.role_check(ctx, role)

        config = await ctx.fetch_config({"bullets": True})
        if typing.TYPE_CHECKING:
            assert config.bullets and isinstance(config.bullets, models.BulletConfig)

        config.bullets.best_bullet_finder_role = role.id
        await config.bullets.save()

        await ctx.respond(
            view=utils.make_view(
                f"Best Truth Bullet Finder role set to {role.mention}!"
            ),
        )

    @best_finder_config.command(
        name="unset",
        description="Unsets the Best Truth Bullet Finder role.",
    )
    async def unset_best_truth_bullet_finder_role(
        self, ctx: utils.THIASlashContext
    ) -> None:
        config = await ctx.fetch_config({"bullets": True})
        if typing.TYPE_CHECKING:
            assert config.bullets and isinstance(config.bullets, models.BulletConfig)

        config.bullets.best_bullet_finder_role = None
        await config.bullets.save()

        await ctx.respond(view=utils.make_view("Best Truth Bullet Finder role unset."))

    @config.command(
        name="mode",
        description="Change the BDA investigation mode.",
    )
    async def set_investigation_mode(
        self,
        ctx: utils.THIASlashContext,
        mode: int = ragwort.Option(
            "The investigation mode to set.",
            choices=[
                discord.OptionChoice("Default", models.InvestigationType.DEFAULT),
                discord.OptionChoice(
                    "/bda-investigate command only",
                    models.InvestigationType.COMMAND_ONLY,
                ),
            ],
        ),
    ) -> None:
        try:
            investigation_type = models.InvestigationType(mode)
        except ValueError:
            raise utils.BadArgument("Invalid investigation mode.") from None

        config = await ctx.fetch_config({"bullets": True})
        if typing.TYPE_CHECKING:
            assert config.bullets and isinstance(config.bullets, models.BulletConfig)

        config.bullets.investigation_type = investigation_type
        await config.bullets.save()

        if investigation_type == models.InvestigationType.COMMAND_ONLY:
            self.bot.msg_enabled_bullets_guilds.discard(int(ctx.guild.id))
        elif config.bullets.bullets_enabled:
            self.bot.msg_enabled_bullets_guilds.add(int(ctx.guild.id))

        await ctx.respond(
            view=utils.make_view(
                "BDA investigation mode now set to"
                f" {config.bullets.investigation_type.name.replace('_', ' ').title()}."
            )
        )

    @config.command(
        name="thread-behavior",
        description=(
            "Change how Truth Bullets in threads behave in relation to their parent"
            " channel."
        ),
    )
    async def set_thread_behavior(
        self,
        ctx: utils.THIASlashContext,
        behavior: int = ragwort.Option(
            "The thread behavior to set.",
            choices=[
                discord.OptionChoice(
                    "Distinct entity from parent channel",
                    models.BulletThreadBehavior.DISTINCT,
                ),
                discord.OptionChoice(
                    "Treated as the parent channel", models.BulletThreadBehavior.PARENT
                ),
            ],
        ),
    ) -> None:
        try:
            thread_behavior = models.BulletThreadBehavior(behavior)
        except ValueError:
            raise utils.BadArgument("Invalid thread behavior.") from None

        config = await ctx.fetch_config({"bullets": True})
        if typing.TYPE_CHECKING:
            assert config.bullets and isinstance(config.bullets, models.BulletConfig)

        config.bullets.thread_behavior = thread_behavior
        await config.bullets.save()

        await ctx.respond(
            view=utils.make_view(
                f"Thread behavior now set to: {config.bullets.thread_behavior_desc}."
            )
        )

    @config.command(
        name="announce-best-finders",
        description=(
            "Toggle whether to announce the Best Truth Bullet Finders at the end of a"
            " BDA investigation."
        ),
    )
    async def set_announce_best_finders(
        self,
        ctx: utils.THIASlashContext,
        _toggle: str = ragwort.Option(
            "Should the Best Truth Bullet Finders be announced at the end of a BDA"
            " investigation?",
            name="toggle",
            choices=[
                discord.OptionChoice("yes", "yes"),
                discord.OptionChoice("no", "no"),
            ],
        ),
    ) -> None:
        toggle = _toggle == "yes"

        config = await ctx.fetch_config({"bullets": True})
        if typing.TYPE_CHECKING:
            assert config.bullets and isinstance(config.bullets, models.BulletConfig)

        config.bullets.show_best_finders = toggle
        await config.bullets.save()

        if toggle:
            await ctx.respond(
                view=utils.make_view(
                    "The bot will now announce Best Truth Bullet Finders at the end of"
                    " a BDA investigation."
                )
            )
        else:
            await ctx.respond(
                view=utils.make_view(
                    "The bot will no longer announce Best Truth Bullet Finders at the"
                    " end of a BDA investigation."
                )
            )

    @config.command(
        name="names",
        description=(
            "Edit the displayed names used for various parts of BDA investigations."
        ),
    )
    @ragwort.auto_defer(enabled=False)
    async def edit_names(
        self,
        ctx: utils.THIASlashContext,
        to_change: str = ragwort.Option(
            "The names to change.",
            choices=[
                discord.OptionChoice("Truth Bullet Names", "bullet_names"),
                discord.OptionChoice("Truth Bullet Finders", "bullet_finders"),
            ],
        ),
    ) -> None:
        if to_change not in {"bullet_names", "bullet_finders"}:
            raise utils.BadArgument("Invalid change requested!")

        config = await ctx.fetch_config({"names": True})
        if typing.TYPE_CHECKING:
            assert config.names and isinstance(config.names, models.Names)
        names = config.names

        if to_change == "bullet_names":
            modal = EditBulletNamesModal(names)
        else:
            modal = EditBulletFinderNamesModal(names)

        await ctx.send_modal(modal)

    def enable_check(self, config: models.GuildConfig) -> None:
        if not config.player_role:
            raise utils.CustomCheckFailure(
                "You still need to set the Player role for this server!"
            )
        elif not config.bullets or not config.bullets.bullet_chan_id:
            raise utils.CustomCheckFailure(
                "You still need to set an investigation channel!"
            )

    @config.command(
        name="toggle",
        description="Enables or disables the discovery of Truth Bullets.",
    )
    async def toggle_bullets(
        self,
        ctx: utils.THIASlashContext,
        _toggle: str = ragwort.Option(
            "Should Truth Bullets be turned on or off?",
            name="toggle",
            choices=[
                discord.OptionChoice("on", "on"),
                discord.OptionChoice("off", "off"),
            ],
        ),
    ) -> None:
        toggle = _toggle == "on"

        config = await ctx.fetch_config({"bullets": True})
        if typing.TYPE_CHECKING:
            assert config.bullets and isinstance(config.bullets, models.BulletConfig)

        if (
            not config.bullets.bullets_enabled and toggle
        ):  # if truth bullets will be enabled by this
            self.enable_check(config)

        config.bullets.bullets_enabled = toggle
        await config.bullets.save()

        if config.bullets.investigation_type != models.InvestigationType.COMMAND_ONLY:
            if toggle:
                self.bot.msg_enabled_bullets_guilds.add(int(ctx.guild.id))
            else:
                self.bot.msg_enabled_bullets_guilds.discard(int(ctx.guild.id))

        await ctx.respond(
            view=utils.make_view(
                "Truth Bullets turned"
                f" {utils.toggle_friendly_str(config.bullets.bullets_enabled)}!"
            )
        )

    @config.command(
        name="help",
        description="Tells you how to set up the BDA investigation system.",
    )
    async def bullets_help(self, ctx: utils.THIASlashContext) -> None:
        container = utils.make_container(
            "To set up the BDA investigation system, follow the BDA Investigation setup"
            " guide below.",
            title="Set Up BDA Investigation System",
        )
        container.add_separator(divider=False)
        container.add_row(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="BDA Investigation Setup Guide",
                url="https://pythia.astrea.cc/setup/bda_investigations_setup",
            )
        )
        await ctx.respond(view=utils.quick_view(container))


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    bot.add_cog(BulletConfigCMDs(bot))
