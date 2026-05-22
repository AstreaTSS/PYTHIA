"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import discord
import typing_extensions as typing

import common.utils as utils


class ContainerPaginator(discord.ui.DesignerView):
    def __init__(
        self,
        *pages: list[discord.ui.ViewItem],
        title: str,
        author_id: int,
        timeout: float = 120,
    ) -> None:
        super().__init__(timeout=timeout, disable_on_timeout=True)
        self.pages = pages
        self.title = title
        self.author_id = author_id
        self.page_index = 0

    @property
    def last_page_index(self) -> int:
        return len(self.pages) - 1

    def update_items(self, disable: bool = False) -> None:
        lower_index = max(0, min((self.last_page_index + 1) - 25, self.page_index - 12))

        container = discord.ui.Container(
            discord.ui.TextDisplay(f"# {self.title}"),
            color=utils.BOT_COLOR,
        )
        for entry in self.pages[self.page_index]:
            container.add_item(entry)

        if not disable:
            container.add_separator(divider=True)
            container.add_row(
                discord.ui.Button(
                    style=discord.ButtonStyle.blurple,
                    emoji="⏮️",
                    custom_id=f"{self.id}|first",
                    disabled=self.page_index == 0,
                ),
                discord.ui.Button(
                    style=discord.ButtonStyle.blurple,
                    emoji="⬅️",
                    custom_id=f"{self.id}|back",
                    disabled=self.page_index == 0,
                ),
                discord.ui.Button(
                    style=discord.ButtonStyle.blurple,
                    emoji="➡️",
                    custom_id=f"{self.id}|next",
                    disabled=self.page_index >= self.last_page_index,
                ),
                discord.ui.Button(
                    style=discord.ButtonStyle.blurple,
                    emoji="⏭️",
                    custom_id=f"{self.id}|last",
                    disabled=self.page_index >= self.last_page_index,
                ),
            )
            container.add_row(
                discord.ui.Select(
                    discord.ComponentType.string_select,
                    options=[
                        discord.SelectOption(
                            label=f"Page {i+1}/{self.last_page_index+1}",
                            value=str(i),
                        )
                        for i in range(
                            lower_index,
                            min(self.last_page_index + 1, lower_index + 25),
                        )
                    ],
                    custom_id=f"{self.id}|select",
                    placeholder=f"Page {self.page_index+1}/{self.last_page_index+1}",
                    max_values=1,
                )
            )

        self.clear_items()
        self.add_item(container)

    def disable_all_items(
        self, *, _: list[discord.ui.ViewItem] | None = None
    ) -> typing.Self:
        self.update_items(disable=True)
        return self

    def _dispatch_item(
        self, item: discord.ui.ViewItem, inter: utils.Interaction
    ) -> None:
        if (
            not isinstance(item, (discord.ui.Button, discord.ui.Select))
            or not item.custom_id
        ):
            return

        match item.custom_id.split("|")[1]:
            case "first":
                self.page_index = 0
            case "last":
                self.page_index = self.last_page_index
            case "next":
                if (self.page_index + 1) <= self.last_page_index:
                    self.page_index += 1
            case "back":
                if self.page_index >= 1:
                    self.page_index -= 1
            case "select":
                self.page_index = int(item.values[0])

        self.update_items()
        inter.client.create_task(inter.response.edit_message(view=self))

    async def interaction_check(self, inter: utils.Interaction) -> bool:
        return inter.user.id == self.author_id

    async def on_check_failure(self, inter: utils.Interaction) -> None:
        await inter.respond(
            view=utils.error_view("You are not allowed to use this paginator."),
            ephemeral=True,
        )

    async def respond(
        self, ctx: utils.THIABridgeContext | discord.Interaction, **kwargs: typing.Any
    ) -> None:
        self.update_items()
        await ctx.respond(view=self, **kwargs)
