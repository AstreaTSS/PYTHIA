"""
Copyright 2022-2024 AstreaTSS.
This file is part of Ultimate Investigator.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import importlib
import typing

import interactions as ipy
import tansy

import common.models as models
import common.utils as utils


class BulletConfigCMDs(utils.Extension):
    """Commands for using and modifying Truth Bullet server settings."""

    def __init__(self, bot: utils.UIBase) -> None:
        self.name = "Bullet Config"
        self.bot: utils.UIBase = bot

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
    async def bullet_config(self, ctx: utils.UIInteractionContext) -> None:
        guild_config = await ctx.fetch_config()

        str_builder = [
            f"Truth Bullets: {utils.toggle_friendly_str(guild_config.bullets_enabled)}",
            (
                "Truth Bullet channel:"
                f" {f'<#{guild_config.bullet_chan_id}>' if guild_config.bullet_chan_id else 'N/A'}"
            ),
            "",
        ]

        str_builder.extend((
            (
                "Player role:"
                f" {f'<@&{guild_config.player_role}>' if guild_config.player_role else 'N/A'}"
            ),
            (
                "Best Truth Bullet Finder role:"
                f" {f'<@&{guild_config.ult_detective_role}>' if guild_config.ult_detective_role else 'N/A'}"
            ),
        ))
        embed = utils.make_embed(
            title=f"Server config for {ctx.guild.name}",
            description="\n".join(str_builder),
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
    ) -> None:
        if not (bool(channel) ^ unset):
            raise ipy.errors.BadArgument(
                "You must set a Truth Bullet channel or specify to unset it."
            )

        guild_config = await ctx.fetch_config()

        guild_config.bullet_chan_id = channel.id if channel else None
        await guild_config.save()

        if channel:
            await ctx.send(
                embed=utils.make_embed(
                    f"Truth Bullet channel set to {channel.mention}!"
                )
            )
        else:
            await ctx.send(embed=utils.make_embed("Truth Bullet channel unset."))

    @config.subcommand(
        sub_cmd_name="best-truth-bullet-finder",
        sub_cmd_description="Sets (or unsets) the Best Truth Bullet Finder role.",
    )
    async def set_best_truth_bullet_finder_role(
        self,
        ctx: utils.UIInteractionContext,
        role: typing.Optional[ipy.Role] = tansy.Option(
            "The Best Detective role to use.",
            converter=utils.ValidRoleConverter,
            default=None,
        ),
        unset: bool = tansy.Option("Should the role be unset?", default=False),
    ) -> None:
        if not (bool(role) ^ unset):
            raise ipy.errors.BadArgument(
                "You must either specify a role or specify to unset the role."
            )

        guild_config = await ctx.fetch_config()
        guild_config.ult_detective_role = role.id if role else None
        await guild_config.save()

        if role:
            await ctx.send(
                embed=utils.make_embed(
                    f"Best Truth Bullet Finder role set to {role.mention}!"
                ),
            )
        else:
            await ctx.send(
                embed=utils.make_embed("Best Truth Bullet Finder role unset.")
            )

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
    ) -> None:
        if not (bool(role) ^ unset):
            raise ipy.errors.BadArgument(
                "You must either specify a role or specify to unset the role."
            )

        guild_config = await ctx.fetch_config()
        guild_config.player_role = role.id if role else None
        await guild_config.save()

        if role:
            await ctx.send(
                embed=utils.make_embed(f"Player role set to {role.mention}!"),
            )
        else:
            await ctx.send(embed=utils.make_embed("Player role unset."))

    def enable_check(self, config: models.Config) -> None:
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
    ) -> None:
        guild_config = await ctx.fetch_config()
        if (
            not guild_config.bullets_enabled and toggle
        ):  # if truth bullets will be enabled by this
            self.enable_check(guild_config)

        guild_config.bullets_enabled = toggle
        await guild_config.save()

        await ctx.send(
            embed=utils.make_embed(
                "Truth Bullets turned"
                f" {utils.toggle_friendly_str(guild_config.bullets_enabled)}!"
            )
        )

    @config.subcommand(
        sub_cmd_name="help",
        sub_cmd_description="Tells you how to set up this bot.",
    )
    async def setup_help(
        self,
        ctx: utils.UISlashContext,
    ) -> None:
        embed = utils.make_embed(
            "To set up this bot, follow the Server Setup Guide below.",
            title="Setup Bot",
        )
        button = ipy.Button(
            style=ipy.ButtonStyle.LINK,
            label="Server Setup Guide",
            url="https://ui.astrea.cc/server_setup.html",
        )
        await ctx.send(embeds=embed, components=button)


def setup(bot: utils.UIBase) -> None:
    importlib.reload(utils)
    BulletConfigCMDs(bot)
