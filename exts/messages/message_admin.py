"""
Copyright 2021-2025 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import importlib
import typing

import interactions as ipy
import tansy

import common.help_tools as help_tools
import common.models as models
import common.utils as utils


class MessageManagement(utils.Extension):
    def __init__(self, bot: utils.THIABase) -> None:
        self.name = "Messaging Management"
        self.bot: utils.THIABase = bot

    config = tansy.SlashCommand(
        name="message-config",
        description="Handles configuration of the messaging system.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @config.subcommand(
        "info",
        sub_cmd_description="Lists out the messaging system settings for the server.",
    )
    async def messages_info(self, ctx: utils.THIASlashContext) -> None:
        config = await ctx.fetch_config({"messages": True})
        if typing.TYPE_CHECKING:
            assert config.messages is not None

        str_builder = [
            f"Messaging enabled: {utils.yesno_friendly_str(config.messages.enabled)}",
            (
                "Anonymous messaging enabled:"
                f" {utils.yesno_friendly_str(config.messages.anon_enabled)}"
            ),
            (
                "Pinging on messages:"
                f" {utils.toggle_friendly_str(config.messages.ping_for_message)}"
            ),
            "",
            f"-# Links can be found at {self.message_view_links.mention()}.",
        ]

        embed = utils.make_embed(
            "\n".join(str_builder),
            title=f"Message config for {ctx.guild.name}",
        )
        await ctx.send(embed=embed)

    @config.subcommand(
        "toggle", sub_cmd_description="Enables or disables the messaging system."
    )
    async def message_toggle(
        self,
        ctx: utils.THIASlashContext,
        _toggle: str = tansy.Option(
            "Should the messaging system be turned on or off?",
            name="toggle",
            choices=[
                ipy.SlashCommandChoice("on", "on"),
                ipy.SlashCommandChoice("off", "off"),
            ],
        ),
    ) -> None:
        toggle = _toggle == "on"
        await ctx.fetch_config({"messages": True})

        await models.MessageConfig.prisma().update(
            data={"enabled": toggle}, where={"guild_id": ctx.guild_id}
        )

        await ctx.send(
            embed=utils.make_embed(
                f"Messaging system turned {utils.toggle_friendly_str(toggle)}!"
            )
        )

    @config.subcommand(
        "anonymous-messaging",
        sub_cmd_description="Enables or disables anonymous messaging.",
    )
    async def message_anon_toggle(
        self,
        ctx: utils.THIASlashContext,
        _toggle: str = tansy.Option(
            "Should anonymous messaging be turned on or off?",
            name="toggle",
            choices=[
                ipy.SlashCommandChoice("on", "on"),
                ipy.SlashCommandChoice("off", "off"),
            ],
        ),
    ) -> None:
        toggle = _toggle == "on"
        await ctx.fetch_config({"messages": True})

        await models.MessageConfig.prisma().update(
            data={"anon_enabled": toggle}, where={"guild_id": ctx.guild_id}
        )

        await ctx.send(
            embed=utils.make_embed(
                f"Anonymous messaging turned {utils.toggle_friendly_str(toggle)}!"
            )
        )

    @config.subcommand(
        "ping-on-message",
        sub_cmd_description="Enables or disables pinging on messages.",
    )
    async def message_ping_toggle(
        self,
        ctx: utils.THIASlashContext,
        _toggle: str = tansy.Option(
            "Should pinging on messages be turned on or off?",
            name="toggle",
            choices=[
                ipy.SlashCommandChoice("on", "on"),
                ipy.SlashCommandChoice("off", "off"),
            ],
        ),
    ) -> None:
        toggle = _toggle == "on"
        await ctx.fetch_config({"messages": True})

        await models.MessageConfig.prisma().update(
            data={"ping_for_message": toggle}, where={"guild_id": ctx.guild_id}
        )

        await ctx.send(
            embed=utils.make_embed(
                f"Pinging on messages turned {utils.toggle_friendly_str(toggle)}!"
            )
        )

    @config.subcommand(
        "help", sub_cmd_description="Tells you how to set up the messaging system."
    )
    async def message_help(self, ctx: utils.THIASlashContext) -> None:
        embed = utils.make_embed(
            "To set up the messaging system, follow the messaging setup guide below.",
            title="Setup Bot",
        )
        button = ipy.Button(
            style=ipy.ButtonStyle.LINK,
            label="Messaging Setup Guide",
            url="https://pythia.astrea.cc/setup/messaging_setup",
        )
        await ctx.send(embeds=embed, components=button)

    manage = tansy.SlashCommand(
        name="message-manage",
        description="Handles management of the messaging system.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @manage.subcommand(
        "link",
        sub_cmd_description=(
            "Creates/updates a messaging link between a user and a channel."
        ),
    )
    async def message_link(
        self,
        ctx: utils.THIASlashContext,
        user: ipy.Member = tansy.Option("The user to link."),
        channel: ipy.GuildText | ipy.GuildPublicThread = tansy.Option(
            "The channel to link for this user.", converter=utils.ValidChannelConverter
        ),
    ) -> None:
        await ctx.fetch_config({"messages": True})
        if (
            await models.MessageLink.prisma().count(where={"guild_id": ctx.guild_id})
            >= 100
        ):
            raise utils.CustomCheckFailure("Cannot add more than 100 messaging links.")

        if link := await models.MessageLink.prisma().find_first(
            where={"guild_id": ctx.guild_id, "user_id": user.id}
        ):
            await models.MessageLink.prisma().update(
                data={"channel_id": channel.id}, where={"id": link.id}
            )
        else:
            await models.MessageLink.prisma().create(
                data={
                    "guild_id": ctx.guild_id,
                    "user_id": user.id,
                    "channel_id": channel.id,
                }
            )

        await ctx.send(
            embed=utils.make_embed(
                f"Created/updated link: {user.mention} -> {channel.mention}"
            )
        )

    @manage.subcommand(
        "list-links", sub_cmd_description="Lists all messaging links for this server."
    )
    async def message_view_links(self, ctx: utils.THIASlashContext) -> None:
        links = await models.MessageLink.prisma().find_many(
            where={"guild_id": ctx.guild_id}
        )

        if not links:
            raise utils.CustomCheckFailure(
                "This server has no messaging links to list."
            )

        links_list = [f"<@{link.user_id}> -> <#{link.channel_id}>" for link in links]
        if len(links_list) > 30:
            chunks = [links_list[x : x + 30] for x in range(0, len(links_list), 30)]
            embeds = [
                utils.make_embed(
                    "\n".join(chunk),
                    title="Messaging Links",
                )
                for chunk in chunks
            ]

            pag = help_tools.HelpPaginator.create_from_embeds(
                self.bot, *embeds, timeout=120
            )
            pag.show_callback_button = False
            await pag.send(ctx)
        else:
            await ctx.send(
                embed=utils.make_embed(
                    "\n".join(links_list),
                    title="Items",
                )
            )

    @manage.subcommand(
        "remove-link", sub_cmd_description="Removes a messaging link for a user."
    )
    async def message_remove_link(
        self,
        ctx: utils.THIASlashContext,
        user: ipy.Member = tansy.Option("The user to remove the link from."),
    ) -> None:
        num_deleted = await models.MessageLink.prisma().delete_many(
            where={"guild_id": ctx.guild_id, "user_id": user.id}
        )

        if num_deleted < 1:
            raise utils.CustomCheckFailure("There's no messaging link to remove!")

        await ctx.send(
            embed=utils.make_embed(
                f"The messaging link for {user.id} has been removed."
            )
        )

    @manage.subcommand(
        "clear-links", sub_cmd_description="Removes all messaging links for the server."
    )
    async def message_clear_links(
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

        num_deleted = await models.MessageLink.prisma().delete_many(
            where={"guild_id": ctx.guild_id}
        )

        if num_deleted < 1:
            raise utils.CustomCheckFailure("There's no messaging links to clear!")

        await ctx.send(
            embed=utils.make_embed(
                "All messaging links for this server have been cleared."
            )
        )


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(help_tools)
    MessageManagement(bot)
