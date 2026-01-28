"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import importlib

import interactions as ipy
import tansy

import common.models as models
import common.utils as utils


class ConfigCMDs(utils.Extension):
    def __init__(self, _: utils.THIABase) -> None:
        self.name = "Config"

    config = tansy.SlashCommand(
        name="config",
        description="Handles configuration of general bot settings.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @config.subcommand(
        sub_cmd_name="info",
        sub_cmd_description=(
            "Lists out the general configuration settings for the server."
        ),
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
        await ctx.send(
            embed=utils.make_embed(only_option_rn, title="General Configuration")
        )

    player_config = config.group(
        name="player",
        description="Commands for configuring player-related settings.",
    )

    @player_config.subcommand(
        sub_cmd_name="set",
        sub_cmd_description="Sets the Player role.",
    )
    async def set_player_role(
        self,
        ctx: utils.THIASlashContext,
        role: ipy.Role = tansy.Option("The Player role to use."),
    ) -> None:
        config = await ctx.fetch_config()
        config.player_role = role.id
        await config.save()

        await ctx.send(
            embed=utils.make_embed(f"Player role set to {role.mention}!"),
        )

    @player_config.subcommand(
        sub_cmd_name="unset",
        sub_cmd_description="Unsets the Player role.",
    )
    async def unset_player_role(self, ctx: utils.THIASlashContext) -> None:
        config = await ctx.fetch_config()
        config.player_role = None
        await config.save()

        await ctx.send(embed=utils.make_embed("Player role unset."))

    @config.subcommand(
        sub_cmd_name="beta",
        sub_cmd_description="Toggles beta features for this server.",
    )
    async def toggle_beta_features(
        self,
        ctx: utils.THIASlashContext,
        _toggle: str = tansy.Option(
            "Whether to turn beta features on or off.",
            name="toggle",
            choices=[
                ipy.SlashCommandChoice("on", "on"),
                ipy.SlashCommandChoice("off", "off"),
            ],
        ),
    ) -> None:
        toggle = _toggle == "on"

        guild_config = await ctx.fetch_config()
        guild_config.enabled_beta = toggle
        await guild_config.save()

        if toggle:
            await ctx.send(
                embed=utils.make_embed(
                    "Beta features have been turned on! These features may break"
                    " compatibility with old Discord mobile clients, so be careful."
                )
            )
        else:
            await ctx.send(
                embed=utils.make_embed("Beta features have been turned off.")
            )

    @config.subcommand(
        sub_cmd_name="clear-all-data",
        sub_cmd_description="Clears all bot data for this server. Use with caution!",
    )
    @ipy.auto_defer(enabled=False)
    async def clear_all_data(
        self,
        ctx: utils.THIASlashContext,
        confirm: bool = tansy.Option(
            "Actually clear? Set this to true if you're sure.", default=False
        ),
    ) -> None:
        if not confirm:
            raise ipy.errors.BadArgument(
                "Confirm option not set to true. Please set the option `confirm` to"
                " true to continue."
            )

        await ctx.send_modal(
            ipy.Modal(
                ipy.InputText(
                    label="Type 'Clear all data.' to confirm.",
                    custom_id="confirm_input",
                    style=ipy.TextStyles.SHORT,
                    required=True,
                    min_length=15,
                    max_length=15,
                    placeholder=(
                        "'Clear all data.' is case-sensitive. Do not put the quotes."
                    ),
                ),
                title="Confirm Clear All Data",
                custom_id="thia:clear-all-data-modal",
            )
        )

    @ipy.modal_callback("thia:clear-all-data-modal")
    async def clear_all_data_modal_callback(self, ctx: utils.THIAModalContext) -> None:
        confirm_input = ctx.responses["confirm_input"]

        if confirm_input != "Clear all data.":
            raise ipy.errors.BadArgument("Confirmation input did not match.")

        await models.GuildConfig.filter(guild_id=int(ctx.guild_id)).delete()
        await models.TruthBullet.filter(guild_id=int(ctx.guild_id)).delete()

        await ctx.send(
            embed=utils.make_embed(
                "All data for this server has been cleared.", title="Data Cleared"
            )
        )

    @config.subcommand(
        sub_cmd_name="help",
        sub_cmd_description="Tells you how to set up this bot.",
    )
    async def setup_help(
        self,
        ctx: utils.THIASlashContext,
    ) -> None:
        embed = utils.make_embed(
            "To set up this bot, follow the Server Setup Guides below.",
            title="Setup Bot",
        )
        button = ipy.Button(
            style=ipy.ButtonStyle.LINK,
            label="Server Setup Guides",
            url="https://pythia.astrea.cc/setup",
        )
        await ctx.send(embeds=embed, components=button)


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    ConfigCMDs(bot)
