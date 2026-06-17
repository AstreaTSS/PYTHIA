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
from discord.ext import commands

import common.classes as classes
import common.models as models
import common.utils as utils


class AttachmentMetadata(typing.NamedTuple):
    url: str
    description: str | None
    spoiler: bool


class MessageModal(discord.ui.DesignerModal):
    def __init__(self, user: discord.Member, anon: bool) -> None:
        super().__init__(
            discord.ui.Label(
                label="Message",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.paragraph,
                    custom_id="message_input",
                    max_length=3500,
                    required=False,
                ),
            ),
            discord.ui.Label(
                label="Image or Video",
                description=(
                    "Only one image/video can be sent. The file must be under 10 MiB."
                ),
                item=discord.ui.FileUpload(
                    custom_id="message_file",
                    min_values=0,
                    max_values=1,
                    required=False,
                ),
            ),
            discord.ui.Label(
                label="Spoiler?",
                description=(
                    "Should the image/video (if present) be marked as a spoiler?"
                ),
                item=discord.ui.Checkbox(custom_id="message_spoiler", default=False),
            ),
            title=utils.short_string(
                f"Send a message to {utils.user_string(user)}", 45
            ),
        )

        self.user = user
        self.anon = anon

    @staticmethod
    async def make_container(
        title: str,
        content: str,
        *,
        attachments: (
            list[discord.Attachment] | list[discord.MediaGalleryItem] | None
        ) = None,
    ) -> tuple[discord.ui.Container, list[discord.File]]:
        files: list[discord.File] = []

        container = utils.make_container(content, title=title)
        if attachments:
            attachment_metadata: list[AttachmentMetadata] = []

            for attachment in attachments:
                if isinstance(attachment, discord.MediaGalleryItem):
                    attachment_metadata.append(
                        AttachmentMetadata(
                            url=attachment.url,
                            description=attachment.description,
                            spoiler=attachment.spoiler,
                        )
                    )
                    continue

                if (
                    not attachment.height
                ):  # little hacky but it does cover all discord supported image/video types
                    raise utils.CustomCheckFailure(
                        f"File `{attachment.filename}` is not an image or video."
                    )

                if attachment.ephemeral:
                    if attachment.size > 10485760:
                        raise utils.CustomCheckFailure(
                            f"File `{attachment.filename}` is too large to send (must"
                            " be under 10 MiB)."
                        )

                    attachment_file = await attachment.to_file(
                        spoiler=attachment.is_spoiler()
                    )
                    files.append(attachment_file)

                    attachment_metadata.append(
                        AttachmentMetadata(
                            url=f"attachment://{attachment.filename}",
                            description=attachment.description,
                            spoiler=attachment.is_spoiler(),
                        )
                    )
                else:
                    attachment_metadata.append(
                        AttachmentMetadata(
                            url=attachment.url,
                            description=attachment.description,
                            spoiler=attachment.is_spoiler(),
                        )
                    )

            container.add_gallery(
                *(
                    discord.MediaGalleryItem(
                        a.url, description=a.description, spoiler=a.spoiler
                    )
                    for a in attachment_metadata
                )
            )
        return container, files

    @staticmethod
    async def actual_message(
        ctx: utils.THIABridgeContext,
        user: discord.Member,
        message: str | None,
        *,
        attachments: list[discord.Attachment] | None = None,
        anon: bool = False,
        from_modal: bool = False,
    ) -> None:
        await ctx.defer(ephemeral=True)

        if user.id == ctx.author.id:
            raise utils.CustomCheckFailure("You cannot message yourself.")

        if not message and not attachments:
            raise utils.CustomCheckFailure(
                "You must provide a message or at least one file."
            )

        config = await ctx.fetch_config({"messages": True})
        if typing.TYPE_CHECKING:
            assert config.messages and isinstance(config.messages, models.MessageConfig)

        if not config.messages.enabled:
            raise utils.CustomCheckFailure(
                "The messaging system is not enabled for this server."
            )
        if anon and not config.messages.anon_enabled:
            raise utils.CustomCheckFailure(
                "Anonymous messages are not enabled for this server."
            )

        ctx_user_link = await models.MessageLink.get_or_none(
            guild_id=ctx.guild_id, user_id=ctx.author.id
        )
        if not ctx_user_link:
            raise utils.CustomCheckFailure(
                "You are not set up with the messaging system."
            )

        other_user_link = await models.MessageLink.get_or_none(
            guild_id=ctx.guild_id, user_id=user.id
        )
        if not other_user_link:
            raise utils.BadArgument(
                "The specified user is not set up with the messaging system."
            )

        try:
            other_chan = ctx.bot.get_partial_messageable(other_user_link.channel_id)

            if anon:
                title = "Anonymous message"
            else:
                title = f"Message from {ctx.author.mention}"

            container, files = await MessageModal.make_container(
                title, message or "", attachments=attachments
            )

            if config.messages.ping_for_message:
                view = utils.quick_view(
                    discord.ui.TextDisplay(f"<@{other_user_link.user_id}>"),
                    container,
                )
            else:
                view = utils.quick_view(container)

            other_msg = await other_chan.send(
                view=view,
                allowed_mentions=discord.AllowedMentions(
                    users=(
                        [discord.Object(other_user_link.user_id)]
                        if config.messages.ping_for_message
                        else False  # type: ignore
                    )
                ),
                files=files,
            )
        except discord.HTTPException:
            raise utils.CustomCheckFailure(
                "Could not send a message to the specified user's channel."
            ) from None

        # reuse attachments from the message we just sent if the message was sent from the modal
        # avoids reuploading the same file twice
        if from_modal and attachments:
            attachments = other_msg.components[0].components[1].items  # type: ignore

        try:
            ctx_user_chan = ctx.bot.get_partial_messageable(ctx_user_link.channel_id)

            title = f"Message sent to {user.mention}"
            if anon:
                title = f"Anonymous message sent to {user.mention}"

            container, files = await MessageModal.make_container(
                title, message or "", attachments=attachments
            )

            await ctx_user_chan.send(view=utils.quick_view(container), files=files)
        except discord.HTTPException:
            raise utils.CustomCheckFailure(
                "Message sent, but could not send receipt to your channel."
            ) from None

        await ctx.respond(view=utils.make_view("Sent!"), ephemeral=True)

    async def callback(self, inter: utils.Interaction) -> None:
        attachments: list[discord.Attachment] = self.children[1].item.values
        spoiler: bool = bool(self.children[2].item.value)

        if spoiler and attachments:
            attachments[0].filename = f"SPOILER_{attachments[0].filename}"

        await self.actual_message(
            utils.THIASlashContext(inter.client, inter),
            self.user,
            self.children[0].item.value,
            attachments=attachments,
            anon=self.anon,
            from_modal=True,
        )


