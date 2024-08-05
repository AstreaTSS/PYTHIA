"""
Copyright 2021-2024 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import typing

import interactions as ipy
from interactions.ext import hybrid_commands as hybrid
from interactions.ext import prefixed_commands as prefixed
from interactions.ext.hybrid_commands.hybrid_slash import (
    HybridSlashCommand,
    _values_wrapper,
    base_subcommand_generator,
    slash_to_prefixed,
)


class PatchedHybridManager(hybrid.HybridManager):

    def __init__(
        self,
        client: ipy.Client,
        *,
        hybrid_context: type[ipy.BaseContext] = hybrid.HybridContext,
        use_slash_command_msg: bool = False,
    ) -> None:
        if not hasattr(client, "prefixed") or not isinstance(
            client.prefixed, prefixed.PrefixedManager
        ):
            raise TypeError("Prefixed commands are not set up for this bot.")

        self.hybrid_context = hybrid_context
        self.use_slash_command_msg = use_slash_command_msg

        self.client = typing.cast(prefixed.PrefixedInjectedClient, client)
        self.ext_command_list: dict[str, list[str]] = {}

        self.client.add_listener(self.handle_ext_unload.copy_with_binding(self))

        self.client._add_command_hook.append(self._add_hybrid_command)

        self.client.hybrid = self

    def _add_hybrid_command(self, callback: typing.Callable) -> None:
        # sourcery skip: use-assigned-variable
        if not isinstance(callback, HybridSlashCommand):
            return

        cmd = callback

        if not cmd.callback or cmd._dummy_base:
            if cmd.group_name:
                if not (
                    group := self.client.prefixed.get_command(
                        f"{cmd.name} {cmd.group_name}"
                    )
                ):
                    group = base_subcommand_generator(
                        str(cmd.group_name),
                        list(_values_wrapper(cmd.group_name.to_locale_dict()))
                        + cmd.aliases,
                        str(cmd.group_name),
                        group=True,
                    )
                    self.client.prefixed.commands[str(cmd.name)].add_command(group)
            elif not (base := self.client.prefixed.commands.get(str(cmd.name))):
                base = base_subcommand_generator(
                    str(cmd.name),
                    list(_values_wrapper(cmd.name.to_locale_dict())) + cmd.aliases,
                    str(cmd.name),
                    group=False,
                )
                self.client.prefixed.add_command(base)

            return

        prefixed_transform = slash_to_prefixed(cmd)

        if cmd.is_subcommand:
            base = None
            if not (base := self.client.prefixed.commands.get(str(cmd.name))):
                base = base_subcommand_generator(
                    str(cmd.name),
                    list(_values_wrapper(cmd.name.to_locale_dict())),
                    str(cmd.name),
                    group=False,
                )
                self.client.prefixed.add_command(base)

            if cmd.group_name:  # group command
                group = None
                if not (group := base.subcommands.get(str(cmd.group_name))):
                    group = base_subcommand_generator(
                        str(cmd.group_name),
                        list(_values_wrapper(cmd.group_name.to_locale_dict())),
                        str(cmd.group_name),
                        group=True,
                    )
                    base.add_command(group)
                base = group

            # since this is added *after* the base command has been added to the bot, we need to run
            # this function ourselves
            prefixed_transform._parse_parameters()
            base.add_command(prefixed_transform)
        else:
            self.client.prefixed.add_command(prefixed_transform)

        if cmd.extension:
            self.ext_command_list.setdefault(cmd.extension.extension_name, []).append(
                cmd.resolved_name
            )
