"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import textwrap
import time

import discord
import typing_extensions as typing

import common.utils as utils


class ContainerPaginator(discord.ui.DesignerView):
    def __init__(
        self,
        *pages: typing.Iterable[discord.ui.ViewItem],
        title: str,
        author_id: int,
        timeout: float = 120,
    ) -> None:
        super().__init__(timeout=timeout, disable_on_timeout=True)
        self.pages = pages
        self.title = title
        self.author_id = author_id
        self.page_index = 0

        if len(self.pages) == 1:
            self.timeout = None
            self.disable_on_timeout = False
            self._store = False

        self.update_items()

    @classmethod
    def create_from_string(
        cls,
        title: str,
        author_id: int,
        content: str,
        prefix: str = "",
        suffix: str = "",
        page_size: int = 3900,
        timeout: float = 120,
    ) -> typing.Self:
        content_pages = textwrap.wrap(
            content,
            width=page_size - (len(prefix) + len(suffix)),
            break_long_words=True,
            break_on_hyphens=False,
            replace_whitespace=False,
        )
        pages: list[list[discord.ui.ViewItem]] = [
            [discord.ui.TextDisplay(f"{prefix}{page}{suffix}")]
            for page in content_pages
        ]
        return cls(
            *pages,
            title=title,
            author_id=author_id,
            timeout=timeout,
        )

    @classmethod
    def create_from_list(
        cls,
        entries: typing.Iterable[str],
        *,
        title: str,
        author_id: int,
        page_size: int = 3900,
        timeout: float = 120,
    ) -> typing.Self:
        pages: list[list[discord.ui.ViewItem]] = []
        page_length = 0
        page = ""
        for entry in entries:
            if len(page) + len(f"\n{entry}") <= page_size:
                page += f"{entry}\n"
            else:
                pages.append([discord.ui.TextDisplay(page)])
                page_length += 1
                page = ""
        if page != "":
            pages.append([discord.ui.TextDisplay(page)])

        return cls(
            *pages,
            title=title,
            author_id=author_id,
            timeout=timeout,
        )

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

        if not disable and len(self.pages) > 1:
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

    async def _scheduled_task(
        self,
        item: discord.ui.ViewItem,
        inter: utils.Interaction,
    ) -> None:
        try:
            if self.timeout:
                self._timeout_expiry = time.monotonic() + self.timeout

            allow = await self.interaction_check(inter)
            if not allow:
                return await self.on_check_failure(inter)

            if (
                not isinstance(item, (discord.ui.Button, discord.ui.Select))
                or not item.custom_id
                or not item.custom_id.startswith(f"{self.id}|")
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
            await inter.response.edit_message(view=self)
        except Exception as e:
            return await self.on_error(e, item, inter)

    async def interaction_check(self, inter: utils.Interaction) -> bool:
        return inter.user.id == self.author_id

    async def on_check_failure(self, inter: utils.Interaction) -> None:
        await inter.respond(
            view=utils.error_view("You are not allowed to use this paginator."),
            ephemeral=True,
        )


class EmbedPaginator(discord.ui.View):
    def __init__(
        self,
        *embeds: discord.Embed,
        author_id: int,
        timeout: float = 120,
    ) -> None:
        super().__init__(timeout=timeout, disable_on_timeout=True)
        self.embeds = embeds
        self.author_id = author_id
        self.page_index = 0

        self.update_items()

    @property
    def last_page_index(self) -> int:
        return len(self.embeds) - 1

    def get_embed(self) -> discord.Embed:
        embed = self.embeds[self.page_index]
        if not (embed.author and embed.author.name):
            embed.set_author(name=f"Page {self.page_index+1}/{len(self.embeds)}")
        return embed

    def update_items(self, disable: bool = False) -> None:
        lower_index = max(0, min((self.last_page_index + 1) - 25, self.page_index - 12))
        self.clear_items()

        if not disable:
            self.add_item(
                discord.ui.ActionRow(
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
            )

            self.add_item(
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
                    row=1,
                )
            )

    def disable_all_items(
        self, *, _: list[discord.ui.ViewItem] | None = None
    ) -> typing.Self:
        self.update_items(disable=True)
        return self

    async def _scheduled_task(
        self,
        item: discord.ui.ViewItem,
        inter: utils.Interaction,
    ) -> None:
        try:
            if self.timeout:
                self._timeout_expiry = time.monotonic() + self.timeout

            allow = await self.interaction_check(inter)
            if not allow:
                return await self.on_check_failure(inter)

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
            await inter.response.edit_message(embed=self.get_embed(), view=self)
        except Exception as e:
            return await self.on_error(e, item, inter)

    async def interaction_check(self, inter: utils.Interaction) -> bool:
        return inter.user.id == self.author_id

    async def on_check_failure(self, inter: utils.Interaction) -> None:
        await inter.respond(
            view=utils.error_view("You are not allowed to use this paginator."),
            ephemeral=True,
        )

    async def respond(
        self, ctx: utils.THIABridgeContext, **kwargs: typing.Any
    ) -> discord.Message:
        self.update_items()
        return await ctx.respond(embed=self.get_embed(), view=self, **kwargs)


class ButtonToModal(discord.ui.DesignerView):
    def __init__(
        self,
        text: str,
        button: discord.ui.Button,
        modal: typing.Callable[[], discord.ui.DesignerModal],
    ) -> None:
        self.button = button
        self.modal = modal
        self.button.callback = self.handle_button

        super().__init__(timeout=None)

        self.add_item(
            discord.ui.Container(
                discord.ui.Section(
                    discord.ui.TextDisplay(text),
                    accessory=self.button,
                ),
                color=utils.BOT_COLOR,
            )
        )

    async def handle_button(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_modal(self.modal())
