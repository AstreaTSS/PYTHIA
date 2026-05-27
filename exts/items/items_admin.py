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

import discord
import ragwort
import typing_extensions as typing

import common.classes as classes
import common.fuzzy as fuzzy
import common.models as models
import common.utils as utils

_item_creation_locks: collections.defaultdict[str, asyncio.Lock] = (
    collections.defaultdict(asyncio.Lock)
)


class CreateItemModal(discord.ui.DesignerModal):
    def __init__(self) -> None:
        super().__init__(
            discord.ui.Label(
                label="Item Name",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    max_length=64,
                    custom_id="item_name",
                ),
            ),
            discord.ui.Label(
                label="Item Description",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.paragraph,
                    max_length=3500,
                    custom_id="item_description",
                ),
            ),
            discord.ui.Label(
                label="Item Image",
                description="The image URL of the item.",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    max_length=2000,
                    custom_id="item_image",
                    required=False,
                ),
            ),
            discord.ui.Label(
                label="Is this item takeable?",
                item=discord.ui.RadioGroup(
                    options=[
                        discord.RadioGroupOption(
                            label="Yes", value="yes", default=True
                        ),
                        discord.RadioGroupOption(label="No", value="no"),
                    ],
                    custom_id="item_takeable",
                    required=True,
                ),
            ),
            title="Create Item",
            custom_id="thia-modal:create_item",
        )

    async def callback(self, inter: utils.Interaction) -> None:
        await inter.response.defer()

        responses = utils.parse_modal_responses(self)
        name = utils.replace_smart_punc(responses["item_name"])

        async with _item_creation_locks[f"{inter.guild_id}-{name.lower()}"]:
            if await models.ItemsSystemItem.exists(
                guild_id=int(inter.guild_id), name__iexact=name
            ):
                raise utils.BadArgument(
                    f"An item named `{discord.utils.escape_markdown(name)}` already"
                    " exists in this server."
                )

            try:
                if isinstance(responses["item_takeable"], list):
                    takeable = utils.convert_to_bool(responses["item_takeable"][0])
                else:
                    takeable = utils.convert_to_bool(responses["item_takeable"])
            except utils.BadArgument:
                raise utils.BadArgument(
                    "Invalid value for if the item is takeable. Giving a simple"
                    " 'yes' or 'no' will work."
                ) from None

            image: str | None = (
                responses["item_image"].strip() if responses.get("item_image") else None
            )
            if image and not utils.HTTP_URL_REGEX.fullmatch(image):
                raise utils.BadArgument("The image given must be a valid URL.")

            await models.GuildConfig.fetch_create(inter.guild_id, {"items": True})

            await models.ItemsSystemItem.create(
                name=name,
                description=responses["item_description"],
                image=image,
                takeable=takeable,
                guild_id=inter.guild_id,
            )

        await inter.respond(
            view=utils.make_view(
                f"Created item `{discord.utils.escape_markdown(name)}`."
            ),
        )


create_item_button = classes.ButtonToModal(
    text="Create items through this button!",
    button=discord.ui.Button(
        style=discord.ButtonStyle.green,
        label="Create item",
        custom_id="thia-button:create_item",
    ),
    modal=CreateItemModal,
)


