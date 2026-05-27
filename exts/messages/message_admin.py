"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import importlib
import typing

import discord
import ragwort

import common.classes as classes
import common.models as models
import common.utils as utils


class MessageManagement(utils.Cog):
    def __init__(self, bot: utils.THIABase) -> None:
        self.bot = bot
        self.__cog_name__ = "Messaging Management"

    config = ragwort.SlashCommandGroup(
        name="message-config",
        description="Handles configuration of the messaging system.",
        default_member_permissions=discord.Permissions(manage_guild=True),
        contexts={discord.InteractionContextType.guild},
    )

    @config.command(
        name="info",
        description="Lists out the messaging system settings for the server.",
    )
    async def messages_info(self, ctx: utils.THIASlashContext) -> None:
        config = await ctx.fetch_config({"messages": True})
        if typing.TYPE_CHECKING:
            assert config.messages and isinstance(config.messages, models.MessageConfig)

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
            "-# Links can be found at `/message-manage list-links`.",
        ]
        await ctx.respond(
            view=utils.make_view(
                "\n".join(str_builder), title=f"Message config for {ctx.guild.name}"
            )
        )

    @config.command(
        name="toggle", description="Enables or disables the messaging system."
    )
    async def message_toggle(
        self,
        ctx: utils.THIASlashContext,
        _toggle: str = ragwort.Option(
            "Should the messaging system be turned on or off?",
            name="toggle",
            choices=[
                discord.OptionChoice("on", "on"),
                discord.OptionChoice("off", "off"),
            ],
        ),
    ) -> None:
        toggle = _toggle == "on"
        await ctx.fetch_config({"messages": True})

        await models.MessageConfig.filter(guild_id=ctx.guild_id).update(enabled=toggle)

        await ctx.respond(
            view=utils.make_view(
                f"Messaging system turned {utils.toggle_friendly_str(toggle)}!"
            )
        )

    @config.command(
        name="anonymous-messaging",
        description="Enables or disables anonymous messaging.",
    )
    async def message_anon_toggle(
        self,
        ctx: utils.THIASlashContext,
        _toggle: str = ragwort.Option(
            "Should anonymous messaging be turned on or off?",
            name="toggle",
            choices=[
                discord.OptionChoice("on", "on"),
                discord.OptionChoice("off", "off"),
            ],
        ),
    ) -> None:
        toggle = _toggle == "on"
        await ctx.fetch_config({"messages": True})

        await models.MessageConfig.filter(guild_id=ctx.guild_id).update(
            anon_enabled=toggle
        )

        await ctx.respond(
            view=utils.make_view(
                f"Anonymous messaging turned {utils.toggle_friendly_str(toggle)}!"
            )
        )

    @config.command(
        name="ping-on-message",
        description="Enables or disables pinging on messages.",
    )
    async def message_ping_toggle(
        self,
        ctx: utils.THIASlashContext,
        _toggle: str = ragwort.Option(
            "Should pinging on messages be turned on or off?",
            name="toggle",
            choices=[
                discord.OptionChoice("on", "on"),
                discord.OptionChoice("off", "off"),
            ],
        ),
    ) -> None:
        toggle = _toggle == "on"
        await ctx.fetch_config({"messages": True})

        await models.MessageConfig.filter(guild_id=ctx.guild_id).update(
            ping_for_message=toggle
        )

        await ctx.respond(
            view=utils.make_view(
                f"Pinging on messages turned {utils.toggle_friendly_str(toggle)}!"
            )
        )

    @config.command(
        name="help", description="Tells you how to set up the messaging system."
    )
    async def message_help(self, ctx: utils.THIASlashContext) -> None:
        container = utils.make_container(
            "To set up the messaging system, follow the messaging setup guide below.",
            title="Setup Messaging System",
        )
        container.add_separator(divider=False)
        container.add_row(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="Messaging Setup Guide",
                url="https://pythia.astrea.cc/setup/messaging_setup",
            ),
        )
        await ctx.respond(view=utils.quick_view(container))

    manage = ragwort.SlashCommandGroup(
        name="message-manage",
        description="Handles management of the messaging system.",
        default_member_permissions=discord.Permissions(manage_guild=True),
        contexts={discord.InteractionContextType.guild},
    )

    @manage.command(
        name="link",
        description="Creates/updates a messaging link between a user and a channel.",
    )
    async def message_link(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option("The user to link."),
        channel: discord.TextChannel | discord.Thread = ragwort.Option(
            "The channel to link for this user.",
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

        await ctx.fetch_config({"messages": True})
        if await models.MessageLink.filter(guild_id=ctx.guild_id).count() >= 200:
            raise utils.CustomCheckFailure("Cannot add more than 200 messaging links.")

        if link := await models.MessageLink.get_or_none(
            guild_id=ctx.guild_id, user_id=user.id
        ):
            await models.MessageLink.filter(id=link.id).update(channel_id=channel.id)
        else:
            await models.MessageLink.create(
                guild_id=ctx.guild_id,
                user_id=user.id,
                channel_id=channel.id,
            )

        await ctx.respond(
            view=utils.make_view(
                f"Created/updated link: {user.mention} -> {channel.mention}"
            )
        )

    message_add_link = utils.alias(
        message_link,
        name="add-link",
        description=(
            "Creates/updates a messaging link between a user and a channel. Alias for"
            " /message-manage link."
        ),
    )

    message_update_link = utils.alias(
        message_link,
        name="update-link",
        description=(
            "Creates/updates a messaging link between a user and a channel. Alias for"
            " /message-manage link."
        ),
    )

    @manage.command(
        name="list-links", description="Lists all messaging links for this server."
    )
    async def message_view_links(self, ctx: utils.THIASlashContext) -> None:
        links = await models.MessageLink.filter(guild_id=ctx.guild_id)
        if not links:
            raise utils.CustomCheckFailure(
                "This server has no messaging links to list."
            )

        links_list = [f"<@{link.user_id}> -> <#{link.channel_id}>" for link in links]
        chunks = [links_list[x : x + 30] for x in range(0, len(links_list), 30)]
        items = [[discord.ui.TextDisplay("\n".join(chunk))] for chunk in chunks]

        pag = classes.ContainerPaginator(
            *items,
            title="Messaging Links",
            author_id=ctx.author.id,
        )
        await ctx.respond(view=pag)

    @manage.command(
        name="remove-link", description="Removes a messaging link for a user."
    )
    async def message_remove_link(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option("The user to remove the link from."),
    ) -> None:
        num_deleted = await models.MessageLink.filter(
            guild_id=ctx.guild_id, user_id=user.id
        ).delete()
        if num_deleted < 1:
            raise utils.CustomCheckFailure("There's no messaging link to remove!")

        await ctx.respond(
            view=utils.make_view(f"The messaging link for {user.id} has been removed.")
        )

    @manage.command(
        name="clear-links", description="Removes all messaging links for the server."
    )
    async def message_clear_links(
        self,
        ctx: utils.THIASlashContext,
        confirm: bool = ragwort.Option(
            "Actually clear? Set this to true if you're sure.", default=False
        ),
    ) -> None:
        if not confirm:
            raise utils.BadArgument(
                "Confirm option not set to true. Please set the option `confirm` to"
                " true to continue."
            )

        num_deleted = await models.MessageLink.filter(guild_id=ctx.guild_id).delete()
        if num_deleted < 1:
            raise utils.CustomCheckFailure("There's no messaging links to clear!")

        await ctx.respond(
            view=utils.make_view(
                "All messaging links for this server have been cleared."
            )
        )


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(classes)
    bot.add_cog(MessageManagement(bot))