class MessageCMDs(utils.Cog):
    def __init__(self, bot: utils.THIABase) -> None:
        self.bot = bot
        self.__cog_name__ = "Messaging Commands"

    @ragwort.bridge_group(
        name="message",
        description="Hosts public-facing messaging commands.",
        contexts={discord.InteractionContextType.guild},
        invoke_without_command=True,
        aliases=["msg"],
    )
    @commands.guild_only()
    async def message(self, _: utils.THIABridgeContext) -> None:
        raise utils.CustomCheckFailure("Please specify a subcommand.")

    @message.command(
        name="send",
        description="Non-anonymously message another player's designated channel.",
        aliases=["whisper"],
    )
    @commands.guild_only()
    @ragwort.auto_defer(enabled=False)
    # @help_tools.prefixed_check() TODO: reimplement in some form
    async def message_whisper(
        self,
        ctx: utils.THIABridgeContext,
        user: discord.Member = ragwort.BridgeOption("The user to message."),
        *,
        message: str | None = ragwort.BridgeOption(
            "The message to send. If not provided, you will be prompted to enter one.",
            default=None,
        ),
    ) -> None:
        if user.id == ctx.author.id:
            raise utils.CustomCheckFailure("You cannot message yourself.")

        config = await ctx.fetch_config({"messages": True})
        if typing.TYPE_CHECKING:
            assert config.messages and isinstance(config.messages, models.MessageConfig)

        if not config.messages.enabled:
            raise utils.CustomCheckFailure(
                "The messaging system is not enabled for this server."
            )

        if not message and not (ctx.message and ctx.message.attachments):
            if isinstance(ctx, utils.THIABridgeExtContext):
                raise utils.CustomCheckFailure("No message provided.")

            await ctx.send_modal(MessageModal(user, anon=False))
            return

        attachments: list[discord.Attachment] = []
        if isinstance(ctx, utils.THIABridgeExtContext):
            attachments = ctx.message.attachments

        await MessageModal.actual_message(ctx, user, message, attachments=attachments)

    @message.command(
        name="anon",
        description="Anonymously message another player's designated channel.",
    )
    @commands.guild_only()
    @ragwort.auto_defer(enabled=False)
    # @help_tools.prefixed_check()
    async def message_anon(
        self,
        ctx: utils.THIABridgeContext,
        user: discord.Member = ragwort.BridgeOption("The user to message."),
        *,
        message: str | None = ragwort.BridgeOption(
            "The message to send. If not provided, you will be prompted to enter one.",
            default=None,
        ),
    ) -> None:
        if user.id == ctx.author.id:
            raise utils.CustomCheckFailure("You cannot message yourself.")

        config = await ctx.fetch_config({"messages": True})
        if typing.TYPE_CHECKING:
            assert config.messages and isinstance(config.messages, models.MessageConfig)

        if not config.messages.enabled:
            raise utils.CustomCheckFailure(
                "The messaging system is not enabled for this server."
            )
        if not config.messages.anon_enabled:
            raise utils.CustomCheckFailure(
                "Anonymous messages are not enabled for this server."
            )

        if not message and not (ctx.message and ctx.message.attachments):
            if isinstance(ctx, utils.THIABridgeExtContext):
                raise utils.CustomCheckFailure("No message provided.")

            await ctx.send_modal(MessageModal(user, anon=True))
            return

        attachments: list[discord.Attachment] = []
        if isinstance(ctx, utils.THIABridgeExtContext):
            attachments = ctx.message.attachments

        await MessageModal.actual_message(
            ctx, user, message, attachments=attachments, anon=True
        )


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(classes)
    bot.add_cog(MessageCMDs(bot))
