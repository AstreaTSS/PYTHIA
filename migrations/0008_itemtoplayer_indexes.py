"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.migrations.operations import RunSQL


class Migration(migrations.Migration):
    dependencies = [("models", "0007_gist_index")]

    initial = False

    operations = [
        RunSQL(
            sql="""
            CREATE INDEX IF NOT EXISTS "thiagachaitemtoplayer_item_id_idx" ON "thiagachaitemtoplayer" ("item_id");
            CREATE INDEX IF NOT EXISTS "thiagachaitemtoplayer_player_id_idx" ON "thiagachaitemtoplayer" ("player_id");
            """.strip(),
            reverse_sql="""
            DROP INDEX IF EXISTS "thiagachaitemtoplayer_item_id_idx";
            DROP INDEX IF EXISTS "thiagachaitemtoplayer_player_id_idx";
            """.strip(),
        )
    ]
