"""
Copyright 2021-2025 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import asyncio
import collections
import contextlib
import typing
import uuid

import attrs
import interactions as ipy
from interactions.ext import paginators

if typing.TYPE_CHECKING:
    import common.utils as utils


@ipy.utils.define(kw_only=False)
class ComponentTimeout(paginators.Timeout):
    if typing.TYPE_CHECKING:
        paginator: "ContainerPaginator"

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
                            components=self.paginator.create_components(disable=True),
                            context=self.paginator.context,
                        )
                return
            else:
                self.ping.clear()


class ContainerComponent(
    ipy.BaseComponent,
    collections.UserList[
        ipy.ActionRow
        | ipy.SectionComponent
        | ipy.TextDisplayComponent
        | ipy.MediaGalleryComponent
        | ipy.FileComponent
        | ipy.SeparatorComponent
    ],
):
    accent_color: int | None = None
    spoiler: bool = False

    def __init__(
        self,
        *components: ipy.ActionRow
        | ipy.SectionComponent
        | ipy.TextDisplayComponent
        | ipy.MediaGalleryComponent
        | ipy.FileComponent
        | ipy.SeparatorComponent,
        accent_color: int | None = None,
        spoiler: bool = False,
    ) -> None:
        self.data = list(components)
        self.accent_color = accent_color
        self.spoiler = spoiler
        self.type = ipy.ComponentType.CONTAINER

    @property
    def components(
        self,
    ) -> list[
        ipy.ActionRow
        | ipy.SectionComponent
        | ipy.TextDisplayComponent
        | ipy.MediaGalleryComponent
        | ipy.FileComponent
        | ipy.SeparatorComponent
    ]:
        return self.data

    @components.setter
    def components(
        self,
        value: list[
            ipy.ActionRow
            | ipy.SectionComponent
            | ipy.TextDisplayComponent
            | ipy.MediaGalleryComponent
            | ipy.FileComponent
            | ipy.SeparatorComponent
        ],
    ) -> None:
        self.data = value

    @typing.overload
    def __getitem__(
        self, i: int
    ) -> (
        ipy.ActionRow
        | ipy.SectionComponent
        | ipy.TextDisplayComponent
        | ipy.MediaGalleryComponent
        | ipy.FileComponent
        | ipy.SeparatorComponent
    ): ...

    @typing.overload
    def __getitem__(self, i: slice) -> typing.Self: ...

    def __getitem__(
        self, i: int | slice
    ) -> (
        typing.Self
        | ipy.ActionRow
        | ipy.SectionComponent
        | ipy.TextDisplayComponent
        | ipy.MediaGalleryComponent
        | ipy.FileComponent
        | ipy.SeparatorComponent
    ):
        if isinstance(i, slice):
            return self.__class__(
                *self.data[i], accent_color=self.accent_color, spoiler=self.spoiler
            )
        return self.data[i]

    def __add__(self, other: typing.Any) -> typing.Self:
        if isinstance(other, ContainerComponent):
            return self.__class__(
                *(self.data + other.data),
                accent_color=self.accent_color,
                spoiler=self.spoiler,
            )
        if isinstance(other, collections.UserList):
            return self.__class__(
                *(self.data + other.data),
                accent_color=self.accent_color,
                spoiler=self.spoiler,
            )
        if isinstance(other, type(self.data)):
            return self.__class__(
                *(self.data + other),
                accent_color=self.accent_color,
                spoiler=self.spoiler,
            )
        return self.__class__(
            *(self.data + list(other)),
            accent_color=self.accent_color,
            spoiler=self.spoiler,
        )

    def __radd__(self, other: typing.Any) -> typing.Self:
        if isinstance(other, ContainerComponent):
            return self.__class__(
                *(self.data + other.data),
                accent_color=other.accent_color,
                spoiler=other.spoiler,
            )
        if isinstance(other, collections.UserList):
            return self.__class__(
                *(other.data + self.data),
                accent_color=self.accent_color,
                spoiler=self.spoiler,
            )
        if isinstance(other, type(self.data)):
            return self.__class__(
                *(other + self.data),
                accent_color=self.accent_color,
                spoiler=self.spoiler,
            )
        return self.__class__(
            *(list(other) + self.data),
            accent_color=self.accent_color,
            spoiler=self.spoiler,
        )

    def __mul__(self, n: int) -> typing.Self:
        return self.__class__(
            *(self.data * n), accent_color=self.accent_color, spoiler=self.spoiler
        )

    __rmul__ = __mul__

    def copy(self) -> typing.Self:
        return self.__class__(
            *self.data, accent_color=self.accent_color, spoiler=self.spoiler
        )

    @classmethod
    def from_dict(cls, data: dict) -> typing.Self:
        return cls(
            *[
                ipy.BaseComponent.from_dict_factory(component)
                for component in data["components"]
            ],
            accent_color=data.get("accent_color"),
            spoiler=data.get("spoiler", False),
        )

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} type={self.type} components={self.components} accent_color={self.accent_color} spoiler={self.spoiler}>"
        )

    def to_dict(self) -> dict:
        return {
            "type": self.type.value,
            "components": [component.to_dict() for component in self.components],
            "accent_color": self.accent_color,
            "spoiler": self.spoiler,
        }


@ipy.utils.define(kw_only=False, auto_detect=True)
class ContainerPaginator:
    client: "utils.THIABase" = attrs.field(
        repr=False,
    )
    """The client to hook listeners into"""

    title: str = attrs.field(kw_only=True)
    """The title of the paginator"""
    pages_data: list[list[ipy.BaseComponent]] = attrs.field(repr=False, kw_only=True)
    """The entries for the paginators"""

    page_index: int = attrs.field(repr=False, kw_only=True, default=0)
    """The index of the current page being displayed"""
    timeout_interval: int = attrs.field(repr=False, default=120, kw_only=True)
    """How long until this paginator disables itself"""

    context: ipy.InteractionContext | None = attrs.field(
        default=None, init=False, repr=False
    )

    _uuid: str = attrs.field(repr=False, init=False, factory=uuid.uuid4)
    _message: ipy.Message = attrs.field(repr=False, init=False, default=ipy.MISSING)
    _timeout_task: ComponentTimeout = attrs.field(
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

    @property
    def last_page_index(self) -> int:
        return len(self.pages_data) - 1

    def create_components(self, disable: bool = False) -> ContainerComponent:
        """
        Create the components for the paginator message.

        Args:
            disable: Should all the components be disabled?

        Returns:
            A ContainerComponent

        """
        lower_index = max(0, min((self.last_page_index + 1) - 25, self.page_index - 12))

        output: ContainerComponent = ContainerComponent(
            ipy.TextDisplayComponent(f"# {self.title}"),
            accent_color=self.bot.color.value,
        )
        output.extend(self.pages_data[self.page_index])

        if not disable:
            output.append(ipy.SeparatorComponent(divider=True))
            output.append(
                ipy.ActionRow(
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
                        disabled=disable or self.page_index >= self.last_page_index,
                    ),
                    ipy.Button(
                        style=ipy.ButtonStyle.BLURPLE,
                        emoji="⏭️",
                        custom_id=f"{self._uuid}|last",
                        disabled=disable or self.page_index >= self.last_page_index,
                    ),
                )
            )
            output.append(
                ipy.ActionRow(
                    ipy.StringSelectMenu(
                        *(
                            ipy.StringSelectOption(
                                label=f"Page {i+1}/{self.last_page_index+1}",
                                value=str(i),
                            )
                            for i in range(
                                lower_index,
                                min(self.last_page_index + 1, lower_index + 25),
                            )
                        ),
                        custom_id=f"{self._uuid}|select",
                        placeholder=(
                            f"Page {self.page_index+1}/{self.last_page_index+1}"
                        ),
                        max_values=1,
                        disabled=disable,
                    )
                )
            )

        return output

    async def to_dict(self) -> dict:
        """Convert this paginator into a dictionary for sending."""
        return {"components": [self.create_components(disable=False).to_dict()]}

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

        self._message = await ctx.send(**await self.to_dict(), **kwargs)
        self._author_id = ctx.author.id

        if self.timeout_interval > 1:
            self._timeout_task = ComponentTimeout(self)
            self.client.create_task(self._timeout_task())

        return self._message

    async def _on_button(
        self, ctx: ipy.ComponentContext, *_: typing.Any, **__: typing.Any
    ) -> ipy.Message | None:
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
                self.page_index = self.last_page_index
            case "next":
                if (self.page_index + 1) <= self.last_page_index:
                    self.page_index += 1
            case "back":
                if self.page_index >= 1:
                    self.page_index -= 1
            case "select":
                self.page_index = int(ctx.values[0])

        await ctx.edit_origin(**await self.to_dict())
        return None
