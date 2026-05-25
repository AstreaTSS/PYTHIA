"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

import discord
import ragwort

__all__ = ("bullet_manage",)

bullet_manage = ragwort.SlashCommandGroup(
    name="bullet-manage",
    description="Handles management of Truth Bullets.",
    default_member_permissions=discord.Permissions(manage_guild=True),
    contexts={
        discord.InteractionContextType.guild,
    },
)
