"""
Copyright 2021-2025 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import importlib

import interactions as ipy
import tansy
import typing_extensions as typing

import common.fuzzy as fuzzy
import common.help_tools as help_tools
import common.utils as utils


class HelpCMD(utils.Extension):
    """The cog that handles the help command."""

    def __init__(self, bot: utils.THIABase) -> None:
        self.name = "Help Category"
        self.bot: utils.THIABase = bot

    async def extract_commands(
        self, ctx: ipy.AutocompleteContext, argument: typing.Optional[str]
    ) -> tuple[str, ...]:
        cmds = help_tools.get_mini_commands_for_scope(self.bot, int(ctx.guild_id))

        runnable_cmds = [v for v in cmds.values() if await help_tools.can_run(ctx, v)]
        resolved_names = {
            c.resolved_name.lower(): c.resolved_name
            for c in sorted(runnable_cmds, key=lambda c: c.resolved_name)
        }

        if not argument:
            return tuple(resolved_names.values())[:25]

        queried_cmds: list[list[str]] = fuzzy.extract_from_list(
            argument=argument.lower(),
            list_of_items=tuple(resolved_names.keys()),
            processors=[lambda x: x.lower()],
            score_cutoff=0.7,
        )
        return tuple(resolved_names[c[0]] for c in queried_cmds)[:25]

    async def get_multi_command_embeds(
        self,
        ctx: utils.THIASlashContext,
        commands: list[help_tools.MiniCommand],
        name: str,
        description: typing.Optional[str],
    ) -> list[ipy.Embed]:
        embeds: list[ipy.Embed] = []

        commands = [c for c in commands if await help_tools.can_run(ctx, c)]
        if not commands:
            return []

        chunks = [commands[x : x + 9] for x in range(0, len(commands), 9)]
        multiple_embeds = len(chunks) > 1

        for index, chunk in enumerate(chunks):
            embed = ipy.Embed(description=description, color=ctx.bot.color)
            embed.set_footer(text='Use "/help command" for more info on a command.')

            embed.title = f"{name} - Page {index + 1}" if multiple_embeds else name
            for cmd in chunk:
                signature = f"{cmd.resolved_name} {cmd.signature}".strip()
                embed.add_field(
                    name=signature,
                    value=cmd.brief_description,
                    inline=False,
                )

            embeds.append(embed)

        return embeds

    async def get_ext_cmd_embeds(
        self,
        ctx: utils.THIASlashContext,
        cmds: dict[str, help_tools.MiniCommand],
        ext: ipy.Extension,
    ) -> list[ipy.Embed]:
        slash_cmds = [
            c
            for c in cmds.values()
            if c.extension == ext and " " not in c.resolved_name
        ]
        slash_cmds.sort(key=lambda c: c.resolved_name)

        if not slash_cmds:
            return []

        name = f"{ext.name} Commands"
        return await self.get_multi_command_embeds(
            ctx, slash_cmds, name, ext.description
        )

    async def get_all_cmd_embeds(
        self,
        ctx: utils.THIASlashContext,
        cmds: dict[str, help_tools.MiniCommand],
        bot: utils.THIABase,
    ) -> list[ipy.Embed]:
        embeds: list[ipy.Embed] = []

        for ext in bot.ext.values():
            ext_cmd_embeds = await self.get_ext_cmd_embeds(ctx, cmds, ext)
            if ext_cmd_embeds:
                embeds.extend(ext_cmd_embeds)

        return embeds

    async def get_command_embeds(
        self, ctx: utils.THIASlashContext, command: help_tools.MiniCommand
    ) -> list[ipy.Embed]:
        if command.subcommands:
            return await self.get_multi_command_embeds(
                ctx, command.view_subcommands, command.name, command.description
            )

        signature = f"{command.resolved_name} {command.signature}"
        return [
            ipy.Embed(
                title=signature,
                description=command.description,
                color=ctx.bot.color,
            )
        ]

    @tansy.slash_command(
        name="help",
        description="Shows help about the bot or a command.",
        dm_permission=False,
    )
    async def help_cmd(
        self,
        ctx: utils.THIASlashContext,
        query: typing.Optional[str] = tansy.Option(
            "The command to search for.",
            autocomplete=True,
            default=None,
        ),
    ) -> None:
        embeds: list[ipy.Embed] = []

        if not self.bot.slash_perms_cache[int(ctx.guild_id)]:
            await help_tools.process_bulk_slash_perms(self.bot, int(ctx.guild_id))

        cmds = help_tools.get_mini_commands_for_scope(self.bot, int(ctx.guild_id))

        if not query:
            embeds = await self.get_all_cmd_embeds(ctx, cmds, self.bot)
        elif (command := cmds.get(query.lower())) and await help_tools.can_run(
            ctx, command
        ):
            embeds = await self.get_command_embeds(ctx, command)
        else:
            raise ipy.errors.BadArgument(f"No valid command called `{query}` found.")

        if not embeds:
            raise ipy.errors.BadArgument(f"No valid command called `{query}` found.")

        if len(embeds) == 1:
            # pointless to do a paginator here
            await ctx.send(embeds=embeds)
            return

        pag = help_tools.HelpPaginator.create_from_embeds(self.bot, *embeds, timeout=60)
        await pag.send(ctx)

    @help_cmd.autocomplete("query")
    async def query_autocomplete(
        self,
        ctx: ipy.AutocompleteContext,
    ) -> None:
        query = ctx.kwargs.get("query")

        if not self.bot.slash_perms_cache[int(ctx.guild_id)]:
            await help_tools.process_bulk_slash_perms(self.bot, int(ctx.guild_id))

        commands = await self.extract_commands(ctx, query)
        await ctx.send([{"name": c, "value": c} for c in commands])


def setup(bot: utils.THIABase) -> None:
    importlib.reload(utils)
    importlib.reload(help_tools)
    HelpCMD(bot)