class EditItemModal(discord.ui.DesignerModal):
    def __init__(self, item: models.ItemsSystemItem) -> None:
        super().__init__(
            discord.ui.Label(
                label="Item Name",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    max_length=64,
                    custom_id="item_name",
                    value=item.name,
                ),
            ),
            discord.ui.Label(
                label="Item Description",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.paragraph,
                    max_length=3500,
                    custom_id="item_description",
                    value=item.description,
                ),
            ),
            discord.ui.Label(
                label="Item Image",
                description="The image URL of the item.",
                item=discord.ui.InputText(
                    style=discord.InputTextStyle.short,
                    max_length=2000,
                    custom_id="item_image",
                    required=False,
                    value=item.image,
                ),
            ),
            discord.ui.Label(
                label="Is this item takeable?",
                item=discord.ui.RadioGroup(
                    options=[
                        discord.RadioGroupOption(
                            label=v,
                            value=v.lower(),
                            default=v.lower()
                            == utils.yesno_friendly_str(item.takeable),
                        )
                        for v in ("Yes", "No")
                    ],
                    custom_id="item_takeable",
                    required=True,
                ),
            ),
            title="Edit Item",
            custom_id=f"thia:edit_item-{item.id}",
        )
        self.item = item

    async def callback(self, inter: utils.Interaction) -> None:
        await inter.response.defer()

        responses = utils.parse_modal_responses(self)

        # quick re-verify
        item = await models.ItemsSystemItem.get_or_none(id=self.item.id)
        if not item:
            raise utils.BadArgument("This item no longer exists.")

        old_name = item.name
        name = utils.replace_smart_punc(responses["item_name"])

        if name.lower() != old_name.lower() and await models.ItemsSystemItem.exists(
            guild_id=int(inter.guild_id), name__iexact=name
        ):
            raise utils.BadArgument(
                f"An item named `{name}` already exists in this server."
            )

        try:
            if isinstance(responses["item_takeable"], list):
                takeable = utils.convert_to_bool(responses["item_takeable"][0])
            else:
                takeable = utils.convert_to_bool(responses["item_takeable"])
        except utils.BadArgument:
            raise utils.BadArgument(
                "Invalid value for if the item is takeable. Giving a simple"
                " 'yes' or 'no' will work."
            ) from None

        image: str | None = (
            responses["item_image"].strip() if responses.get("item_image") else None
        )
        if image and not utils.HTTP_URL_REGEX.fullmatch(image):
            raise utils.BadArgument("The image given must be a valid URL.")

        item.name = name
        item.description = responses["item_description"]
        item.image = image
        item.takeable = takeable
        await item.save()

        if name != old_name:
            await inter.respond(
                view=utils.make_view(
                    f"Edited item `{discord.utils.escape_markdown(old_name)}`, now"
                    f" renamed to `{discord.utils.escape_markdown(name)}`."
                )
            )
        else:
            await inter.respond(
                view=utils.make_view(
                    f"Edited item `{discord.utils.escape_markdown(name)}`."
                )
            )


