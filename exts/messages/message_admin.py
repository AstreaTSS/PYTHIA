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
from tortoise.transactions import in_transaction

import common.classes as classes
import common.models as models
import common.utils as utils


async def thread_mode_enabled_check(ctx: utils.THIASlashContext) -> bool:
    config = await ctx.fetch_config({"messages": True})
    if typing.TYPE_CHECKING:
        assert config.messages and isinstance(config.messages, models.MessageConfig)

    if not config.messages.mode.is_thread():
        raise utils.CustomCheckFailure(
            "This command can only be used in servers with thread-based message modes."
        )

    return True


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
            f"Message mode: {config.messages.mode.display_name()}",
            (
                "Anonymous messaging enabled:"
                f" {utils.yesno_friendly_str(config.messages.anon_enabled)}"
            ),
            (
                "Pinging on messages:"
                f" {utils.toggle_friendly_str(config.messages.ping_for_message)}"
            ),
            "",
            (
                "-# Links can be found at"
                f" {self.bot.mention_command('message-manage list-links')}."
            ),
        ]
        await ctx.respond(
            view=utils.make_view("\n".join(str_builder), title="Message Configuration")
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
        name="mode",
        description=(
            "Sets the message mode for the server. This controls how messages are sent"
            " in the linked channels."
        ),
    )
    async def message_mode(
        self,
        ctx: utils.THIASlashContext,
        _mode: int = ragwort.Option(
            "The message mode to set for the server.",
            name="mode",
            choices=[
                discord.OptionChoice(
                    models.MessageMode.CLASSIC.display_name(),
                    models.MessageMode.CLASSIC,
                ),
                discord.OptionChoice(
                    models.MessageMode.PUBLIC_THREAD.display_name(),
                    models.MessageMode.PUBLIC_THREAD,
                ),
                discord.OptionChoice(
                    models.MessageMode.PRIVATE_THREAD.display_name(),
                    models.MessageMode.PRIVATE_THREAD,
                ),
            ],
        ),
    ) -> None:
        config = await ctx.fetch_config({"messages": True})
        if typing.TYPE_CHECKING:
            assert config.messages and isinstance(config.messages, models.MessageConfig)

        try:
            mode = models.MessageMode(_mode)
        except ValueError:
            raise utils.BadArgument("Invalid message mode selected.") from None

        message_link_ids: list[int] = []

        if config.messages.mode != mode and mode.is_thread():
            async for link in models.MessageLink.filter(guild_id=ctx.guild_id):
                message_link_ids.append(link.id)

                channel = await utils.getch_channel(ctx.guild, link.channel_id)
                if not channel:
                    raise utils.CustomCheckFailure(
                        f"Channel with ID {link.channel_id} not found. Please fix or"
                        " remove this link before changing to a thread-based message"
                        " mode."
                    )

                if typing.TYPE_CHECKING:
                    assert isinstance(channel, discord.TextChannel | discord.Thread)

                if channel.type != discord.ChannelType.text:
                    raise utils.CustomCheckFailure(
                        f"Channel {channel.mention} is not a text channel. Please fix"
                        " or remove this link before changing to a thread-based"
                        " message mode."
                    )

                self_permissions = channel.permissions_for(ctx.guild.me)

                if (
                    mode == models.MessageMode.PUBLIC_THREAD
                    and not self_permissions.create_public_threads
                ):
                    raise utils.CustomCheckFailure(
                        "Missing permission to create public threads in"
                        f" {channel.mention}. Please fix or remove this link before"
                        " changing to the Public Thread message mode."
                    )
                elif (
                    mode == models.MessageMode.PRIVATE_THREAD
                    and not self_permissions.create_private_threads
                ):
                    raise utils.CustomCheckFailure(
                        "Missing permission to create private threads in"
                        f" {channel.mention}. Please fix or remove this link before"
                        " changing to the Private Thread message mode."
                    )

        async with in_transaction():
            if config.messages.mode != mode and mode.is_thread():
                await models.MessageThread.filter(
                    message_link_id__in=message_link_ids
                ).delete()

            await models.MessageConfig.filter(guild_id=ctx.guild_id).update(mode=mode)

        await ctx.respond(
            view=utils.make_view(
                f"Message mode set to {mode.name.replace('_', ' ').title()}!"
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

        if await models.MessageLink.filter(guild_id=ctx.guild_id).count() >= 200:
            raise utils.CustomCheckFailure("Cannot add more than 200 messaging links.")

        config = await ctx.fetch_config({"messages": True})
        if typing.TYPE_CHECKING:
            assert config.messages and isinstance(config.messages, models.MessageConfig)

        if config.messages.mode.is_thread():
            if channel.type != discord.ChannelType.text:
                raise utils.BadArgument(
                    "Invalid channel type. The current message mode requires linking"
                    f" to text channels, but {channel.mention} is not a text channel."
                )

            permissions = channel.permissions_for(ctx.guild.me)

            if (
                config.messages.mode == models.MessageMode.PUBLIC_THREAD
                and not permissions.create_public_threads
            ):
                raise utils.BadArgument(
                    f"Missing permission to create public threads in {channel.mention}."
                )
            elif (
                config.messages.mode == models.MessageMode.PRIVATE_THREAD
                and not permissions.create_private_threads
            ):
                raise utils.BadArgument(
                    "Missing permission to create private threads in"
                    f" {channel.mention}."
                )

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
        config = await ctx.fetch_config({"messages": True})
        if typing.TYPE_CHECKING:
            assert config.messages and isinstance(config.messages, models.MessageConfig)

        links = await models.MessageLink.filter(guild_id=ctx.guild_id)
        if not links:
            raise utils.CustomCheckFailure(
                "This server has no messaging links to list."
            )

        links_list = [f"- <@{link.user_id}> -> <#{link.channel_id}>" for link in links]
        chunks = [links_list[x : x + 30] for x in range(0, len(links_list), 30)]
        items: list[list[discord.ui.ViewItem]] = [
            [discord.ui.TextDisplay("\n".join(chunk))] for chunk in chunks
        ]

        if config.messages.mode.is_thread():
            items[-1].extend(
                (
                    discord.ui.TextDisplay(
                        "-# Threads for individual links can be found at"
                        f" {self.bot.mention_command('message-manage threads view-for')}."
                    ),
                )
            )

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

    threads = manage.create_subgroup(
        name="threads",
        description="Handles management of message threads for the messaging system.",
        checks=[thread_mode_enabled_check],
    )

    @threads.command(
        name="view-for",
        description="Views the threads for a user. Only works in thread message modes.",
    )
    async def message_thread_view_for(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option("The user to view the threads for."),
    ) -> None:
        link = await models.MessageLink.get_or_none(
            guild_id=ctx.guild_id, user_id=user.id
        ).prefetch_related("threads")
        if not link:
            raise utils.CustomCheckFailure(
                f"No messaging link found for {user.mention}."
            )

        if not link.threads:
            raise utils.CustomCheckFailure(f"No threads found for {user.mention}.")

        str_builder: list[str] = []

        for thread in link.threads:
            if thread.is_anonymous():
                str_builder.insert(0, f"- Anonymous -> <#{thread.thread_id}>")
            else:
                str_builder.append(f"- <@{thread.user_id}> -> <#{thread.thread_id}>")

        pag = classes.ContainerPaginator.create_from_list(
            str_builder, title=f"Threads for {user.mention}", author_id=ctx.author.id
        )
        await ctx.respond(view=pag)

    @threads.command(
        name="set",
        description=(
            "Sets a thread for a user for messages from another user. Only works in"
            " thread message modes."
        ),
    )
    async def message_thread_set_for(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option("The user to set the thread for."),
        other_user: discord.Member = ragwort.Option(
            "The other user to set the thread for."
        ),
        thread: discord.Thread = ragwort.Option(
            "The thread to set.",
            input_type=discord.SlashCommandOptionType.channel,
            channel_types=[
                discord.ChannelType.public_thread,
                discord.ChannelType.private_thread,
            ],
        ),
    ) -> None:
        link = await models.MessageLink.get_or_none(
            guild_id=ctx.guild_id, user_id=user.id
        )
        if not link:
            raise utils.CustomCheckFailure(
                f"No messaging link found for {user.mention}."
            )

        if thread.locked:
            raise utils.BadArgument("The provided thread is locked.")

        permissions = thread.permissions_for(ctx.guild.me)

        if (
            thread.type == discord.ChannelType.public_thread
            and not permissions.create_public_threads
        ):
            raise utils.BadArgument(
                f"Missing permission to create public threads in {thread.mention}."
            )
        elif (
            thread.type == discord.ChannelType.private_thread
            and not permissions.create_private_threads
        ):
            raise utils.BadArgument(
                f"Missing permission to create private threads in {thread.mention}."
            )

        await models.MessageThread.update_or_create(
            defaults={"thread_id": thread.id},
            message_link_id=link.id,
            user_id=other_user.id,
        )

        if other_user.id != -1:
            await ctx.respond(
                view=utils.make_view(
                    f"Set thread {thread.mention} for messages from"
                    f" {other_user.mention} to {user.mention}."
                )
            )
        else:
            await ctx.respond(
                view=utils.make_view(
                    f"Set thread {thread.mention} for anonymous messages to"
                    f" {user.mention}."
                )
            )

    @threads.command(
        name="set-anonymous",
        description=(
            "Sets a thread for a user for anonymous messages. Only works in thread"
            " message modes."
        ),
    )
    async def message_thread_set_anonymous(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option("The user to set the thread for."),
        thread: discord.Thread = ragwort.Option(
            "The thread to set.",
            input_type=discord.SlashCommandOptionType.channel,
            channel_types=[
                discord.ChannelType.public_thread,
                discord.ChannelType.private_thread,
            ],
        ),
    ) -> None:
        await self.message_thread_set_for(
            ctx,
            user=user,
            other_user=discord.Object(-1),
            thread=thread,
        )

    @threads.command(
        name="unset",
        description=(
            "Unsets a thread for a user for messages from another user. Only works in"
            " thread message modes."
        ),
    )
    async def message_thread_unset(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option("The user to unset the thread for."),
        other_user: discord.Member = ragwort.Option(
            "The other user to unset the thread for."
        ),
    ) -> None:
        link = await models.MessageLink.get_or_none(
            guild_id=ctx.guild_id, user_id=user.id
        )
        if not link:
            raise utils.CustomCheckFailure(
                f"No messaging link found for {user.mention}."
            )

        if not await models.MessageThread.exists(
            message_link_id=link.id, user_id=other_user.id
        ):
            if other_user.id != -1:
                raise utils.CustomCheckFailure(
                    f"No thread found for messages from {other_user.mention} to"
                    f" {user.mention}."
                )
            else:
                raise utils.CustomCheckFailure(
                    f"No thread found for anonymous messages to {user.mention}."
                )

        await models.MessageThread.filter(
            message_link_id=link.id, user_id=other_user.id
        ).delete()

        if other_user.id != -1:
            await ctx.respond(
                view=utils.make_view(
                    f"Unset thread for messages from {other_user.mention} to"
                    f" {user.mention}."
                )
            )
        else:
            await ctx.respond(
                view=utils.make_view(
                    f"Unset thread for anonymous messages to {user.mention}."
                )
            )

    @threads.command(
        name="unset-anonymous",
        description=(
            "Unsets a thread for a user for anonymous messages. Only works in thread"
            " message modes."
        ),
    )
    async def message_thread_unset_anonymous(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option("The user to unset the thread for."),
    ) -> None:
        await self.message_thread_unset(
            ctx,
            user=user,
            other_user=discord.Object(-1),
        )

    @threads.command(
        name="clear",
        description=(
            "Clears/unsets all threads for a user. Only works in thread message modes."
        ),
    )
    async def message_thread_clear(
        self,
        ctx: utils.THIASlashContext,
        user: discord.Member = ragwort.Option("The user to clear the threads for."),
        confirm: bool = ragwort.Option(
            "Actually clear? Set this to true if you're sure.", default=False
        ),
    ) -> None:
        if not confirm:
            raise utils.BadArgument(
                "Confirm option not set to true. Please set the option `confirm` to"
                " true to continue."
            )

        link = await models.MessageLink.get_or_none(
            guild_id=ctx.guild_id, user_id=user.id
        )
        if not link:
            raise utils.CustomCheckFailure(
                f"No messaging link found for {user.mention}."
            )

        num_deleted = await models.MessageThread.filter(
            message_link_id=link.id
        ).delete()
        if num_deleted < 1:
            raise utils.CustomCheckFailure(f"No threads found for {user.mention}.")

        await ctx.respond(
            view=utils.make_view(f"Unset all threads for {user.mention}.")
        )

    message_threads_unset_all = utils.alias(
        message_thread_clear,
        name="unset-all",
        description=(
            "Unsets all threads for a user. Alias for /message-manage threads clear."
        ),
    )


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(classes)
    bot.add_cog(MessageManagement(bot))
