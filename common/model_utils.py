"""
Copyright 2021-2025 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import asyncio
import contextlib
import typing
import uuid
from collections import Counter
from copy import copy

import attrs
import interactions as ipy
from interactions.ext import paginators

import common.models as models
import common.text_utils as text_utils
import common.utils as utils


def gacha_profile_cozy(
    player: models.GachaPlayer,
    user_display_name: str,
    names: "models.Names",
    *,
    show_rarity: bool,
) -> list[ipy.ContainerComponent]:
    components: list[ipy.ContainerComponent] = []

    curr_component = ipy.ContainerComponent(
        ipy.TextDisplayComponent(
            f"# f{user_display_name}'s Gacha Profile\nBalance:"
            f" {player.currency_amount} {names.currency_name(player.currency_amount)}"
        ),
        ipy.SeparatorComponent(divider=True, spacing=ipy.SeparatorSpacingSize.SMALL),
    )

    if not (
        player.items._fetched
        and player.items
        and all(isinstance(entry.item, models.GachaItem) for entry in player.items)
    ):
        curr_component.components.append(ipy.TextDisplayComponent("*No items.*"))
        return [curr_component]

    counter: Counter[models.GachaHash] = Counter()
    for entry in player.items:
        counter[models.GachaHash(entry.item)] += 1

    counter_data = sorted(
        ((name, count) for name, count in counter.items()),
        key=lambda x: x[0].item.name.lower(),
    )

    chunks = [counter_data[x : x + 10] for x in range(0, len(counter_data), 10)]

    for chunk in chunks:
        for item_tuple in chunk:
            entry, count = item_tuple
            curr_component.components.extend(
                (
                    ipy.SectionComponent(
                        components=[
                            ipy.TextDisplayComponent(
                                f"**{entry.item.name}**{f' (x{count})' if count > 1 else ''}\n"
                                f"{names.rarity_name(entry.item.rarity)} ● "
                                if show_rarity
                                else (
                                    f"{text_utils.short_desc(entry.item.description, 80)}"
                                )
                            )
                        ],
                        accessory=ipy.Button(
                            style=ipy.ButtonStyle.SECONDARY,
                            label="View",
                            custom_id=f"gacha_view_item_{entry.item.id}",
                        ),
                    ),
                    ipy.SeparatorComponent(
                        divider=True, spacing=ipy.SeparatorSpacingSize.SMALL
                    ),
                )
            )

        components.append(curr_component)
        curr_component = ipy.ContainerComponent(
            ipy.TextDisplayComponent(f"# f{user_display_name}'s Gacha Profile"),
            ipy.SeparatorComponent(
                divider=True, spacing=ipy.SeparatorSpacingSize.SMALL
            ),
        )

    return components


def gacha_profile_compact(
    player: models.GachaPlayer, user_display_name: str, names: "models.Names"
) -> list[ipy.Embed]:
    str_builder = [
        (
            "Balance:"
            f" {player.currency_amount} {names.currency_name(player.currency_amount)}"
        ),
        "\n**Items:**",
    ]

    if (
        player.items._fetched
        and player.items
        and all(isinstance(entry.item, models.GachaItem) for entry in player.items)
    ):
        counter: Counter[models.GachaHash] = Counter()
        for item in player.items:
            counter[models.GachaHash(item.item)] += 1

        counter_data = sorted(
            ((name, count) for name, count in counter.items()),
            key=lambda x: x[0].item.name.lower(),
        )

        str_builder.extend(
            f"**{entry.item.name}**{f' (x{count})' if count > 1 else ''} -"
            f" {text_utils.short_desc(entry.item.description)}"
            for entry, count in counter_data
        )
    else:
        str_builder.append("*No items.*")

    if len(str_builder) <= 30:
        return [
            ipy.Embed(
                title=f"{user_display_name}'s Gacha Profile",
                description="\n".join(str_builder),
                color=utils.BOT_COLOR,
                timestamp=ipy.Timestamp.utcnow(),
            )
        ]

    chunks = [str_builder[x : x + 30] for x in range(0, len(str_builder), 30)]
    return [
        ipy.Embed(
            title=f"{user_display_name}'s Gacha Profile",
            description="\n".join(chunk),
            color=utils.BOT_COLOR,
            timestamp=ipy.Timestamp.utcnow(),
        )
        for chunk in chunks
    ]


@ipy.utils.define(kw_only=False)
class Componentv2Timeout(paginators.Timeout):
    if typing.TYPE_CHECKING:
        paginator: "Componentv2Paginator"

    async def __call__(self) -> None:
        while self.run:
            try:
                await asyncio.wait_for(
                    self.ping.wait(), timeout=self.paginator.timeout_interval
                )
            except asyncio.TimeoutError:
                if self.paginator.message:
                    with contextlib.suppress(ipy.errors.HTTPException):
                        await self.paginator.message.edit(
                            components=[self.paginator.to_dict(disable=True)],
                            context=self.paginator.context,
                        )
                return
            else:
                self.ping.clear()


@ipy.utils.define(kw_only=False, auto_detect=True)
class Componentv2Paginator:
    client: "utils.THIABase" = attrs.field(
        repr=False,
    )
    """The client to hook listeners into"""

    pages: list[ipy.ContainerComponent] = attrs.field(repr=False, kw_only=True)
    """The entries for the paginator"""
    page_index: int = attrs.field(repr=False, kw_only=True, default=0)
    """The index of the current page being displayed"""
    timeout_interval: int = attrs.field(repr=False, default=120, kw_only=True)
    """How long until this paginator disables itself"""

    context: ipy.InteractionContext | None = attrs.field(
        default=None, init=False, repr=False
    )

    _uuid: str = attrs.field(repr=False, init=False, factory=lambda: str(uuid.uuid4()))
    _message: ipy.Message = attrs.field(repr=False, init=False, default=ipy.MISSING)
    _timeout_task: Componentv2Timeout = attrs.field(
        repr=False, init=False, default=ipy.MISSING
    )
    _author_id: ipy.Snowflake_Type = attrs.field(
        repr=False, init=False, default=ipy.MISSING
    )

    def __attrs_post_init__(self) -> None:
        self.bot.add_component_callback(
            ipy.ComponentCommand(
                name=f"Paginator:{self._uuid}",
                callback=self._on_button,
                listeners=[
                    f"{self._uuid}|select",
                    f"{self._uuid}|first",
                    f"{self._uuid}|back",
                    f"{self._uuid}|next",
                    f"{self._uuid}|last",
                ],
            )
        )

    @property
    def bot(self) -> "utils.THIABase":
        return self.client

    @property
    def message(self) -> ipy.Message:
        """The message this paginator is currently attached to"""
        return self._message

    @property
    def author_id(self) -> ipy.Snowflake_Type:
        """The ID of the author of the message this paginator is currently attached to"""
        return self._author_id

    def create_components(self, disable: bool = False) -> list[ipy.ActionRow]:
        """
        Create the components for the paginator message.

        Args:
            disable: Should all the components be disabled?

        Returns:
            A list of ActionRows

        """
        lower_index = max(0, min(len(self.pages) - 25, self.page_index - 12))

        output: list[ipy.Button | ipy.StringSelectMenu] = [
            ipy.StringSelectMenu(
                *(
                    ipy.StringSelectOption(
                        label=f"Page {i+1}/{len(self.pages)}", value=str(i)
                    )
                    for i in range(lower_index, lower_index + 25)
                ),
                custom_id=f"{self._uuid}|select",
                placeholder=f"Page {self.page_index+1}/{len(self.pages)}",
                max_values=1,
                disabled=disable,
            ),
            ipy.Button(
                style=ipy.ButtonStyle.BLURPLE,
                emoji="⏮️",
                custom_id=f"{self._uuid}|first",
                disabled=disable or self.page_index == 0,
            ),
            ipy.Button(
                style=ipy.ButtonStyle.BLURPLE,
                emoji="⬅️",
                custom_id=f"{self._uuid}|back",
                disabled=disable or self.page_index == 0,
            ),
            ipy.Button(
                style=ipy.ButtonStyle.BLURPLE,
                emoji="➡️",
                custom_id=f"{self._uuid}|next",
                disabled=disable or self.page_index >= len(self.pages) - 1,
            ),
            ipy.Button(
                style=ipy.ButtonStyle.BLURPLE,
                emoji="⏭️",
                custom_id=f"{self._uuid}|last",
                disabled=disable or self.page_index >= len(self.pages) - 1,
            ),
        ]
        return ipy.spread_to_rows(*output)

    def to_dict(self, *, disable: bool = False) -> dict:
        """Convert this paginator into a dictionary for sending."""
        page = copy(self.pages[self.page_index])
        page.components = copy(page.components)
        page.components.extend(self.create_components(disable=disable))
        return {"components": [page.to_dict()]}

    async def send(self, ctx: ipy.BaseContext, **kwargs: typing.Any) -> ipy.Message:
        """
        Send this paginator.

        Args:
            ctx: The context to send this paginator with
            **kwargs: Additional options to pass to `send`.

        Returns:
            The resulting message

        """
        if isinstance(ctx, ipy.InteractionContext):
            self.context = ctx

        self._message = await ctx.send(**self.to_dict(), **kwargs)
        self._author_id = ctx.author.id

        if self.timeout_interval > 1:
            self._timeout_task = Componentv2Timeout(self)
            self.client.create_task(self._timeout_task())

        return self._message

    async def _on_button(
        self, ctx: ipy.ComponentContext, *_: typing.Any, **__: typing.Any
    ) -> typing.Optional[ipy.Message]:

        if ctx.author.id != self.author_id:
            return await ctx.send(
                "You are not allowed to use this paginator.", ephemeral=True
            )

        if self._timeout_task:
            self._timeout_task.ping.set()
        match ctx.custom_id.split("|")[1]:
            case "first":
                self.page_index = 0
            case "last":
                self.page_index = len(self.pages) - 1
            case "next":
                if (self.page_index + 1) < len(self.pages):
                    self.page_index += 1
            case "back":
                if self.page_index >= 1:
                    self.page_index -= 1
            case "select":
                self.page_index = int(ctx.values[0])

        await ctx.edit_origin(**self.to_dict())
        return None
