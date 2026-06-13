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
    dependencies = [("models", "0008_itemtoplayer_indexes")]

    initial = False

    operations = [
        RunSQL(
            sql="""
            CREATE TABLE "thiatruthbulletalias" (
                id SERIAL PRIMARY KEY,
                bullet_id INTEGER NOT NULL REFERENCES "thiatruthbullets" (id) ON DELETE CASCADE,
                alias TEXT NOT NULL
            );
            INSERT INTO "thiatruthbulletalias" (bullet_id, alias) SELECT id, unnest(aliases) FROM "thiatruthbullets" WHERE aliases IS NOT NULL;
            ALTER TABLE "thiatruthbullets" DROP COLUMN "aliases";
            CREATE INDEX "thiatruthbulletalias_bullet_id_idx" ON "thiatruthbulletalias" (bullet_id);
            CREATE UNIQUE INDEX "thiatruthbulletalias_bullet_id_alias_idx" ON "thiatruthbulletalias" (bullet_id, alias);
            """.strip(),
            reverse_sql="""
            ALTER TABLE "thiatruthbullets" ADD COLUMN "aliases" VARCHAR(40)[] NULL;
            UPDATE "thiatruthbullets" t SET aliases = a.aliases FROM (
                SELECT bullet_id, array_agg(alias) AS aliases
                FROM "thiatruthbulletalias"
                GROUP BY bullet_id
            ) a WHERE t.id = a.bullet_id;
            DROP TABLE "thiatruthbulletalias";
            """.strip(),
        )
    ]
