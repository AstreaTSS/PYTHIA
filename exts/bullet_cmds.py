"""
Copyright 2022-2024 AstreaTSS.
This file is part of Ultimate Investigator.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import collections
import importlib

import interactions as ipy
import tansy
from tortoise.expressions import Q

import common.fuzzy as fuzzy
import common.help_tools as help_tools
import common.models as models
import common.utils as utils


def name_shorten(name: str, shorten_amount: int = 16) -> str:
    return f"{name[:shorten_amount].strip()}..." if len(name) > shorten_amount else name


class BulletCMDs(utils.Extension):
    """Commands for using and modifying Truth Bullets."""

    def __init__(self, bot: utils.UIBase) -> None:
        self.name = "Bullet"
        self.bot: utils.UIBase = bot

    @utils.manage_guild_slash_cmd(
        name="add-bullets",
        description="Open a prompt to add Truth Bullets to a specified channel.",
    )
    async def add_bullets(
        self,
        ctx: utils.UISlashContext,
        channel: ipy.GuildText | ipy.GuildPublicThread = tansy.Option(
            "The channel for the Truth Bullets to be added.",
            converter=utils.ValidChannelConverter,
        ),
    ) -> None:
        button = ipy.Button(
            style=ipy.ButtonStyle.GREEN,
            label=f"Add Truth Bullets for #{channel.name}",
            custom_id=f"ui-button:add_bullets-{channel.id}",
        )

        embeds: list[ipy.Embed] = []

        if not await models.TruthBullet.filter(
            guild_id=ctx.guild_id, found=False
        ).exists():
            embeds.append(
                ipy.Embed(
                    "Warning",
                    "This server has Truth Bullets that all have been found, likely"
                    " from a previous investigation. If you want to start fresh with"
                    " completely new Truth Bullets, you can clear the current ones"
                    f" with {self.bot.mention_command('clear-bullets')}.",
                    color=ipy.RoleColors.YELLOW,
                )
            )

        embeds.append(utils.make_embed("Add Truth Bullets via the button below!"))

        await ctx.send(
            embeds=embeds,
            components=button,
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

            modal = ipy.Modal(
                ipy.ShortText(
                    label="What's the name of the Truth Bullet?",
                    custom_id="truth_bullet_name",
                    max_length=60,
                ),
                ipy.ParagraphText(
                    label="What's the description of the Truth Bullet?",
                    custom_id="truth_bullet_desc",
                    max_length=3900,
                ),
                title=f"Add Truth Bullets for #{name_shorten(channel.name)}",
                custom_id=f"ui-modal:add_bullets-{channel.id}",
            )
            await ctx.send_modal(modal)

    @ipy.listen("modal_completion")
    async def on_modal_add_bullet(self, event: ipy.events.ModalCompletion) -> None:
        ctx = event.ctx

        if ctx.custom_id.startswith("ui-modal:add_bullets-"):
            channel_id = int(ctx.custom_id.removeprefix("ui-modal:add_bullets-"))

            if await models.TruthBullet.filter(
                Q(channel_id=channel_id)
                & Q(
                    Q(name__iexact=ctx.responses["truth_bullet_name"])
                    | Q(aliases__icontains=[ctx.responses["truth_bullet_name"]])
                )
            ).exists():
                await ctx.send(
                    embed=utils.error_embed_generate(
                        f"A Truth Bullet in <#{channel_id}> is either already called"
                        f" `{ctx.responses['truth_bullet_name']}` or has an alias named"
                        " that!"
                    )
                )
                return

            await models.TruthBullet.create(
                name=ctx.responses["truth_bullet_name"],
                aliases=set(),
                description=ctx.responses["truth_bullet_desc"],
                channel_id=channel_id,
                guild_id=ctx.guild.id,
                found=False,
                finder=None,
            )

            await ctx.send(
                embed=utils.make_embed(
                    f"Added Truth Bullet `{ctx.responses['truth_bullet_name']}` to"
                    f" <#{channel_id}>!"
                ),
            )

    @utils.manage_guild_slash_cmd(
        "remove-bullet",
        description="Removes a Truth Bullet from the list of Truth Bullets.",
    )
    async def remove_bullet(
        self,
        ctx: utils.UISlashContext,
        channel: ipy.GuildText | ipy.GuildPublicThread = tansy.Option(
            "The channel for the Truth Bullet to be removed."
        ),
        name: str = tansy.Option(
            "The name of the Truth Bullet to be removed.", autocomplete=True
        ),
    ) -> None:
        num_deleted = await models.TruthBullet.filter(
            channel_id=channel.id, name__iexact=name
        ).delete()

        if num_deleted > 0:
            await ctx.send(embed=utils.make_embed(f"`{name}` deleted!"))
        else:
            raise ipy.errors.BadArgument(f"Truth Bullet `{name}` does not exists!")

    @utils.manage_guild_slash_cmd(
        "clear-bullets",
        description=(
            "Removes all Truth Bullets from the list of Truth Bullets. This action is"
            " irreversible."
        ),
    )
    async def clear_bullets(self, ctx: utils.UISlashContext) -> None:
        num_deleted = await models.TruthBullet.filter(guild_id=ctx.guild.id).delete()

        # just to give a more clear indication to users
        # technically everything's fine without this
        if num_deleted > 0:
            await ctx.send(
                embed=utils.make_embed("Cleared all Truth Bullets for this server!")
            )
        else:
            raise utils.CustomCheckFailure(
                "There's no Truth Bullets to delete for this server!"
            )

    @utils.manage_guild_slash_cmd(
        "list-bullets", "Lists all Truth Bullets in the server this is run in."
    )
    async def list_bullets(self, ctx: utils.UIInteractionContext) -> None:
        guild_bullets = await models.TruthBullet.filter(guild_id=ctx.guild.id)
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
            for bullet in bullet_dict[channel_id]:
                str_builder.append(
                    f"- `{bullet.name}`{' (found)' if bullet.found else ''}"
                )

            str_builder.append("")

        pag = help_tools.HelpPaginator.create_from_list(
            ctx.bot, list(str_builder), timeout=300
        )
        if len(pag.pages) == 1:
            embed = pag.pages[0].to_embed()  # type: ignore
            embed.timestamp = ipy.Timestamp.utcnow()
            embed.color = ctx.bot.color
            await ctx.send(embeds=embed)
            return

        pag.show_callback_button = False
        pag.show_select_menu = False
        pag.default_color = ctx.bot.color
        await pag.send(ctx)

    @utils.manage_guild_slash_cmd(
        "bullet-info", "Lists all information about a Truth Bullet."
    )
    async def bullet_info(
        self,
        ctx: utils.UISlashContext,
        channel: ipy.GuildText | ipy.GuildPublicThread = tansy.Option(
            "The channel the Truth Bullet is in."
        ),
        name: str = tansy.Option("The name of the Truth Bullet.", autocomplete=True),
    ) -> None:
        possible_bullet = await models.TruthBullet.get_or_none(
            channel_id=channel.id, name__iexact=name
        )

        if not possible_bullet:
            raise ipy.errors.BadArgument(f"Truth Bullet `{name}` does not exist!")

        bullet_info = possible_bullet.bullet_info()
        embed = ipy.Embed(
            title=f"Information about {name}",
            description=bullet_info,
            color=ctx.bot.color,
            timestamp=ipy.Timestamp.utcnow(),
        )

        await ctx.send(embeds=embed, allowed_mentions=utils.deny_mentions(ctx.author))

    @utils.manage_guild_slash_cmd(
        "edit-bullet", "Sends a prompt to edit a Truth Bullet."
    )
    @ipy.auto_defer(enabled=False)
    async def edit_bullet(
        self,
        ctx: utils.UISlashContext,
        channel: ipy.GuildText | ipy.GuildPublicThread = tansy.Option(
            "The channel the Truth Bullet is in."
        ),
        name: str = tansy.Option(
            "The name of the Truth Bullet to edit.", autocomplete=True
        ),
    ) -> None:
        possible_bullet = await models.TruthBullet.get_or_none(
            channel_id=channel.id, name__iexact=name
        )
        if not possible_bullet:
            raise ipy.errors.BadArgument(f"Truth Bullet `{name}` does not exist!")

        modal = ipy.Modal(
            ipy.ParagraphText(
                label="New description",
                custom_id="description",
                value=possible_bullet.description,
                max_length=3900,
            ),
            title=(
                f"Edit {name_shorten(possible_bullet.name, 10)} for"
                f" #{name_shorten(channel.name, 14)}"
            ),
            custom_id=f"ui:edit-bullet-{channel.id}|{name}",
        )
        await ctx.send_modal(modal)
        await ctx.send(embed=utils.make_embed("Done!"))

    @ipy.listen("modal_completion")
    async def on_modal_edit_bullet(self, event: ipy.events.ModalCompletion) -> None:
        ctx = event.ctx

        if ctx.custom_id.startswith("ui:edit-bullet-"):
            channel_id, name = ctx.custom_id.removeprefix("ui:edit-bullet-").split(
                "|", maxsplit=1
            )
            channel_id = int(channel_id)

            possible_bullet = await models.TruthBullet.get_or_none(
                channel_id=channel_id,
                name__iexact=name,
            )
            if possible_bullet is None:
                await ctx.send(
                    embed=utils.error_embed_generate(
                        f"Truth Bullet `{name}` no longer exists!"
                    )
                )
                return

            possible_bullet.description = ctx.responses["description"]
            await possible_bullet.save()

            await ctx.send(
                embed=utils.make_embed(
                    f"Edited Truth Bullet `{ctx.responses['description']}` in"
                    f" <#{channel_id}>!"
                )
            )

    @utils.manage_guild_slash_cmd("unfind-bullet", "Un-finds a Truth Bullet.")
    async def unfind_bullet(
        self,
        ctx: utils.UISlashContext,
        channel: ipy.GuildText | ipy.GuildPublicThread = tansy.Option(
            "The channel the Truth Bullet is in."
        ),
        name: str = tansy.Option(
            "The name of the Truth Bullet to unfind.", autocomplete=True
        ),
    ) -> None:
        possible_bullet = await models.TruthBullet.get_or_none(
            channel_id=channel.id,
            name__iexact=name,
        )

        if not possible_bullet:
            raise ipy.errors.BadArgument(f"Truth Bullet `{name}` does not exist!")
        if not possible_bullet.found:
            raise ipy.errors.BadArgument(f"Truth Bullet `{name}` has not been found!")

        possible_bullet.found = False
        possible_bullet.finder = None
        await possible_bullet.save()

        await ctx.send(embed=utils.make_embed("Truth Bullet un-found!"))

    @utils.manage_guild_slash_cmd(
        "override-bullet",
        "Overrides who found a Truth Bullet with the person specified.",
    )
    async def override_bullet(
        self,
        ctx: utils.UISlashContext,
        channel: ipy.GuildText | ipy.GuildPublicThread = tansy.Option(
            "The channel the Truth Bullet is in."
        ),
        name: str = tansy.Option(
            "The name of the Truth Bullet to unfind.", autocomplete=True
        ),
        user: ipy.Member = tansy.Option("The user who will find the Truth Bullet."),
    ) -> None:
        possible_bullet = await models.TruthBullet.get_or_none(
            channel_id=channel.id,
            name__iexact=name,
        )
        if not possible_bullet:
            raise ipy.errors.BadArgument(f"Truth Bullet `{name}` does not exist!")

        possible_bullet.found = True
        possible_bullet.finder = user.id
        await possible_bullet.save()

        await ctx.send(embed=utils.make_embed("Truth Bullet overrided and found!"))

    @utils.manage_guild_slash_cmd(
        "add-alias", "Adds an alias to the Truth Bullet specified."
    )
    async def add_alias(
        self,
        ctx: utils.UISlashContext,
        channel: ipy.GuildText | ipy.GuildPublicThread = tansy.Option(
            "The channel the Truth Bullet is in."
        ),
        name: str = tansy.Option(
            "The name of the Truth Bullet to add an alias to.", autocomplete=True
        ),
        alias: str = tansy.Option(
            "The alias to add. Cannot be over 40 characters.", max_length=40
        ),
    ) -> None:
        if len(alias) > 40:
            raise ipy.errors.BadArgument(
                "The name is too large for me to use! "
                + "Please use something at or under 40 characters."
            )

        if await models.TruthBullet.exists(channel_id=channel.id, name__iexact=alias):
            raise ipy.errors.BadArgument(
                f"Alias `{alias}` is used as a name for another Truth Bullet for this"
                " channel!"
            )

        possible_bullet = await models.TruthBullet.get_or_none(
            channel_id=channel.id, name__iexact=name
        )
        if not possible_bullet:
            raise ipy.errors.BadArgument(f"Truth Bullet `{name}` does not exist!")

        if len(possible_bullet.aliases) >= 5:
            raise utils.CustomCheckFailure(
                "I cannot add more aliases to this Truth Bullet!"
            )

        if alias in possible_bullet.aliases:
            raise ipy.errors.BadArgument(
                f"Alias `{alias}` already exists for this Truth Bullet!"
            )

        possible_bullet.aliases.add(alias)
        await possible_bullet.save()

        await ctx.send(
            embed=utils.make_embed(f"Alias `{alias}` added to Truth Bullet!")
        )

    @utils.manage_guild_slash_cmd(
        "remove-alias", "Removes an alias from the Truth Bullet specified."
    )
    async def remove_alias(
        self,
        ctx: utils.UISlashContext,
        channel: ipy.GuildText | ipy.GuildPublicThread = tansy.Option(
            "The channel the Truth Bullet is in."
        ),
        name: str = tansy.Option(
            "The name of the Truth Bullet to remove an alias to.", autocomplete=True
        ),
        alias: str = tansy.Option("The alias to remove.", autocomplete=True),
    ) -> None:
        possible_bullet = await models.TruthBullet.get_or_none(
            channel_id=channel.id,
            name__iexact=name,
        )
        if not possible_bullet:
            raise ipy.errors.BadArgument(f"Truth Bullet `{name}` does not exist!")

        try:
            possible_bullet.aliases.remove(alias)
        except KeyError:
            raise ipy.errors.BadArgument(
                f"Alias `{alias}` does not exists for this Truth Bullet!"
            ) from None

        await possible_bullet.save()

        await ctx.send(
            embed=utils.make_embed(f"Alias `{alias}` removed from Truth Bullet!")
        )

    @remove_bullet.autocomplete("name")
    @bullet_info.autocomplete("name")
    @edit_bullet.autocomplete("name")
    @unfind_bullet.autocomplete("name")
    @override_bullet.autocomplete("name")
    @add_alias.autocomplete("name")
    @remove_alias.autocomplete("name")
    async def _bullet_name_autocomplete(self, ctx: ipy.AutocompleteContext) -> None:
        return await fuzzy.autocomplete_bullets(ctx, **ctx.kwargs)

    @remove_alias.autocomplete("alias")
    async def _remove_alias_alias_autocomplete(
        self,
        ctx: ipy.AutocompleteContext,
    ) -> None:
        return await fuzzy.autocomplete_aliases(ctx, **ctx.kwargs)


def setup(bot: utils.UIBase) -> None:
    importlib.reload(utils)
    importlib.reload(fuzzy)
    BulletCMDs(bot)
