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
from discord.ext import commands

import common.models as models
import common.utils as utils


class ConfigCMDs(utils.Cog):
    def __init__(self, bot: utils.THIABase) -> None:
        self.bot = bot
        self.__cog_name__ = "Config"

    config = ragwort.SlashCommandGroup(
        name="config",
        description="Handles configuration of general bot settings.",
        default_member_permissions=discord.Permissions(manage_guild=True),
    )

    @config.command(
        name="info",
        description="Lists out the general configuration settings for the server.",
    )
    async def general_config(self, ctx: utils.THIASlashContext) -> None:
        config = await ctx.fetch_config()

        only_option_rn = (
            "Player role:"
            f" {f'<@&{config.player_role}>' if config.player_role else 'N/A'}\nBeta"
            f" enabled: {utils.yesno_friendly_str(config.enabled_beta)}\n\n*Looking a"
            " bit empty? This is the general configuration display - check out the"
            " other config commands for more of your configuration.*"
        )
        await ctx.respond(
            view=utils.make_view(only_option_rn, title="General Configuration")
        )

    player_config = config.create_subgroup(
        name="player",
        description="Commands for configuring player-related settings.",
    )

    @player_config.command(
        name="set",
        description="Sets the Player role.",
    )
    async def set_player_role(
        self,
        ctx: utils.THIASlashContext,
        role: discord.Role = ragwort.Option("The Player role to use."),
    ) -> None:
        config = await ctx.fetch_config()
        config.player_role = role.id
        await config.save()

        await ctx.respond(
            view=utils.make_view(f"Player role set to {role.mention}!"),
        )

    @player_config.command(
        name="unset",
        description="Unsets the Player role.",
    )
    async def unset_player_role(self, ctx: utils.THIASlashContext) -> None:
        config = await ctx.fetch_config()
        config.player_role = None
        await config.save()

        await ctx.respond(view=utils.make_view("Player role unset."))

    @config.command(
        name="beta",
        description="Toggles beta features for this server.",
    )
    async def toggle_beta_features(
        self,
        ctx: utils.THIASlashContext,
        _toggle: str = ragwort.Option(
            "Whether to turn beta features on or off.",
            name="toggle",
            choices=[
                discord.OptionChoice("on", "on"),
                discord.OptionChoice("off", "off"),
            ],
        ),
    ) -> None:
        toggle = _toggle == "on"

        guild_config = await ctx.fetch_config()
        guild_config.enabled_beta = toggle
        await guild_config.save()

        if toggle:
            await ctx.respond(
                view=utils.make_view("Beta features have been turned on!")
            )
        else:
            await ctx.respond(
                view=utils.make_view("Beta features have been turned off.")
            )

    @config.command(
        name="clear-all-data",
        description="Clears all bot data for this server. Use with caution!",
    )
    @ragwort.auto_defer(enabled=False)
    async def clear_all_data(
        self,
        ctx: utils.THIASlashContext,
        confirm: bool = ragwort.Option(
            "Actually clear? Set this to true if you're sure.", default=False
        ),
    ) -> None:
        if not confirm:
            raise commands.BadArgument(
                "Confirm option not set to true. Please set the option `confirm` to"
                " true to continue."
            )

        await ctx.send_modal(
            utils.quick_model(
                discord.ui.Label(
                    label="Type 'Clear all data.' to confirm.",
                    description=(
                        "'Clear all data.' is case-sensitive. Do not put the quotes."
                    ),
                    item=discord.ui.InputText(
                        style=discord.InputTextStyle.short,
                        custom_id="confirm_input",
                        min_length=15,
                        max_length=15,
                        required=True,
                    ),
                ),
                title="Confirm Clear All Data",
                custom_id="thia:clear-all-data-modal",
            )
        )

    @utils.modal_handler(custom_id="thia:clear-all-data-modal")
    async def clear_all_data_modal_callback(
        self, inter: utils.Interaction, responses: dict[str, typing.Any]
    ) -> None:
        await inter.response.defer()

        confirm_input: str = responses["confirm_input"]

        if confirm_input != "Clear all data.":
            raise commands.BadArgument("Confirmation input did not match.")

        await models.GuildConfig.filter(guild_id=int(inter.guild_id)).delete()
        await models.TruthBullet.filter(guild_id=int(inter.guild_id)).delete()

        await inter.followup.send(
            view=utils.make_view(
                title="Data Cleared",
                description="All data for this server has been cleared.",
            )
        )

    @config.command(
        name="help",
        description="Tells you how to set up this bot.",
    )
    async def setup_help(
        self,
        ctx: utils.THIASlashContext,
    ) -> None:
        container = utils.make_container(
            title="Setup Bot",
            description="To set up this bot, follow the Server Setup Guides below.",
        )
        container.add_separator(divider=False)
        container.add_row(
            discord.ui.Button(
                style=discord.ButtonStyle.url,
                label="Server Setup Guides",
                url="https://pythia.astrea.cc/setup",
            ),
        )
        await ctx.respond(view=utils.quick_view(container))


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    bot.add_cog(ConfigCMDs(bot))