class ItemsManagement(utils.Cog):
    def __init__(self, bot: utils.THIABase) -> None:
        self.bot = bot
        self.__cog_name__ = "Items Management"

        self.bot.add_view(create_item_button)

        # i sure do love weird edge cases with race conditions!
        self.item_creation_locks: collections.defaultdict[str, asyncio.Lock] = (
            collections.defaultdict(asyncio.Lock)
        )

    config = ragwort.SlashCommandGroup(
        name="items-config",
        description="Handles configuration of items.",
        default_member_permissions=discord.Permissions(manage_guild=True),
        contexts={
            discord.InteractionContextType.guild,
        },
    )

    @config.command(
        name="info",
        description="Lists out the items configuration settings for the server.",
    )
    async def items_info(self, ctx: utils.THIASlashContext) -> None:
        config = await ctx.fetch_config({"items": True})
        if typing.TYPE_CHECKING:
            assert config.items and isinstance(config.items, models.ItemsConfig)

        options = (
            f"Enabled: {utils.yesno_friendly_str(config.items.enabled)}",
            f"Auto-Suggestions: {utils.toggle_friendly_str(config.items.autosuggest)}",
        )
        await ctx.respond(
            view=utils.make_view("\n".join(options), title="Items Configuration")
        )

    @config.command(
        name="toggle",
        description="Enables or disables the items system.",
    )
    async def items_toggle(
        self,
        ctx: utils.THIASlashContext,
        _toggle: str = ragwort.Option(
            "Should the items system be turned on or off?",
            name="toggle",
            choices=[
                discord.OptionChoice("on", "on"),
                discord.OptionChoice("off", "off"),
            ],
        ),
    ) -> None:
        toggle = _toggle == "on"
        config = await ctx.fetch_config({"items": True})
        if typing.TYPE_CHECKING:
            assert config.items and isinstance(config.items, models.ItemsConfig)

        if toggle and not config.player_role:
            raise utils.CustomCheckFailure(
                "Player role not set. Please set it with `/config player set` first."
            )

        config.items.enabled = toggle
        await config.items.save()

        await ctx.respond(
            view=utils.make_view(
                f"Items system turned {utils.toggle_friendly_str(toggle)}."
            )
        )

    @config.command(
        name="auto-suggestions",
        description="Enables or disables auto-suggestions when investigating items.",
    )
    async def auto_suggestions_toggle(
        self,
        ctx: utils.THIASlashContext,
        _toggle: str = ragwort.Option(
            "Should auto-suggestions be turned on or off?",
            name="toggle",
            choices=[
                discord.OptionChoice("on", "on"),
                discord.OptionChoice("off", "off"),
            ],
        ),
    ) -> None:
        toggle = _toggle == "on"
        config = await ctx.fetch_config({"items": True})
        if typing.TYPE_CHECKING:
            assert config.items and isinstance(config.items, models.ItemsConfig)

        config.items.autosuggest = toggle
        await config.items.save()

        await ctx.respond(
            view=utils.make_view(
                f"Auto-suggestions turned {utils.toggle_friendly_str(toggle)}."
            )
        )

    @config.command(
        name="help", description="Tells you how to set up the items system."
    )
    async def items_help(self, ctx: utils.THIASlashContext) -> None:
        container = utils.make_container(
            "To set up the items system, follow the items setup guide below.",
            title="Set Up Items System",
        )
        container.add_separator(divider=False)
        container.add_row(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label="Items Setup Guide",
                url="https://pythia.astrea.cc/setup/items_setup",
            )
        )
        await ctx.respond(view=utils.quick_view(container))

    manage = ragwort.SlashCommandGroup(
        name="items-manage",
        description="Handles management of items.",
        default_member_permissions=discord.Permissions(manage_guild=True),
        contexts={
            discord.InteractionContextType.guild,
        },
    )

    @manage.command(
        name="create-item",
        description="Creates an investigable item.",
    )
    @ragwort.auto_defer(enabled=False)
    async def item_create(
        self,
        ctx: utils.THIASlashContext,
        _send_button: str = ragwort.Option(
            "Should a button be sent that allows for repeatedly creating items?",
            name="send_button",
            choices=[
                discord.OptionChoice("yes", "yes"),
                discord.OptionChoice("no", "no"),
            ],
            default="yes",
        ),
    ) -> None:
        send_button = _send_button == "yes"

        if send_button:
            await ctx.respond(view=create_item_button)
            return

        await ctx.send_modal(CreateItemModal())

    @manage.command(name="edit-item", description="Sends a prompt to edit an item.")
    @ragwort.auto_defer(enabled=False)
    async def edit_item(
        self,
        ctx: utils.THIASlashContext,
        name: str = ragwort.Option(
            "The name of the item to edit.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
    ) -> None:
        item = await models.ItemsSystemItem.get_or_none(
            guild_id=ctx.guild_id,
            name=name,
        )
        if not item:
            raise utils.BadArgument(
                f"Item `{discord.utils.escape_markdown(name)}` does not exist in this"
                " server."
            )

        await ctx.send_modal(EditItemModal(item))

    @manage.command(
        name="list-items",
        description="Lists all items in the server.",
    )
    async def list_items(
        self,
        ctx: utils.THIASlashContext,
        mode: str = ragwort.Option(
            "The mode to show the list of items in.",
            choices=[
                discord.OptionChoice("Cozy", "cozy"),
                discord.OptionChoice("Compact", "compact"),
            ],
            default="cozy",
        ),
    ) -> None:
        if mode not in ("cozy", "compact"):
            raise utils.BadArgument("Invalid mode.")

        items = await models.ItemsSystemItem.filter(guild_id=ctx.guild_id)
        if not items:
            raise utils.CustomCheckFailure("This server has no items to show.")

        items_list = [
            (
                f"**{discord.utils.escape_markdown(i.name)}**:"
                f" {models.short_desc(i.description)}"
                if mode == "compact"
                else (
                    f"**{discord.utils.escape_markdown(i.name)}**\n-#"
                    f" {models.short_desc(i.description, 70)}"
                )
            )
            for i in sorted(items, key=lambda i: i.name.lower())
        ]
        limit = 15 if mode == "cozy" else 30

        chunks = [items_list[x : x + limit] for x in range(0, len(items_list), limit)]
        items = [[discord.ui.TextDisplay("\n".join(chunk))] for chunk in chunks]

        pag = classes.ContainerPaginator(*items, title="Items", author_id=ctx.author.id)
        await ctx.respond(view=pag)

    @manage.command(
        name="list-placed-items",
        description="Lists all items currently placed in channels.",
    )
    async def list_placed_items(self, ctx: utils.THIASlashContext) -> None:
        placed_items = await models.ItemRelation.filter(
            guild_id=ctx.guild_id,
            object_type=models.ItemsRelationType.CHANNEL,
        ).prefetch_related("item")
        if not placed_items:
            raise utils.CustomCheckFailure(
                "This server has no items placed in channels."
            )

        items_dict: collections.defaultdict[
            int, collections.Counter[models.ItemHash]
        ] = collections.defaultdict(collections.Counter)

        for item in placed_items:
            items_dict[item.object_id][models.ItemHash(item.item)] += 1

        str_builder: collections.deque[str] = collections.deque()

        for channel_id in items_dict.keys():
            str_builder.append(f"<#{channel_id}>:")

            for k, v in sorted(
                items_dict[channel_id].items(), key=lambda i: i[0].item.name.lower()
            ):
                str_builder.append(
                    f"- **{discord.utils.escape_markdown(k.item.name)}** x{v}"
                )

            str_builder.append("")

        pag = classes.ContainerPaginator.create_from_list(
            str_builder, title="Placed Items", author_id=ctx.author.id
        )
        await ctx.respond(view=pag)

    @manage.command(
        name="list-items-in-channel",
        description="Lists all items in a channel.",
    )
    async def list_items_in_channel(
        self,
        ctx: utils.THIASlashContext,
        channel: discord.TextChannel | discord.Thread = ragwort.Option(
            "The channel to list items for.",
            channel_types=[
                discord.ChannelType.text,
                discord.ChannelType.public_thread,
                discord.ChannelType.private_thread,
            ],
        ),
        mode: str = ragwort.Option(
            "The mode to show the list of items in.",
            choices=[
                discord.OptionChoice("Cozy", "cozy"),
                discord.OptionChoice("Compact", "compact"),
            ],
            default="cozy",
        ),
    ) -> None:
        if mode not in ("cozy", "compact"):
            raise utils.BadArgument("Invalid mode.")

        channel_items = await models.ItemRelation.filter(
            object_id=channel.id,
        ).prefetch_related("item")
        if not channel_items:
            raise utils.CustomCheckFailure("This channel has no items placed in it.")

        items_counter: collections.Counter[models.ItemHash] = collections.Counter()

        for item in channel_items:
            items_counter[models.ItemHash(item.item)] += 1

        str_builder: list[str] = []

        for k, v in sorted(items_counter.items(), key=lambda i: i[0].item.name.lower()):
            if mode == "compact":
                str_builder.append(
                    f"**{discord.utils.escape_markdown(k.item.name)}**{f' (x{v})' if v > 1 else ''}:"
                    f" {models.short_desc(k.item.description)}"
                )
            else:
                str_builder.append(
                    f"**{discord.utils.escape_markdown(k.item.name)}**{f' (x{v})' if v > 1 else ''}\n-#"
                    f" {models.short_desc(k.item.description, 70)}"
                )

        limit = 15 if mode == "cozy" else 30

        chunks = [str_builder[x : x + limit] for x in range(0, len(str_builder), limit)]
        items = [[discord.ui.TextDisplay("\n".join(chunk))] for chunk in chunks]

        pag = classes.ContainerPaginator(
            *items, title=f"Items in #{channel.name}", author_id=ctx.author.id
        )
        await ctx.respond(view=pag)

    @manage.command(
        name="place-item-in-channel",
        description="Places an item in a channel.",
    )
    async def place_item_in_channel(
        self,
        ctx: utils.THIASlashContext,
        name: str = ragwort.Option(
            "The name of the item to place.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
        channel: discord.TextChannel | discord.Thread = ragwort.Option(
            "The channel to place the item in.",
            channel_types=[
                discord.ChannelType.text,
                discord.ChannelType.public_thread,
                discord.ChannelType.private_thread,
            ],
        ),
        amount: int = ragwort.Option(
            "The amount of the item to place. Defaults to 1.",
            min_value=1,
            max_value=50,
            default=1,
        ),
    ) -> None:
        item = await models.ItemsSystemItem.get_or_none(
            guild_id=ctx.guild_id,
            name=name,
        )
        if not item:
            raise utils.BadArgument(
                f"Item `{discord.utils.escape_markdown(name)}` does not exist in this"
                " server."
            )

        if not item.takeable and amount > 1:
            raise utils.CustomCheckFailure(
                "This item is not takeable, so you can only place one of it per"
                " channel."
            )

        if await models.ItemRelation.filter(
            item_id=item.id, object_id=channel.id
        ).count() >= (50 if item.takeable else 1):
            if item.takeable:
                raise utils.CustomCheckFailure(
                    "You cannot place more than 50 of the same item in a channel."
                )
            raise utils.CustomCheckFailure(
                "You cannot place more than 1 of a non-takeable item in a channel."
            )

        await models.ItemRelation.bulk_create(
            models.ItemRelation(
                item_id=item.id,
                guild_id=ctx.guild_id,
                object_id=int(channel.id),
                object_type=models.ItemsRelationType.CHANNEL,
            )
            for _ in range(amount)
        )

        await ctx.respond(
            view=utils.make_view(
                f"Placed {amount} of item `{discord.utils.escape_markdown(name)}` in"
                f" <#{channel.id}>."
            )
        )

    @manage.command(
        name="remove-item-from-channel",
        description="Removes an item from a channel.",
    )
    async def remove_item_from_channel(
        self,
        ctx: utils.THIASlashContext,
        channel: discord.TextChannel | discord.Thread = ragwort.Option(
            "The channel to remove the item from.",
            channel_types=[
                discord.ChannelType.text,
                discord.ChannelType.public_thread,
                discord.ChannelType.private_thread,
            ],
        ),
        name: str = ragwort.Option(
            "The name of the item to remove.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
        amount: int = ragwort.Option(
            "The amount of the item to remove. Defaults to 1.",
            min_value=1,
            max_value=50,
            default=1,
        ),
    ) -> None:
        item = await models.ItemsSystemItem.get_or_none(
            guild_id=ctx.guild_id,
            name=name,
        )
        if not item:
            raise utils.BadArgument(
                f"Item `{discord.utils.escape_markdown(name)}` does not exist in this"
                " server."
            )

        total = await models.ItemRelation.filter(
            item_id=item.id, object_id=channel.id
        ).count()

        if amount >= total:
            amount = total
            await models.ItemRelation.filter(
                item_id=item.id, object_id=channel.id
            ).delete()
        elif total == 0:
            raise utils.CustomCheckFailure(
                "There are no items of this type in the channel."
            )
        else:
            to_delete = (
                await models.ItemRelation.filter(item_id=item.id, object_id=channel.id)
                .limit(amount)
                .values_list("id", flat=True)
            )
            await models.ItemRelation.filter(id__in=to_delete).delete()

        await ctx.respond(
            view=utils.make_view(
                f"Removed {amount} of item `{discord.utils.escape_markdown(name)}` from"
                f" <#{channel.id}>."
            )
        )

    @manage.command(
        name="view-item",
        description="Shows information about an item.",
    )
    async def view_item(
        self,
        ctx: utils.THIASlashContext,
        name: str = ragwort.Option(
            "The name of the item to view.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
        _view_possessors: str = ragwort.Option(
            "Should the possessors of this item (channels and users) be shown?",
            name="view_possessors",
            choices=[
                discord.OptionChoice("yes", "yes"),
                discord.OptionChoice("no", "no"),
            ],
            default="no",
        ),
    ) -> None:
        view_possessors = _view_possessors == "yes"

        queryset = models.ItemsSystemItem.get_or_none(
            guild_id=ctx.guild_id,
            name=name,
        )
        if view_possessors:
            queryset = queryset.prefetch_related("relations")

        item = await queryset
        if not item:
            raise utils.BadArgument(
                f"Item `{discord.utils.escape_markdown(name)}` does not exist in this"
                " server."
            )

        embeds = item.embeds()

        if len(embeds) > 1:
            pag = classes.EmbedPaginator(*embeds, author_id=ctx.author.id)
            await pag.respond(ctx)
        else:
            await ctx.respond(embeds=embeds)

    @manage.command(
        name="delete-item",
        description="Deletes an item.",
    )
    async def delete_item(
        self,
        ctx: utils.THIASlashContext,
        name: str = ragwort.Option(
            "The name of the item to delete.",
            input_type=utils.ReplaceSmartPuncConverter,
        ),
    ) -> None:
        count = await models.ItemsSystemItem.filter(
            guild_id=ctx.guild_id, name=name
        ).delete()
        if count == 0:
            raise utils.BadArgument(
                f"Item `{discord.utils.escape_markdown(name)}` does not exist in this"
                " server."
            )

        await ctx.respond(
            view=utils.make_view(
                f"Deleted item `{discord.utils.escape_markdown(name)}`."
            )
        )

    @manage.command(
        name="clear-items-in-channel",
        description="Clears all items in a channel.",
    )
    async def clear_items_in_channel(
        self,
        ctx: utils.THIASlashContext,
        channel: discord.TextChannel | discord.Thread = ragwort.Option(
            "The channel to clear items from.",
            channel_types=[
                discord.ChannelType.text,
                discord.ChannelType.public_thread,
                discord.ChannelType.private_thread,
            ],
        ),
    ) -> None:
        count = await models.ItemRelation.filter(
            object_id=channel.id,
        ).delete()
        if count == 0:
            raise utils.CustomCheckFailure(
                "There are no items to clear from this channel."
            )

        await ctx.respond(
            view=utils.make_view(f"Cleared all items from <#{channel.id}>.")
        )

    @manage.command(
        name="clear-everything",
        description=(
            "Clears ALL items data (except config data) in this server."
            " Use with caution!"
        ),
    )
    async def clear_everything(
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

        items_amount = await models.ItemRelation.filter(
            guild_id=ctx.guild_id,
        ).delete()

        if items_amount <= 0:
            raise utils.CustomCheckFailure("There's no items data to clear!")

        await ctx.respond(view=utils.make_view("All items data cleared."))

    @edit_item.autocomplete("name")
    @place_item_in_channel.autocomplete("name")
    @view_item.autocomplete("name")
    @delete_item.autocomplete("name")
    async def _item_name_autocomplete(
        self, ctx: discord.AutocompleteContext
    ) -> list[discord.OptionChoice]:
        return await fuzzy.autocomplete_item(
            ctx,
            **ctx.options,
        )

    @remove_item_from_channel.autocomplete("name")
    async def _channel_item_name_autocomplete(
        self, ctx: discord.AutocompleteContext
    ) -> list[discord.OptionChoice]:
        return await fuzzy.autocomplete_item_channel(
            ctx,
            **ctx.options,
        )


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(classes)
    importlib.reload(fuzzy)
    bot.add_cog(ItemsManagement(bot))
