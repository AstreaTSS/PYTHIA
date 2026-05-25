"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import asyncio
import collections
import importlib
import typing

import discord
import ragwort
from discord.ext import commands

import common.classes as classes
import common.fuzzy as fuzzy
import common.models as models
import common.utils as utils

from ._bullet_common import bullet_manage


class BulletManagement(utils.Cog):
    """Commands for using and modifying Truth Bullets."""

    def __init__(self, bot: utils.THIABase) -> None:
        self.bot = bot
        self.name = "Bullet"

        # i sure do love weird edge cases with race conditions!
        self.bullet_creation_locks: collections.defaultdict[str, asyncio.Lock] = (
            collections.defaultdict(asyncio.Lock)
        )

    @staticmethod
    def add_truth_bullets_modal(
        channel: discord.TextChannel | discord.Thread,
    ) -> discord.ui.DesignerModal:
        return utils.quick_model(
            discord.ui.Label(
                label="Truth Bullet Trigger",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="truth_bullet_trigger",
                    max_length=60,
                ),
            ),
            discord.ui.Label(
                label="Truth Bullet Description",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.paragraph,
                    custom_id="truth_bullet_desc",
                    max_length=3800,
                ),
            ),
            discord.ui.Label(
                label="Truth Bullet Image",
                description="The image URL of the Truth Bullet.",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="truth_bullet_image",
                    max_length=1000,
                    required=False,
                ),
            ),
            discord.ui.Label(
                label="Hide this Truth Bullet only to the finder?",
                item=discord.ui.Select(
                    discord.ComponentType.string_select,
                    options=[
                        discord.SelectOption(label="Yes", value="yes"),
                        discord.SelectOption(label="No", value="no", default=True),
                    ],
                    custom_id="truth_bullet_hidden",
                    required=True,
                ),
            ),
            title=(
                "Add Truth Bullets for"
                f" #{utils.short_string(channel.name or 'this-channel', length=16)}"
            ),
            custom_id=f"ui-modal:add_bullets-{channel.id}",
        )

    @bullet_manage.command(
        name="add",
        description="Adds a Truth Bullet to a channel.",
    )
    @ragwort.auto_defer(enabled=False)
    async def add_bullets(
        self,
        ctx: utils.THIASlashContext,
        channel: discord.TextChannel | discord.Thread = ragwort.Option(
            "The channel for the Truth Bullets to be added.",
            channel_types=[
                discord.ChannelType.text,
                discord.ChannelType.public_thread,
                discord.ChannelType.private_thread,
            ],
        ),
        _send_button: str = ragwort.Option(
            "Should a button be sent that allows for repeatedly adding Truth Bullets?",
            name="send_button",
            choices=[
                discord.OptionChoice("yes", "yes"),
                discord.OptionChoice("no", "no"),
            ],
            default="yes",
        ),
    ) -> None:
        channel = utils.valid_channel_check(
            channel, channel.permissions_for(ctx.guild.me)
        )

        config = await ctx.fetch_config({"bullets": True})
        if typing.TYPE_CHECKING:
            assert config.bullets and isinstance(config.bullets, models.BulletConfig)

        if (
            config.bullets.thread_behavior == models.BulletThreadBehavior.PARENT
            and isinstance(channel, discord.Thread)
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

            containers: list[discord.ui.Container] = []
            if (
                count > 0
                and await models.TruthBullet.filter(
                    guild_id=ctx.guild_id, found=True
                ).exists()
            ):
                containers.append(
                    discord.ui.Container(
                        discord.ui.TextDisplay("# Warning"),
                        discord.ui.TextDisplay(
                            "This server has Truth Bullets that all have been"
                            " found, likely from a previous investigation. If you"
                            " want to start fresh with completely new Truth"
                            " Bullets, you can clear the current ones with"
                            " `/bullet-manage clear`.",
                        ),
                        color=discord.Color.gold(),
                    ),
                )

            containers.append(
                discord.ui.Container(
                    discord.ui.Section(
                        discord.ui.TextDisplay(
                            f"Add Truth Bullets for {channel.mention} with this button!"
                        ),
                        accessory=discord.ui.Button(
                            style=discord.ButtonStyle.green,
                            label="Add Truth Bullet",
                            custom_id=f"thia:add-bullets|{channel.id}",
                        ),
                    ),
                    color=self.bot.color,
                )
            )

            await ctx.send(view=utils.quick_view(*containers))
        else:
            await ctx.send_modal(self.add_truth_bullets_modal(channel))

    add_bullet_full = utils.alias(
        add_bullets,
        name="add-bullet",
        description="Adds a Truth Bullet to a channel. Alias to /bullet-manage add.",
    )

    @utils.button_handler(custom_id_prefix="thia:add-bullets|")
    async def on_add_bullets_button(
        self, inter: utils.Interaction, custom_id: str
    ) -> None:
        channel_id = int(custom_id.removeprefix("thia:add-bullets|"))
        channel = await self.bot.getch_channel(channel_id)

        if not channel:
            raise utils.CustomCheckFailure(
                "Could not find the channel this was associated to. Was it deleted?"
            )
        await inter.response.send_modal(self.add_truth_bullets_modal(channel))

    @utils.button_handler(custom_id_prefix="ui-button:add_bullets-")
    async def on_add_bullets_button_old(
        self, inter: utils.Interaction, custom_id: str
    ) -> None:
        channel_id = int(custom_id.removeprefix("ui-button:add_bullets-"))
        channel = await self.bot.getch_channel(channel_id)

        if not channel:
            raise utils.CustomCheckFailure(
                "Could not find the channel this was associated to. Was it deleted?"
            )
        await inter.response.send_modal(self.add_truth_bullets_modal(channel))

    @utils.modal_handler(custom_id_prefix="ui-modal:add_bullets-")
    async def on_modal_add_bullet(
        self, inter: utils.Interaction, responses: dict[str, typing.Any]
    ) -> None:
        await inter.response.defer()

        config = await models.GuildConfig.fetch_create(
            inter.guild_id, {"bullets": True}
        )
        if typing.TYPE_CHECKING:
            assert config.bullets and isinstance(config.bullets, models.BulletConfig)

        channel_id = int(inter.data["custom_id"].removeprefix("ui-modal:add_bullets-"))
        channel = await self.bot.fetch_channel(channel_id)

        if not channel:
            raise utils.CustomCheckFailure(
                "Could not find the channel this was associated to. Was it deleted?"
            )

        if (
            config.bullets.thread_behavior == models.BulletThreadBehavior.PARENT
            and isinstance(channel, discord.Thread)
        ):
            raise utils.CustomCheckFailure(
                "Cannot add Truth Bullets to a thread while thread behavior is set"
                " to follow the parent channel."
            )

        async with self.bullet_creation_locks[
            f"{channel_id}-{responses['truth_bullet_trigger'].lower()}"
        ]:
            if await models.TruthBullet.validate(
                channel_id, responses["truth_bullet_trigger"]
            ):
                raise commands.BadArgument(
                    f"A Truth Bullet in <#{channel_id}> already has the trigger"
                    f" `{responses['truth_bullet_trigger']}` or has an"
                    " alias named that!"
                )

            try:
                if isinstance(responses["truth_bullet_hidden"], list):
                    hidden = utils.convert_to_bool(responses["truth_bullet_hidden"][0])
                else:
                    hidden = utils.convert_to_bool(responses["truth_bullet_hidden"])
            except commands.BadArgument:
                raise commands.BadArgument(
                    "Invalid value for hiding the Truth Bullet! Giving a simple"
                    " 'yes' or 'no' will work."
                ) from None

            image: str | None = (
                responses["truth_bullet_image"].strip()
                if responses.get("truth_bullet_image")
                else None
            )
            if image and not utils.HTTP_URL_REGEX.fullmatch(image):
                raise commands.BadArgument("The image given must be a valid URL.")

            await models.TruthBullet.create(
                trigger=utils.replace_smart_punc(responses["truth_bullet_trigger"]),
                aliases=[],
                description=responses["truth_bullet_desc"],
                channel_id=channel_id,
                guild_id=inter.guild_id,
                found=False,
                finder=None,
                hidden=hidden,
                image=image,
            )

        await inter.respond(
            view=utils.make_view(
                "Added Truth Bullet with trigger"
                f" `{responses['truth_bullet_trigger']}` to <#{channel_id}>!"
            ),
        )

    @bullet_manage.command(
        name="remove",
        description="Removes a Truth Bullet.",
    )
    async def remove_bullet(
        self,
        ctx: utils.THIASlashContext,
        channel: discord.TextChannel | discord.Thread = ragwort.Option(
            "The channel for the Truth Bullet to be removed.",
            channel_types=[
                discord.ChannelType.text,
                discord.ChannelType.public_thread,
                discord.ChannelType.private_thread,
            ],
        ),
        trigger: str = ragwort.Option(
            "The trigger of the Truth Bullet to be removed.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
    ) -> None:
        num_deleted = await models.TruthBullet.filter(
            channel_id=channel.id,
            trigger__iexact=trigger,
        ).delete()

        if num_deleted > 0:
            await ctx.respond(
                view=utils.make_view(
                    f"Truth Bullet with trigger `{trigger}` removed from"
                    f" {channel.mention}!"
                )
            )
        else:
            raise commands.BadArgument(
                f"Truth Bullet with trigger `{trigger}` does not exists!"
            )

    delete_bullet = utils.alias(
        remove_bullet,
        name="delete-bullet",
        description="Deletes a Truth Bullet. Alias to /bullet-manage remove.",
    )

    @bullet_manage.command(
        name="clear",
        description="Removes all Truth Bullets. This action is irreversible.",
    )
    async def clear_bullets(
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

        num_deleted = await models.TruthBullet.filter(guild_id=ctx.guild_id).delete()
        if num_deleted > 0:
            await ctx.respond(
                view=utils.make_view("Cleared all Truth Bullets for this server!")
            )
        else:
            raise utils.CustomCheckFailure(
                "There's no Truth Bullets to delete for this server!"
            )

    clear_bullets_full = utils.alias(
        clear_bullets,
        name="clear-bullets",
        description="Clears all Truth Bullets. Alias to /bullet-manage clear.",
    )

    @bullet_manage.command(
        name="list",
        description="Lists all Truth Bullets in the server.",
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
                    f"- `{discord.utils.escape_markdown(bullet.trigger)}`{' (found)' if bullet.found else ''}"
                )

            str_builder.append("")

        pag = classes.ContainerPaginator.create_from_list(
            str_builder, title="Truth Bullets in this Server", author_id=ctx.author.id
        )
        if len(pag.pages) == 1:
            item: discord.ui.TextDisplay = pag.pages[0][0]  # type: ignore
            view = utils.make_view(item.content, title="Truth Bullets in this Server")
            await ctx.respond(view=view)
            return

        await ctx.respond(view=pag)

    list_bullets_full = utils.alias(
        list_bullets,
        name="list-bullets",
        description="Lists all Truth Bullets. Alias to /bullet-manage list.",
    )

    @bullet_manage.command(
        name="info", description="Displays information about a Truth Bullet."
    )
    async def bullet_info(
        self,
        ctx: utils.THIASlashContext,
        channel: discord.TextChannel | discord.Thread = ragwort.Option(
            "The channel the Truth Bullet is in.",
            channel_types=[
                discord.ChannelType.text,
                discord.ChannelType.public_thread,
                discord.ChannelType.private_thread,
            ],
        ),
        trigger: str = ragwort.Option(
            "The trigger of the Truth Bullet.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
    ) -> None:
        bullet = await models.TruthBullet.find_via_trigger(channel.id, trigger)
        if not bullet:
            raise commands.BadArgument(
                f"Truth Bullet with trigger `{trigger}` does not exist in"
                f" {channel.mention}!"
            )

        aliases = (
            "\n-# Aliases:"
            f" {', '.join(f'`{discord.utils.escape_markdown(a)}`' for a in bullet.aliases)}"
            if bullet.aliases
            else ""
        )
        embed = discord.Embed(
            description=(
                f"# `{discord.utils.escape_markdown(bullet.trigger)}` -"
                f" {bullet.chan_mention}{aliases}\n{bullet.description}"
            ),
            color=self.bot.color,
        )
        embed.add_field(
            name="Hidden",
            value=utils.yesno_friendly_str(bullet.hidden).title(),
            inline=True,
        )
        embed.add_field(
            name="Finder",
            value=f"<@{bullet.finder}>" if bullet.finder else "N/A",
            inline=True,
        )
        if bullet.image:
            embed.set_image(url=bullet.image)

        await ctx.respond(embed=embed)

    view_bullet = utils.alias(
        bullet_info,
        name="view-bullet",
        description="Views a Truth Bullet. Alias to /bullet-manage info.",
    )

    @bullet_manage.command(name="edit", description="Edits a Truth Bullet.")
    @ragwort.auto_defer(enabled=False)
    async def edit_bullet(
        self,
        ctx: utils.THIASlashContext,
        channel: discord.TextChannel | discord.Thread = ragwort.Option(
            "The channel the Truth Bullet is in.",
            channel_types=[
                discord.ChannelType.text,
                discord.ChannelType.public_thread,
                discord.ChannelType.private_thread,
            ],
        ),
        trigger: str = ragwort.Option(
            "The trigger of the Truth Bullet to edit.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
    ) -> None:
        await ctx.fetch_config()

        bullet = await models.TruthBullet.find_via_trigger(channel.id, trigger)
        if not bullet:
            raise commands.BadArgument(
                f"Truth Bullet with trigger `{trigger}` does not exist!"
            )

        modal = utils.quick_model(
            discord.ui.Label(
                label="Truth Bullet Trigger",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="truth_bullet_trigger",
                    max_length=60,
                    value=bullet.trigger,
                ),
            ),
            discord.ui.Label(
                label="Truth Bullet Description",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.paragraph,
                    custom_id="truth_bullet_desc",
                    max_length=3800,
                    value=bullet.description,
                ),
            ),
            discord.ui.Label(
                label="Truth Bullet Image",
                description="The image URL of the Truth Bullet.",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    custom_id="truth_bullet_image",
                    max_length=1000,
                    required=False,
                    value=bullet.image,
                ),
            ),
            discord.ui.Label(
                label="Hide this Truth Bullet only to the finder?",
                item=discord.ui.Select(
                    discord.ComponentType.string_select,
                    options=[
                        discord.SelectOption(
                            label=v,
                            value=v.lower(),
                            default=v.lower()
                            == utils.yesno_friendly_str(bullet.hidden),
                        )
                        for v in ("Yes", "No")
                    ],
                    custom_id="truth_bullet_hidden",
                    required=True,
                ),
            ),
            title=(
                f"Edit {utils.short_string(bullet.trigger, 10)} for"
                f" #{utils.short_string(channel.name, 14)}"
            ),
            custom_id=f"ui:edit-bullet-{channel.id}|{trigger}",
        )
        await ctx.send_modal(modal)

    edit_bullet_full = utils.alias(
        edit_bullet,
        name="edit-bullet",
        description="Edits a Truth Bullet. Alias to /bullet-manage edit.",
    )

    @utils.modal_handler(custom_id_prefix="ui:edit-bullet-")
    async def on_modal_edit_bullet(
        self, inter: utils.Interaction, responses: dict[str, typing.Any]
    ) -> None:
        await inter.response.defer()

        channel_id, trigger = (
            inter.data["custom_id"]
            .removeprefix("ui:edit-bullet-")
            .split("|", maxsplit=1)
        )
        channel_id = int(channel_id)

        bullet = await models.TruthBullet.find_via_trigger(channel_id, trigger)
        if bullet is None:
            raise utils.CustomCheckFailure("This Truth Bullet no longer exists.")

        trigger = utils.replace_smart_punc(responses["truth_bullet_trigger"])

        if (
            bullet.trigger.lower() != trigger.lower()
            and await models.TruthBullet.validate(channel_id, trigger)
        ):
            raise commands.BadArgument(
                f"A Truth Bullet in <#{channel_id}> already has the trigger"
                f" `{trigger}` or has an alias named that."
            )

        try:
            if isinstance(responses["truth_bullet_hidden"], list):
                hidden = utils.convert_to_bool(responses["truth_bullet_hidden"][0])
            else:
                hidden = utils.convert_to_bool(responses["truth_bullet_hidden"])
        except commands.BadArgument:
            raise commands.BadArgument(
                "Invalid value for hiding the Truth Bullet. Giving a simple 'yes'"
                " or 'no' will work."
            ) from None

        image: str | None = (
            responses["truth_bullet_image"].strip()
            if responses.get("truth_bullet_image")
            else None
        )
        if image and not utils.HTTP_URL_REGEX.fullmatch(image):
            raise commands.BadArgument("The image given must be a valid URL.")

        bullet.trigger = trigger
        bullet.description = responses["truth_bullet_desc"]
        bullet.hidden = hidden
        bullet.image = image
        await bullet.save(force_update=True)

        if bullet.trigger != trigger:
            await inter.respond(
                view=utils.make_view(
                    f"Edited Truth Bullet `{trigger}` (renamed to"
                    f" `{bullet.trigger}`) in <#{channel_id}>."
                )
            )
        else:
            await inter.respond(
                view=utils.make_view(
                    f"Edited Truth Bullet `{trigger}` in <#{channel_id}>."
                )
            )

    @bullet_manage.command(name="unfind", description="Un-finds a Truth Bullet.")
    async def unfind_bullet(
        self,
        ctx: utils.THIASlashContext,
        channel: discord.TextChannel | discord.Thread = ragwort.Option(
            "The channel the Truth Bullet is in.",
            channel_types=[
                discord.ChannelType.text,
                discord.ChannelType.public_thread,
                discord.ChannelType.private_thread,
            ],
        ),
        trigger: str = ragwort.Option(
            "The trigger of the Truth Bullet to unfind.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
    ) -> None:
        possible_bullet = await models.TruthBullet.find_via_trigger(channel.id, trigger)

        if not possible_bullet:
            raise commands.BadArgument(
                f"Truth Bullet with trigger `{trigger}` does not exist!"
            )
        if not possible_bullet.found:
            raise commands.BadArgument(
                f"Truth Bullet with trigger `{trigger}` has not been found!"
            )

        possible_bullet.found = False
        possible_bullet.finder = None
        await possible_bullet.save(force_update=True)

        await ctx.respond(view=utils.make_view("Truth Bullet un-found!"))

    unfind_bullet_full = utils.alias(
        unfind_bullet,
        name="unfind-bullet",
        description="Un-finds a Truth Bullet. Alias to /bullet-manage unfind.",
    )

    @bullet_manage.command(
        name="override-finder",
        description="Overrides who found a Truth Bullet with the person specified.",
    )
    async def override_bullet(
        self,
        ctx: utils.THIASlashContext,
        channel: discord.TextChannel | discord.Thread = ragwort.Option(
            "The channel the Truth Bullet is in.",
            channel_types=[
                discord.ChannelType.text,
                discord.ChannelType.public_thread,
                discord.ChannelType.private_thread,
            ],
        ),
        trigger: str = ragwort.Option(
            "The trigger of the Truth Bullet to find.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
        user: discord.Member = ragwort.Option(
            "The user who will find the Truth Bullet."
        ),
    ) -> None:
        possible_bullet = await models.TruthBullet.find_via_trigger(channel.id, trigger)
        if not possible_bullet:
            raise commands.BadArgument(f"Truth Bullet with `{trigger}` does not exist!")

        possible_bullet.found = True
        possible_bullet.finder = user.id
        await possible_bullet.save(force_update=True)

        await ctx.respond(view=utils.make_view("Truth Bullet overrided and found!"))

    @bullet_manage.command(
        name="add-alias", description="Adds an alias to the Truth Bullet specified."
    )
    async def add_alias(
        self,
        ctx: utils.THIASlashContext,
        channel: discord.TextChannel | discord.Thread = ragwort.Option(
            "The channel the Truth Bullet is in.",
            channel_types=[
                discord.ChannelType.text,
                discord.ChannelType.public_thread,
                discord.ChannelType.private_thread,
            ],
        ),
        trigger: str = ragwort.Option(
            "The trigger of the Truth Bullet to add an alias to.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
        alias: str = ragwort.Option(
            "The alias to add. Cannot be over 40 characters.",
            input_type=utils.ReplaceSmartPuncConverter,
            max_length=40,
        ),
    ) -> None:
        if len(alias) > 40:
            raise commands.BadArgument(
                "The name is too large for me to use! "
                + "Please use something at or under 40 characters."
            )

        if await models.TruthBullet.exists(
            channel_id=channel.id,
            trigger__iexact=alias,
        ):
            raise commands.BadArgument(
                f"Alias `{alias}` is used as a trigger for another Truth Bullet for"
                " this channel!"
            )

        possible_bullet = await models.TruthBullet.find_via_trigger(channel.id, trigger)
        if not possible_bullet:
            raise commands.BadArgument(
                f"Truth Bullet with trigger `{trigger}` does not exist!"
            )

        if possible_bullet.aliases is None:
            possible_bullet.aliases = []

        if len(possible_bullet.aliases) >= 5:
            raise utils.CustomCheckFailure(
                "Cannot add more aliases to this Truth Bullet!"
            )

        if alias in possible_bullet.aliases:
            raise commands.BadArgument(
                f"Alias `{alias}` already exists for this Truth Bullet!"
            )

        possible_bullet.aliases.append(alias)
        await possible_bullet.save(force_update=True)

        await ctx.respond(
            view=utils.make_view(
                f"Alias `{alias}` added to Truth Bullet with trigger `{trigger}` in"
                f" {channel.mention}!"
            )
        )

    @bullet_manage.command(
        name="remove-alias",
        description="Removes an alias from the Truth Bullet specified.",
    )
    async def remove_alias(
        self,
        ctx: utils.THIASlashContext,
        channel: discord.TextChannel | discord.Thread = ragwort.Option(
            "The channel the Truth Bullet is in.",
            channel_types=[
                discord.ChannelType.text,
                discord.ChannelType.public_thread,
                discord.ChannelType.private_thread,
            ],
        ),
        trigger: str = ragwort.Option(
            "The trigger of the Truth Bullet to remove an alias from.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
        alias: str = ragwort.Option(
            "The alias to remove.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
    ) -> None:
        possible_bullet = await models.TruthBullet.find_via_trigger(channel.id, trigger)
        if not possible_bullet:
            raise commands.BadArgument(f"Truth Bullet with `{trigger}` does not exist!")

        if possible_bullet.aliases is None:
            possible_bullet.aliases = []

        try:
            possible_bullet.aliases.remove(alias)
        except KeyError:
            raise commands.BadArgument(
                f"Alias `{alias}` does not exists for this Truth Bullet!"
            ) from None

        await possible_bullet.save(force_update=True)

        await ctx.send(
            view=utils.make_view(
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
    async def _bullet_trigger_autocomplete(
        self, ctx: discord.AutocompleteContext
    ) -> list[discord.OptionChoice]:
        return await fuzzy.autocomplete_bullets(**ctx.options)

    @remove_alias.autocomplete("alias")
    async def _remove_alias_alias_autocomplete(
        self,
        ctx: discord.AutocompleteContext,
    ) -> list[discord.OptionChoice]:
        return await fuzzy.autocomplete_aliases(**ctx.options)


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(fuzzy)
    importlib.reload(classes)
    bot.add_cog(BulletManagement(bot))
