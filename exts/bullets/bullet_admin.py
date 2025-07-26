"""
Copyright 2021-2025 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import collections
import importlib
import typing

import interactions as ipy
import tansy

import common.fuzzy as fuzzy
import common.help_tools as help_tools
import common.models as models
import common.text_utils as text_utils
import common.utils as utils


class BulletManagement(utils.Extension):
    """Commands for using and modifying Truth Bullets."""

    def __init__(self, _: utils.THIABase) -> None:
        self.name = "Bullet"

    manage = tansy.SlashCommand(
        name="bullet-manage",
        description="Handles management of Truth Bullets.",
        default_member_permissions=ipy.Permissions.MANAGE_GUILD,
        dm_permission=False,
    )

    @staticmethod
    def add_truth_bullets_modal(
        channel: ipy.GuildText | ipy.GuildPublicThread,
    ) -> ipy.Modal:
        return ipy.Modal(
            ipy.InputText(
                label="Truth Bullet Trigger",
                style=ipy.TextStyles.SHORT,
                custom_id="truth_bullet_trigger",
                max_length=60,
            ),
            ipy.InputText(
                label="Truth Bullet Description",
                style=ipy.TextStyles.PARAGRAPH,
                custom_id="truth_bullet_desc",
                max_length=3800,
            ),
            ipy.InputText(
                label="Truth Bullet Image",
                style=ipy.TextStyles.SHORT,
                custom_id="truth_bullet_image",
                placeholder="The image URL of the Truth Bullet.",
                max_length=1000,
                required=False,
            ),
            ipy.InputText(
                label="Hide this Truth Bullet only to the finder?",
                style=ipy.TextStyles.SHORT,
                custom_id="truth_bullet_hidden",
                value="no",
                max_length=10,
            ),
            title=(
                "Add Truth Bullets for"
                f" #{text_utils.name_shorten(channel.name or 'this-channel')}"
            ),
            custom_id=f"ui-modal:add_bullets-{channel.id}",
        )

    @manage.subcommand(
        sub_cmd_name="add",
        sub_cmd_description="Adds a Truth Bullet to a channel.",
    )
    @ipy.auto_defer(enabled=False)
    async def add_bullets(
        self,
        ctx: utils.THIASlashContext,
        channel: ipy.GuildText | ipy.GuildPublicThread = tansy.Option(
            "The channel for the Truth Bullets to be added.",
            converter=utils.ValidChannelConverter,
        ),
        _send_button: str = tansy.Option(
            "Should a button be sent that allows for repeatedly adding Truth Bullets?",
            name="send_button",
            choices=[
                ipy.SlashCommandChoice("yes", "yes"),
                ipy.SlashCommandChoice("no", "no"),
            ],
            default="yes",
        ),
    ) -> None:
        config = await ctx.fetch_config({"bullets": True})
        if typing.TYPE_CHECKING:
            assert config.bullets is not None

        if (
            config.bullets.thread_behavior == models.BulletThreadBehavior.PARENT
            and isinstance(channel, ipy.ThreadChannel)
        ):
            raise utils.CustomCheckFailure(
                "Cannot add Truth Bullets to a thread while thread behavior is set to"
                " follow the parent channel."
            )

        send_button = _send_button == "yes"

        count = await models.TruthBullet.filter(
            guild_id=ctx.guild_id,
        ).count()
        if count > 500:
            raise utils.CustomCheckFailure("Cannot add more than 500 Truth Bullets.")

        if send_button:
            await ctx.defer()

            embeds: list[ipy.Embed] = []
            if (
                count > 0
                and await models.TruthBullet.filter(
                    guild_id=ctx.guild_id, found=False
                ).exists()
            ):
                embeds.append(
                    ipy.Embed(
                        "Warning",
                        "This server has Truth Bullets that all have been found,"
                        " likely from a previous investigation. If you want to start"
                        " fresh with completely new Truth Bullets, you can clear the"
                        " current ones with"
                        f" {self.bot.mention_command('bullet-manage clear')}.",
                        color=ipy.RoleColors.YELLOW,
                    )
                )

            button = ipy.Button(
                style=ipy.ButtonStyle.GREEN,
                label=f"Add Truth Bullets for #{channel.name}",
                custom_id=f"ui-button:add_bullets-{channel.id}",
            )
            embeds.append(utils.make_embed("Add Truth Bullets via the button below!"))

            await ctx.send(
                embeds=embeds,
                components=button,
            )
        else:
            await ctx.send_modal(self.add_truth_bullets_modal(channel))

    add_bullet_full = utils.alias(
        add_bullets,
        "bullet-manage add-bullet",
        "Adds a Truth Bullet to a channel. Alias to /bullet-manage add.",
    )

    @ipy.listen("component")
    async def on_add_bullets_button(self, event: ipy.events.Component) -> None:
        ctx = event.ctx

        if ctx.custom_id.startswith("ui-button:add_bullets-"):
            channel_id = int(ctx.custom_id.removeprefix("ui-button:add_bullets-"))
            channel = await self.bot.fetch_channel(channel_id)

            if not channel:
                raise utils.CustomCheckFailure(
                    "Could not find the channel this was associated to. Was it deleted?"
                )

            await ctx.send_modal(self.add_truth_bullets_modal(channel))

    @ipy.listen("modal_completion")
    @utils.modal_event_error_handler
    async def on_modal_add_bullet(self, event: ipy.events.ModalCompletion) -> None:
        ctx = event.ctx

        if ctx.custom_id.startswith("ui-modal:add_bullets-"):
            await ctx.defer()

            config = await models.GuildConfig.fetch_create(
                ctx.guild_id, {"bullets": True}
            )
            if typing.TYPE_CHECKING:
                assert config.bullets is not None

            channel_id = int(ctx.custom_id.removeprefix("ui-modal:add_bullets-"))
            channel = await self.bot.fetch_channel(channel_id)

            if (
                config.bullets.thread_behavior == models.BulletThreadBehavior.PARENT
                and isinstance(channel, ipy.ThreadChannel)
            ):
                raise utils.CustomCheckFailure(
                    "Cannot add Truth Bullets to a thread while thread behavior is set"
                    " to follow the parent channel."
                )

            if await models.TruthBullet.validate(
                channel_id, ctx.responses["truth_bullet_trigger"]
            ):
                await ctx.send(
                    embed=utils.error_embed_generate(
                        f"A Truth Bullet in <#{channel_id}> already has the trigger"
                        f" `{ctx.responses['truth_bullet_trigger']}` or has an alias"
                        " named that!"
                    )
                )
                return

            try:
                hidden = utils.convert_to_bool(ctx.responses["truth_bullet_hidden"])
            except ipy.errors.BadArgument:
                await ctx.send(
                    embed=utils.error_embed_generate(
                        "Invalid value for hiding the Truth Bullet! Giving a simple"
                        " 'yes' or 'no' will work."
                    )
                )
                return

            image: str | None = ctx.kwargs.get("truth_bullet_image", "").strip() or None
            if image and not text_utils.HTTP_URL_REGEX.fullmatch(image):
                raise ipy.errors.BadArgument("The image given must be a valid URL.")

            await models.TruthBullet.create(
                trigger=text_utils.replace_smart_punc(
                    ctx.responses["truth_bullet_trigger"]
                ),
                aliases=[],
                description=ctx.responses["truth_bullet_desc"],
                channel_id=channel_id,
                guild_id=ctx.guild_id,
                found=False,
                finder=None,
                hidden=hidden,
                image=image,
            )

            await ctx.send(
                embed=utils.make_embed(
                    "Added Truth Bullet with trigger"
                    f" `{ctx.responses['truth_bullet_trigger']}` to <#{channel_id}>!"
                ),
            )

    @manage.subcommand(
        "remove",
        sub_cmd_description="Removes a Truth Bullet.",
    )
    async def remove_bullet(
        self,
        ctx: utils.THIASlashContext,
        channel: ipy.GuildText | ipy.GuildPublicThread = tansy.Option(
            "The channel for the Truth Bullet to be removed."
        ),
        trigger: str = tansy.Option(
            "The trigger of the Truth Bullet to be removed.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
    ) -> None:
        num_deleted = await models.TruthBullet.filter(
            channel_id=channel.id,
            trigger__iexact=trigger,
        ).delete()

        if num_deleted > 0:
            await ctx.send(
                embed=utils.make_embed(
                    f"Truth Bullet with trigger `{trigger}` removed from"
                    f" {channel.mention}!"
                )
            )
        else:
            raise ipy.errors.BadArgument(
                f"Truth Bullet with trigger `{trigger}` does not exists!"
            )

    delete_bullet = utils.alias(
        remove_bullet,
        "bullet-manage delete-bullet",
        "Deletes a Truth Bullet. Alias to /bullet-manage remove.",
    )

    @manage.subcommand(
        "clear",
        sub_cmd_description="Removes all Truth Bullets. This action is irreversible.",
    )
    async def clear_bullets(
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

        num_deleted = await models.TruthBullet.filter(guild_id=ctx.guild_id).delete()
        if num_deleted > 0:
            await ctx.send(
                embed=utils.make_embed("Cleared all Truth Bullets for this server!")
            )
        else:
            raise utils.CustomCheckFailure(
                "There's no Truth Bullets to delete for this server!"
            )

    clear_bullets_full = utils.alias(
        clear_bullets,
        "bullet-manage clear-bullets",
        "Clears all Truth Bullets. Alias to /bullet-manage clear.",
    )

    @manage.subcommand(
        "list",
        sub_cmd_description="Lists all Truth Bullets in the server.",
    )
    async def list_bullets(self, ctx: utils.THIASlashContext) -> None:
        guild_bullets = await models.TruthBullet.filter(
            guild_id=ctx.guild_id,
        )
        if not guild_bullets:
            raise utils.CustomCheckFailure("There's no Truth Bullets for this server!")

        bullet_dict: collections.defaultdict[int, list[models.TruthBullet]] = (
            collections.defaultdict(list)
        )
        for bullet in guild_bullets:
            bullet_dict[bullet.channel_id].append(bullet)

        str_builder: collections.deque[str] = collections.deque()

        for channel_id in bullet_dict.keys():
            str_builder.append(f"<#{channel_id}>:")
            for bullet in sorted(
                bullet_dict[channel_id], key=lambda x: x.trigger.lower()
            ):
                str_builder.append(
                    f"- `{text_utils.escape_markdown(bullet.trigger)}`{' (found)' if bullet.found else ''}"
                )

            str_builder.append("")

        pag = help_tools.HelpPaginator.create_from_list(
            ctx.bot, list(str_builder), timeout=120
        )
        if len(pag.pages) == 1:
            embed = pag.pages[0].to_embed()  # type: ignore
            embed.timestamp = ipy.Timestamp.utcnow()
            embed.color = ctx.bot.color
            embed.title = None
            await ctx.send(embeds=embed)
            return

        pag.show_callback_button = False
        pag.show_select_menu = False
        pag.default_color = ctx.bot.color
        await pag.send(ctx)

    list_bullets_full = utils.alias(
        list_bullets,
        "bullet-manage list-bullets",
        "Lists all Truth Bullets. Alias to /bullet-manage list.",
    )

    @manage.subcommand(
        "info", sub_cmd_description="Displays information about a Truth Bullet."
    )
    async def bullet_info(
        self,
        ctx: utils.THIASlashContext,
        channel: ipy.GuildText | ipy.GuildPublicThread = tansy.Option(
            "The channel the Truth Bullet is in."
        ),
        trigger: str = tansy.Option(
            "The trigger of the Truth Bullet.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
    ) -> None:
        bullet = await models.TruthBullet.find_via_trigger(channel.id, trigger)
        if not bullet:
            raise ipy.errors.BadArgument(
                f"Truth Bullet with trigger `{trigger}` does not exist in"
                f" {channel.mention}!"
            )

        aliases = (
            "\n-# Aliases:"
            f" {', '.join(f'`{text_utils.escape_markdown(a)}`' for a in bullet.aliases)}"
            if bullet.aliases
            else ""
        )
        embed = utils.make_embed(
            description=(
                f"# `{text_utils.escape_markdown(bullet.trigger)}` - in"
                f" {bullet.chan_mention}{aliases}\n{bullet.description}"
            ),
        )
        embed.add_field(
            "Hidden", utils.yesno_friendly_str(bullet.hidden).title(), inline=True
        )
        embed.add_field(
            "Finder", f"<@{bullet.finder}>" if bullet.finder else "N/A", inline=True
        )
        if bullet.image:
            embed.add_image(bullet.image)

        await ctx.send(embeds=embed)

    view_bullet = utils.alias(
        bullet_info,
        "bullet-manage view-bullet",
        "Views a Truth Bullet. Alias to /bullet-manage info.",
    )

    @manage.subcommand("edit", sub_cmd_description="Edits a Truth Bullet.")
    @ipy.auto_defer(enabled=False)
    async def edit_bullet(
        self,
        ctx: utils.THIASlashContext,
        channel: ipy.GuildText | ipy.GuildPublicThread = tansy.Option(
            "The channel the Truth Bullet is in."
        ),
        trigger: str = tansy.Option(
            "The trigger of the Truth Bullet to edit.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
    ) -> None:
        bullet = await models.TruthBullet.find_via_trigger(channel.id, trigger)
        if not bullet:
            raise ipy.errors.BadArgument(
                f"Truth Bullet with trigger `{trigger}` does not exist!"
            )

        modal = ipy.Modal(
            ipy.InputText(
                label="Truth Bullet Trigger",
                style=ipy.TextStyles.SHORT,
                custom_id="truth_bullet_trigger",
                value=bullet.trigger,
                max_length=60,
            ),
            ipy.InputText(
                label="Truth Bullet Description",
                style=ipy.TextStyles.PARAGRAPH,
                custom_id="truth_bullet_desc",
                value=bullet.description,
                max_length=3800,
            ),
            ipy.InputText(
                label="Truth Bullet Image",
                style=ipy.TextStyles.SHORT,
                custom_id="truth_bullet_image",
                placeholder="The image URL of the Truth Bullet.",
                value=bullet.image or ipy.MISSING,
                max_length=1000,
                required=False,
            ),
            ipy.InputText(
                label="Hide this Truth Bullet only to the finder?",
                style=ipy.TextStyles.SHORT,
                custom_id="truth_bullet_hidden",
                value=utils.yesno_friendly_str(bullet.hidden),
                max_length=10,
            ),
            title=(
                f"Edit {text_utils.name_shorten(bullet.trigger, 10)} for"
                f" #{text_utils.name_shorten(channel.name, 14)}"
            ),
            custom_id=f"ui:edit-bullet-{channel.id}|{trigger}",
        )
        await ctx.send_modal(modal)

    edit_bullet_full = utils.alias(
        edit_bullet,
        "bullet-manage edit-bullet",
        "Edits a Truth Bullet. Alias to /bullet-manage edit.",
    )

    @ipy.listen("modal_completion")
    @utils.modal_event_error_handler
    async def on_modal_edit_bullet(self, event: ipy.events.ModalCompletion) -> None:
        ctx = event.ctx

        if ctx.custom_id.startswith("ui:edit-bullet-"):
            channel_id, trigger = ctx.custom_id.removeprefix("ui:edit-bullet-").split(
                "|", maxsplit=1
            )
            channel_id = int(channel_id)

            bullet = await models.TruthBullet.find_via_trigger(channel_id, trigger)
            if bullet is None:
                await ctx.send(
                    embed=utils.error_embed_generate(
                        f"Truth Bullet with trigger `{trigger}` no longer exists!"
                    )
                )
                return

            try:
                hidden = utils.convert_to_bool(ctx.responses["truth_bullet_hidden"])
            except ipy.errors.BadArgument:
                await ctx.send(
                    embed=utils.error_embed_generate(
                        "Invalid value for hiding the Truth Bullet! Giving a simple"
                        " 'yes' or 'no' will work."
                    )
                )
                return

            image: str | None = ctx.kwargs.get("truth_bullet_image", "").strip() or None
            if image and not text_utils.HTTP_URL_REGEX.fullmatch(image):
                raise ipy.errors.BadArgument("The image given must be a valid URL.")

            bullet.trigger = text_utils.replace_smart_punc(
                ctx.responses["truth_bullet_trigger"]
            )
            bullet.description = ctx.responses["truth_bullet_desc"]
            bullet.hidden = hidden
            bullet.image = image
            await bullet.save(force_update=True)

            if bullet.trigger != trigger:
                await ctx.send(
                    embed=utils.make_embed(
                        f"Edited Truth Bullet `{trigger}` (renamed to"
                        f" `{bullet.trigger}`) in <#{channel_id}>!"
                    )
                )
            else:
                await ctx.send(
                    embed=utils.make_embed(
                        f"Edited Truth Bullet `{trigger}` in <#{channel_id}>!"
                    )
                )

    @manage.subcommand("unfind", sub_cmd_description="Un-finds a Truth Bullet.")
    async def unfind_bullet(
        self,
        ctx: utils.THIASlashContext,
        channel: ipy.GuildText | ipy.GuildPublicThread = tansy.Option(
            "The channel the Truth Bullet is in."
        ),
        trigger: str = tansy.Option(
            "The trigger of the Truth Bullet to unfind.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
    ) -> None:
        possible_bullet = await models.TruthBullet.find_via_trigger(channel.id, trigger)

        if not possible_bullet:
            raise ipy.errors.BadArgument(
                f"Truth Bullet with trigger `{trigger}` does not exist!"
            )
        if not possible_bullet.found:
            raise ipy.errors.BadArgument(
                f"Truth Bullet with trigger `{trigger}` has not been found!"
            )

        possible_bullet.found = False
        possible_bullet.finder = None
        await possible_bullet.save(force_update=True)

        await ctx.send(embed=utils.make_embed("Truth Bullet un-found!"))

    unfind_bullet_full = utils.alias(
        unfind_bullet,
        "bullet-manage unfind-bullet",
        "Un-finds a Truth Bullet. Alias to /bullet-manage unfind.",
    )

    @manage.subcommand(
        "override-finder",
        sub_cmd_description=(
            "Overrides who found a Truth Bullet with the person specified."
        ),
    )
    async def override_bullet(
        self,
        ctx: utils.THIASlashContext,
        channel: ipy.GuildText | ipy.GuildPublicThread = tansy.Option(
            "The channel the Truth Bullet is in."
        ),
        trigger: str = tansy.Option(
            "The trigger of the Truth Bullet to find.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
        user: ipy.Member = tansy.Option("The user who will find the Truth Bullet."),
    ) -> None:
        possible_bullet = await models.TruthBullet.find_via_trigger(channel.id, trigger)
        if not possible_bullet:
            raise ipy.errors.BadArgument(
                f"Truth Bullet with `{trigger}` does not exist!"
            )

        possible_bullet.found = True
        possible_bullet.finder = user.id
        await possible_bullet.save(force_update=True)

        await ctx.send(embed=utils.make_embed("Truth Bullet overrided and found!"))

    @manage.subcommand(
        "add-alias", sub_cmd_description="Adds an alias to the Truth Bullet specified."
    )
    async def add_alias(
        self,
        ctx: utils.THIASlashContext,
        channel: ipy.GuildText | ipy.GuildPublicThread = tansy.Option(
            "The channel the Truth Bullet is in."
        ),
        trigger: str = tansy.Option(
            "The trigger of the Truth Bullet to add an alias to.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
        alias: str = tansy.Option(
            "The alias to add. Cannot be over 40 characters.",
            max_length=40,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
    ) -> None:
        if len(alias) > 40:
            raise ipy.errors.BadArgument(
                "The name is too large for me to use! "
                + "Please use something at or under 40 characters."
            )

        if await models.TruthBullet.exists(
            channel_id=channel.id,
            trigger__iexact=alias,
        ):
            raise ipy.errors.BadArgument(
                f"Alias `{alias}` is used as a trigger for another Truth Bullet for"
                " this channel!"
            )

        possible_bullet = await models.TruthBullet.find_via_trigger(channel.id, trigger)
        if not possible_bullet:
            raise ipy.errors.BadArgument(
                f"Truth Bullet with trigger `{trigger}` does not exist!"
            )

        if possible_bullet.aliases is None:
            possible_bullet.aliases = []

        if len(possible_bullet.aliases) >= 5:
            raise utils.CustomCheckFailure(
                "Cannot add more aliases to this Truth Bullet!"
            )

        if alias in possible_bullet.aliases:
            raise ipy.errors.BadArgument(
                f"Alias `{alias}` already exists for this Truth Bullet!"
            )

        possible_bullet.aliases.append(alias)
        await possible_bullet.save(force_update=True)

        await ctx.send(
            embed=utils.make_embed(
                f"Alias `{alias}` added to Truth Bullet with trigger `{trigger}` in"
                f" {channel.mention}!"
            )
        )

    @manage.subcommand(
        "remove-alias",
        sub_cmd_description="Removes an alias from the Truth Bullet specified.",
    )
    async def remove_alias(
        self,
        ctx: utils.THIASlashContext,
        channel: ipy.GuildText | ipy.GuildPublicThread = tansy.Option(
            "The channel the Truth Bullet is in."
        ),
        trigger: str = tansy.Option(
            "The trigger of the Truth Bullet to remove an alias to.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
        alias: str = tansy.Option(
            "The alias to remove.",
            autocomplete=True,
            converter=text_utils.ReplaceSmartPuncConverter,
        ),
    ) -> None:
        possible_bullet = await models.TruthBullet.find_via_trigger(channel.id, trigger)
        if not possible_bullet:
            raise ipy.errors.BadArgument(
                f"Truth Bullet with `{trigger}` does not exist!"
            )

        if possible_bullet.aliases is None:
            possible_bullet.aliases = []

        try:
            possible_bullet.aliases.remove(alias)
        except KeyError:
            raise ipy.errors.BadArgument(
                f"Alias `{alias}` does not exists for this Truth Bullet!"
            ) from None

        await possible_bullet.save(force_update=True)

        await ctx.send(
            embed=utils.make_embed(
                f"Alias `{alias}` removed from Truth Bullet with trigger `{trigger}` in"
                f" {channel.mention}!"
            )
        )

    @remove_bullet.autocomplete("trigger")
    @bullet_info.autocomplete("trigger")
    @edit_bullet.autocomplete("trigger")
    @unfind_bullet.autocomplete("trigger")
    @override_bullet.autocomplete("trigger")
    @add_alias.autocomplete("trigger")
    @remove_alias.autocomplete("trigger")
    async def _bullet_trigger_autocomplete(self, ctx: ipy.AutocompleteContext) -> None:
        return await fuzzy.autocomplete_bullets(ctx, **ctx.kwargs)

    @remove_alias.autocomplete("alias")
    async def _remove_alias_alias_autocomplete(
        self,
        ctx: ipy.AutocompleteContext,
    ) -> None:
        return await fuzzy.autocomplete_aliases(ctx, **ctx.kwargs)


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(fuzzy)
    importlib.reload(help_tools)
    importlib.reload(text_utils)
    BulletManagement(bot)
