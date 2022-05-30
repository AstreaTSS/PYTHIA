import collections
import importlib
import typing

import naff

import common.fuzzy as fuzzy
import common.models as models
import common.utils as utils


class BulletCMDs(utils.Extension):
    """Commands for using and modifying Truth Bullets."""

    def __init__(self, bot):
        self.name = "Bullet"
        self.bot = bot

    @naff.prefixed_command()
    @utils.proper_permissions()
    async def add_bullet(
        self,
        ctx: naff.PrefixedContext,
        channel: typing.Annotated[naff.GuildText, utils.ValidChannelConverter],
        name: str,
        *,
        description: str,
    ):
        """Adds a Truth Bullet to the list of Truth Bullets.
        Requires a channel (mentions or IDS work), name, and description of the Bullet itself.
        If you wish for the name/trigger to be more than one word, put quotes around it.
        The name must be under or at 100 characters, and the description must be at or under 3900 characters.
        Requires being able to Manage Truth Bullets."""

        if len(name) > 100:
            raise naff.errors.BadArgument(
                "The name is too large for me to use! "
                + "Please use something at or under 100 characters."
            )
        if len(description) > 3900:
            raise naff.errors.BadArgument(
                "The description is too large for me to use! "
                + "Please use something at or under 3900 characters, or consider using"
                " a Google "
                + "Doc to store the text."
            )

        async with ctx.channel.typing:
            possible_duplicate = await models.TruthBullet.exists(
                channel_id=channel.id, name=name
            )
            if possible_duplicate:
                raise naff.errors.BadArgument(f"Truth Bullet `{name}` already exists!")

            await models.TruthBullet.create(
                name=name,
                aliases=set(),
                description=description,
                channel_id=channel.id,
                guild_id=ctx.guild.id,
                found=False,
                finder=0,
            )

        await ctx.message.reply("Added Truth Bullet!")

    @utils.manage_guild_slash_cmd(
        name="add-bullets",
        description="Open a prompt to add Truth Bullets to a specified channel.",
    )
    @naff.slash_option(
        "channel",
        "The channel for the Truth Bullets to be added.",
        naff.OptionTypes.CHANNEL,
        required=True,
        channel_types=[
            naff.ChannelTypes.GUILD_TEXT,
            naff.ChannelTypes.GUILD_PUBLIC_THREAD,
        ],
    )
    async def add_bullets(
        self,
        ctx: naff.InteractionContext,
        channel: typing.Annotated[naff.GuildText, utils.ValidChannelSlashConverter],
    ):
        button = naff.Button(
            style=naff.ButtonStyles.GREEN,
            label=f"Add Truth Bullets for #{channel.name}",
            custom_id=f"ui-button:add_bullets-{channel.id}",
        )

        await ctx.send(
            content="Add Truth Bullets via the button below!", components=button
        )

    @naff.listen("component")
    async def on_add_bullets_button(self, event: naff.events.Component):
        ctx = event.context

        if ctx.custom_id.startswith("ui-button:add_bullets-"):
            channel_id = int(ctx.custom_id.removeprefix("ui-button:add_bullets-"))
            channel = self.bot.get_channel(channel_id)

            modal = naff.Modal(
                title=f"Add Truth Bullets for #{channel.name}",
                components=[
                    naff.ShortText(
                        label="What's the name of the Truth Bullet?",
                        custom_id="truth_bullet_name",
                        max_length=100,
                    ),
                    naff.ParagraphText(
                        label="What's the description of the Truth Bullet?",
                        custom_id="truth_bullet_desc",
                        max_length=3900,
                    ),
                ],
                custom_id=f"ui-modal:add_bullets-{channel.id}",
            )
            await ctx.send_modal(modal)

    @naff.listen("modal_response")
    async def on_modal_add_bullet(self, event: naff.events.ModalResponse):
        ctx = event.context

        if ctx.custom_id.startswith("ui-modal:add_bullets-"):
            channel_id = int(ctx.custom_id.removeprefix("ui-modal:add_bullets-"))

            possible_duplicate = await models.TruthBullet.exists(
                channel_id=channel_id,
                name=ctx.responses["truth_bullet_name"],
            )
            if possible_duplicate:
                await ctx.send(
                    f"Truth Bullet `{ctx.responses['truth_bullet_name']}` already"
                    " exists!"
                )
                return

            await models.TruthBullet.create(
                name=ctx.responses["truth_bullet_name"],
                aliases=set(),
                description=ctx.responses["truth_bullet_desc"],
                channel_id=channel_id,
                guild_id=ctx.guild.id,
                found=False,
                finder=0,
            )

            await ctx.send(
                f"Added Truth Bullet `{ctx.responses['truth_bullet_name']}`!"
            )

    @utils.manage_guild_slash_cmd(
        "remove-bullet",
        description="Removes a Truth Bullet from the list of Truth Bullets.",
    )
    @naff.slash_option(
        "channel",
        "The channel for the Truth Bullet to be removed.",
        naff.OptionTypes.CHANNEL,
        required=True,
        channel_types=[
            naff.ChannelTypes.GUILD_TEXT,
            naff.ChannelTypes.GUILD_PUBLIC_THREAD,
        ],
    )
    @naff.slash_option(
        "name",
        "The name of the Truth Bullet to be removed.",
        naff.OptionTypes.STRING,
        required=True,
        autocomplete=True,
    )
    async def remove_bullet(
        self,
        ctx: naff.InteractionContext,
        channel: naff.GuildText,
        name: str,
    ):
        await ctx.defer()

        num_deleted = await models.TruthBullet.filter(
            channel_id=channel.id, name=name
        ).delete()

        if num_deleted > 0:
            await ctx.send(f"`{name}` deleted!")
        else:
            raise naff.errors.BadArgument(f"Truth Bullet `{name}` does not exists!")

    @remove_bullet.autocomplete("name")
    async def _remove_bullet_autocomplete(
        self, ctx: naff.AutocompleteContext, **kwargs
    ):
        return await fuzzy.autocomplete_bullets(ctx, **kwargs)

    @utils.manage_guild_slash_cmd(
        "clear-bullets",
        description=(
            "Removes all Truth Bullets from the list of Truth Bullets. This action is"
            " irreversible."
        ),
    )
    async def clear_bullets(self, ctx: naff.InteractionContext):
        await ctx.defer()

        num_deleted = await models.TruthBullet.filter(guild_id=ctx.guild.id).delete()

        # just to give a more clear indication to users
        # technically everything's fine without this
        if num_deleted > 0:
            await ctx.send("Cleared all Truth Bullets for this server!")
        else:
            raise utils.CustomCheckFailure(
                "There's no Truth Bullets to delete for this server!"
            )

    @utils.manage_guild_slash_cmd(
        "list-bullets", "Lists all Truth Bullets in the server this is run in."
    )
    async def list_bullets(self, ctx: naff.InteractionContext):
        await ctx.defer()

        guild_bullets = await models.TruthBullet.filter(guild_id=ctx.guild.id)
        if not guild_bullets:
            raise utils.CustomCheckFailure("There's no Truth Bullets for this server!")

        bullet_dict: typing.DefaultDict[
            int, list[models.TruthBullet]
        ] = collections.defaultdict(list)
        for bullet in guild_bullets:
            bullet_dict[bullet.channel_id].append(bullet)

        str_builder = collections.deque()

        for channel_id in bullet_dict.keys():
            str_builder.append(f"<#{channel_id}>:")
            for bullet in bullet_dict[channel_id]:
                str_builder.append(
                    f"\t- `{bullet.name}`{' (found)' if bullet.found else ''}"
                )

            str_builder.append("")

        chunks = utils.line_split("\n".join(str_builder), split_by=30)
        for chunk in chunks:
            await ctx.send("\n".join(chunk))

    @utils.manage_guild_slash_cmd(
        "bullet-info", "Lists all information about a Truth Bullet."
    )
    @naff.slash_option(
        "channel",
        "The channel the Truth Bullet is in.",
        naff.OptionTypes.CHANNEL,
        required=True,
        channel_types=[
            naff.ChannelTypes.GUILD_TEXT,
            naff.ChannelTypes.GUILD_PUBLIC_THREAD,
        ],
    )
    @naff.slash_option(
        "name",
        "The name of the Truth Bullet.",
        naff.OptionTypes.STRING,
        required=True,
        autocomplete=True,
    )
    async def bullet_info(
        self,
        ctx: naff.InteractionContext,
        channel: naff.GuildText,
        name: str,
    ):
        await ctx.defer()

        possible_bullet = await models.TruthBullet.get_or_none(
            channel_id=channel.id, name=name
        )

        if possible_bullet is None:
            raise naff.errors.BadArgument(f"Truth Bullet `{name}` does not exist!")

        await ctx.send(
            str(possible_bullet), allowed_mentions=utils.deny_mentions(ctx.author)
        )

    @bullet_info.autocomplete("name")
    async def _bullet_info_autocomplete(self, ctx: naff.AutocompleteContext, **kwargs):
        return await fuzzy.autocomplete_bullets(ctx, **kwargs)

    @naff.prefixed_command(name="edit_bullet")
    @utils.bullet_proper_perms()
    async def edit_bullet_legacy(
        self,
        ctx: naff.PrefixedContext,
        channel: naff.GuildText,
        name: str,
        *,
        description: str,
    ):
        """Edits a Truth Bullet.
        Requires a channel (mentions or IDS work), the name, and a new description of the Bullet itself.
        If the name/trigger has more than one word, put quotes around it.
        The new description must be at or under 3900 characters.
        Requires being able to Manage Truth Bullets."""

        if len(description) > 3900:
            raise naff.errors.BadArgument(
                "The description is too large for me to use! "
                + "Please use something at or under 3900 characters, or consider using"
                " a Google "
                + "Doc to store the text."
            )

        async with ctx.channel.typing:
            possible_bullet = await models.TruthBullet.get_or_none(
                channel_id=channel.id, name=name
            )
            if possible_bullet is None:
                raise naff.errors.BadArgument(f"Truth Bullet `{name}` does not exist!")

            possible_bullet.description = description
            await possible_bullet.save()

        await ctx.message.reply("Edited Truth Bullet!")

    @utils.manage_guild_slash_cmd(
        "edit-bullet", "Sends a prompt to edit a Truth Bullet."
    )
    @naff.slash_option(
        "channel",
        "The channel the Truth Bullet is in.",
        naff.OptionTypes.CHANNEL,
        required=True,
        channel_types=[
            naff.ChannelTypes.GUILD_TEXT,
            naff.ChannelTypes.GUILD_PUBLIC_THREAD,
        ],
    )
    @naff.slash_option(
        "name",
        "The name of the Truth Bullet to edit.",
        naff.OptionTypes.STRING,
        required=True,
        autocomplete=True,
    )
    async def edit_bullet(
        self,
        ctx: naff.InteractionContext,
        channel: naff.GuildText,
        name: str,
    ):
        possible_bullet = await models.TruthBullet.get_or_none(
            channel_id=channel.id, name=name
        )
        if possible_bullet is None:
            raise naff.errors.BadArgument(f"Truth Bullet `{name}` does not exist!")

        modal = naff.Modal(
            title=f"Edit {possible_bullet.name} for #{channel.name}",
            components=[
                naff.ParagraphText(
                    "New description",
                    "description",
                    value=possible_bullet.description,
                    max_length=3900,
                )
            ],
            custom_id=f"ui:edit-bullet-{channel.id}|{name}",
        )
        await ctx.send_modal(modal)
        await ctx.send("Done!")

    @edit_bullet.autocomplete("name")
    async def _edit_bullet_autocomplete(self, ctx: naff.AutocompleteContext, **kwargs):
        return await fuzzy.autocomplete_bullets(ctx, **kwargs)

    @naff.listen("modal_response")
    async def on_modal_edit_bullet(self, event: naff.events.ModalResponse):
        ctx = event.context

        if ctx.custom_id.startswith("ui:edit-bullet-"):
            channel_id, name = ctx.custom_id.removeprefix("ui:edit-bullet-").split(
                "|", maxsplit=1
            )
            channel_id = int(channel_id)

            possible_bullet = await models.TruthBullet.get_or_none(
                channel_id=channel_id, name=name
            )
            if possible_bullet is None:
                await ctx.send(f"Truth Bullet `{name}` no longer exists!")
                return

            possible_bullet.description = ctx.responses["description"]
            await possible_bullet.save()

            await ctx.send(f"Edited Truth Bullet `{ctx.responses['description']}`!")

    @utils.manage_guild_slash_cmd("unfind-bullet", "Un-finds a Truth Bullet.")
    @naff.slash_option(
        "channel",
        "The channel the Truth Bullet is in.",
        naff.OptionTypes.CHANNEL,
        required=True,
        channel_types=[
            naff.ChannelTypes.GUILD_TEXT,
            naff.ChannelTypes.GUILD_PUBLIC_THREAD,
        ],
    )
    @naff.slash_option(
        "name",
        "The name of the Truth Bullet to un-find.",
        naff.OptionTypes.STRING,
        required=True,
        autocomplete=True,
    )
    async def unfind_bullet(
        self, ctx: naff.InteractionContext, channel: naff.GuildText, name: str
    ):
        await ctx.defer()

        possible_bullet = await models.TruthBullet.get_or_none(
            channel_id=channel.id, name=name
        )

        if possible_bullet is None:
            raise naff.errors.BadArgument(f"Truth Bullet `{name}` does not exist!")
        if not possible_bullet.found:
            raise naff.errors.BadArgument(f"Truth Bullet `{name}` has not been found!")

        possible_bullet.found = False
        possible_bullet.finder = 0
        await possible_bullet.save()

        await ctx.send("Truth Bullet un-found!")

    @unfind_bullet.autocomplete("name")
    async def _unfind_bullet_autocomplete(
        self, ctx: naff.AutocompleteContext, **kwargs
    ):
        return await fuzzy.autocomplete_bullets(ctx, **kwargs)

    @utils.manage_guild_slash_cmd(
        "override-bullet",
        "Overrides who found a Truth Bullet with the person specified.",
    )
    @naff.slash_option(
        "channel",
        "The channel the Truth Bullet is in.",
        naff.OptionTypes.CHANNEL,
        required=True,
        channel_types=[
            naff.ChannelTypes.GUILD_TEXT,
            naff.ChannelTypes.GUILD_PUBLIC_THREAD,
        ],
    )
    @naff.slash_option(
        "name",
        "The name of the Truth Bullet to override.",
        naff.OptionTypes.STRING,
        required=True,
        autocomplete=True,
    )
    @naff.slash_option(
        "user",
        "The user who will not 'find' the Truth Bullet.",
        naff.OptionTypes.USER,
        required=True,
    )
    async def override_bullet(
        self,
        ctx: naff.InteractionContext,
        channel: naff.GuildText,
        name: str,
        user: naff.Member,
    ):
        await ctx.defer()

        possible_bullet = await models.TruthBullet.get_or_none(
            channel_id=channel.id, name=name
        )
        if possible_bullet is None:
            raise naff.errors.BadArgument(f"Truth Bullet `{name}` does not exist!")

        possible_bullet.found = True
        possible_bullet.finder = user.id
        await possible_bullet.save()

        await ctx.send("Truth Bullet overrided and found!")

    @override_bullet.autocomplete("name")
    async def _override_bullet_autocomplete(
        self, ctx: naff.AutocompleteContext, **kwargs
    ):
        return await fuzzy.autocomplete_bullets(ctx, **kwargs)

    @utils.manage_guild_slash_cmd(
        "add-alias", "Adds an alias to the Truth Bullet specified."
    )
    @naff.slash_option(
        "channel",
        "The channel the Truth Bullet is in.",
        naff.OptionTypes.CHANNEL,
        required=True,
        channel_types=[
            naff.ChannelTypes.GUILD_TEXT,
            naff.ChannelTypes.GUILD_PUBLIC_THREAD,
        ],
    )
    @naff.slash_option(
        "name",
        "The name of the Truth Bullet to add an alias to.",
        naff.OptionTypes.STRING,
        required=True,
        autocomplete=True,
    )
    @naff.slash_option(
        "alias",
        "The alias to add. Cannot be over 40 characters.",
        naff.OptionTypes.STRING,
        required=True,
    )
    async def add_alias(
        self,
        ctx: naff.InteractionContext,
        channel: naff.GuildText,
        name: str,
        alias: str,
    ):
        if len(alias) > 40:
            raise naff.errors.BadArgument(
                "The name is too large for me to use! "
                + "Please use something at or under 40 characters."
            )

        await ctx.defer()

        possible_bullet = await models.TruthBullet.get_or_none(
            channel_id=channel.id, name=name
        )
        if possible_bullet is None:
            raise naff.errors.BadArgument(f"Truth Bullet `{name}` does not exist!")

        if len(possible_bullet.aliases) >= 5:
            raise utils.CustomCheckFailure(
                "I cannot add more aliases to this Truth Bullet!"
            )

        if alias in possible_bullet.aliases:
            raise naff.errors.BadArgument(
                f"Alias `{alias}` already exists for this Truth Bullet!"
            )

        possible_bullet.aliases.add(alias)
        await possible_bullet.save()

        await ctx.send(f"Alias `{alias}` added to Truth Bullet!")

    @add_alias.autocomplete("name")
    async def _add_alias_autocomplete(self, ctx: naff.AutocompleteContext, **kwargs):
        return await fuzzy.autocomplete_bullets(ctx, **kwargs)

    @utils.manage_guild_slash_cmd(
        "remove-alias", "Removes an alias from the Truth Bullet specified."
    )
    @naff.slash_option(
        "channel",
        "The channel the Truth Bullet is in.",
        naff.OptionTypes.CHANNEL,
        required=True,
        channel_types=[
            naff.ChannelTypes.GUILD_TEXT,
            naff.ChannelTypes.GUILD_PUBLIC_THREAD,
        ],
    )
    @naff.slash_option(
        "name",
        "The name of the Truth Bullet to remove an alias from.",
        naff.OptionTypes.STRING,
        required=True,
        autocomplete=True,
    )
    @naff.slash_option(
        "alias",
        "The alias to remove.",
        naff.OptionTypes.STRING,
        required=True,
        autocomplete=True,
    )
    async def remove_alias(
        self,
        ctx: naff.InteractionContext,
        channel: naff.GuildText,
        name: str,
        alias: str,
    ):
        await ctx.defer()

        possible_bullet = await models.TruthBullet.get_or_none(
            channel_id=channel.id, name=name
        )
        if possible_bullet is None:
            raise naff.errors.BadArgument(f"Truth Bullet `{name}` does not exist!")

        try:
            possible_bullet.aliases.remove(alias)
        except KeyError:
            raise naff.errors.BadArgument(
                f"Alias `{alias}` does not exists for this Truth Bullet!"
            )

        await possible_bullet.save()

        await ctx.send(f"Alias `{alias}` removed from Truth Bullet!")

    @remove_alias.autocomplete("name")
    async def _remove_alias_name_autocomplete(
        self, ctx: naff.AutocompleteContext, **kwargs
    ):
        return await fuzzy.autocomplete_bullets(ctx, **kwargs)

    @add_alias.autocomplete("alias")
    async def _remove_alias_alias_autocomplete(
        self, ctx: naff.AutocompleteContext, **kwargs
    ):
        return await fuzzy.autocomplete_aliases(ctx, **kwargs)


def setup(bot):
    importlib.reload(utils)
    importlib.reload(fuzzy)
    BulletCMDs(bot)
