"""
Copyright 2021-2026 AstreaTSS.
This file is part of PYTHIA.

This Source Code Form is subject to the terms of the Mozilla Public
License, v. 2.0. If a copy of the MPL was not distributed with this
file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""

from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        UPDATE "thiagachaitems" SET "rarity" = '1' WHERE "rarity" = 'COMMON';
        UPDATE "thiagachaitems" SET "rarity" = '2' WHERE "rarity" = 'UNCOMMON';
        UPDATE "thiagachaitems" SET "rarity" = '3' WHERE "rarity" = 'RARE';
        UPDATE "thiagachaitems" SET "rarity" = '4' WHERE "rarity" = 'SUPER_RARE';
        UPDATE "thiagachaitems" SET "rarity" = '5' WHERE "rarity" = 'LEGENDARY';

        ALTER TABLE "thiagachaitems" ALTER COLUMN "rarity" SET DEFAULT 1;
        ALTER TABLE "thiagachaitems" ALTER COLUMN "rarity" TYPE SMALLINT USING "rarity"::SMALLINT;
        COMMENT ON COLUMN "thiagachaitems"."rarity" IS 'COMMON: 1
UNCOMMON: 2
RARE: 3
EPIC: 4
LEGENDARY: 5';
        CREATE TABLE IF NOT EXISTS "thiagachararities" (
    "common_color" VARCHAR(7) NOT NULL DEFAULT '#979797',
    "uncommon_color" VARCHAR(7) NOT NULL DEFAULT '#6aad0f',
    "rare_color" VARCHAR(7) NOT NULL DEFAULT '#109db9',
    "epic_color" VARCHAR(7) NOT NULL DEFAULT '#ab47b9',
    "legendary_color" VARCHAR(7) NOT NULL DEFAULT '#f4d046',
    "common_odds" DECIMAL(5,4) NOT NULL DEFAULT 0.6,
    "uncommon_odds" DECIMAL(5,4) NOT NULL DEFAULT 0.25,
    "rare_odds" DECIMAL(5,4) NOT NULL DEFAULT 0.1,
    "epic_odds" DECIMAL(5,4) NOT NULL DEFAULT 0.04,
    "legendary_odds" DECIMAL(5,4) NOT NULL DEFAULT 0.01,
    "guild_id" BIGINT NOT NULL PRIMARY KEY REFERENCES "thiagachaconfig" ("guild_id") ON DELETE CASCADE
);
        ALTER TABLE "thianames" ADD "gacha_uncommon_name" TEXT NOT NULL DEFAULT 'Uncommon';
        ALTER TABLE "thianames" ADD "gacha_rare_name" TEXT NOT NULL DEFAULT 'Rare';
        ALTER TABLE "thianames" ADD "gacha_legendary_name" TEXT NOT NULL DEFAULT '***__Legendary__***';
        ALTER TABLE "thianames" ADD "gacha_common_name" TEXT NOT NULL DEFAULT 'Common';
        ALTER TABLE "thianames" ADD "gacha_epic_name" TEXT NOT NULL DEFAULT 'Epic';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "thianames" DROP COLUMN "gacha_uncommon_name";
        ALTER TABLE "thianames" DROP COLUMN "gacha_rare_name";
        ALTER TABLE "thianames" DROP COLUMN "gacha_legendary_name";
        ALTER TABLE "thianames" DROP COLUMN "gacha_common_name";
        ALTER TABLE "thianames" DROP COLUMN "gacha_epic_name";
        ALTER TABLE "thiagachaitems" ALTER COLUMN "rarity" TYPE VARCHAR(10) USING "rarity"::VARCHAR(10);
        ALTER TABLE "thiagachaitems" ALTER COLUMN "rarity" SET DEFAULT 'COMMON';

        UPDATE "thiagachaitems" SET "rarity" = 'COMMON' WHERE "rarity" = '1';
        UPDATE "thiagachaitems" SET "rarity" = 'UNCOMMON' WHERE "rarity" = '2';
        UPDATE "thiagachaitems" SET "rarity" = 'RARE' WHERE "rarity" = '3';
        UPDATE "thiagachaitems" SET "rarity" = 'SUPER_RARE' WHERE "rarity" = '4';
        UPDATE "thiagachaitems" SET "rarity" = 'LEGENDARY' WHERE "rarity" = '5';

        COMMENT ON COLUMN "thiagachaitems"."rarity" IS 'COMMON: COMMON
UNCOMMON: UNCOMMON
RARE: RARE
SUPER_RARE: SUPER_RARE
LEGENDARY: LEGENDARY';
        DROP TABLE IF EXISTS "thiagachararities";"""


MODELS_STATE = (
    "eJztXW1v4jgQ/iuI+7K76q0opWW33yhle72j9ETb0522FTKJAV+Dw+Vld9GK/36Ocd4DMU"
    "5CIbEqtcU2M87jlxnPjCc/63NdhZr5cQDm0Kxf1n7WwWJB/rLy+kmtjkmVX8JaknILjDVa"
    "Yc0QwG4pwir8QUl9fSEf56RmClXyEduaRgrA2LQMoFikZAI0E5KixetogqCmUvYut6mNNH"
    "WEVIemjdF/tlNqGbbzBRVOgK1ZPtE1U9Vv4ZSz7rlc1PFI0TV7jqPUVV0hXUJ46tObQgwN"
    "YFGK7vdpF0fWckG7d4Wmt9j6QrtNKhUdO4+FsLUGceo0+vVzs3l21m42zi4+nbfa7fNPjU"
    "+kLe1VvKq9ok9mKgZaWEjHfm8WS2umY481YVJfP4/fpTVX2rHbm9vBo9NAJzCvB8gpWK2S"
    "H3XCwPdHrDmPlOhNPVASGaL8xodvGAgQZBpCi/ag23nodq57Th8M8N2bRaHhDY/bPYaPOv"
    "lFR+6WDBrACkwYQd7BYIvixmHY1fEETevuXHPpsadeOVCqwAKJWJrkwW0NGKMxYQOtEKoe"
    "Qh6s9UfDtma1K6+tD7DbOG0FJDAUWgiP8MfGZcALIvnOlhn92Pubzue5af6nOQWDvzrD7m"
    "+d4bu7zt/vac2S1fTvBzduc3/6D7r9+yu6AHy8F5ptAE0AbVMM7hi/KoHtzTXLAZKBQNgT"
    "FI007H/+ZM0dYqtV7Yv3rQxzfkM/qjQmbELmNiLZ1oUckPoYmtZuA3FFvlHzRmP9ndVKbB"
    "ySuVcJf29zUGzDgFhZ0vmdNgZdHeGMm1GMX5VQZ+t/Z8yzbTeVhnwKlBkgmMznpB98eDtN"
    "xQBPZFY9tG28A95PrHEWxGMMq4e5AQzIhfeQNMyCdYhR9XCGC6Rw4dwjDbPgHGJUPZw1SB"
    "5QBQafkPzw4cNo1Pe+MiKfs2AfZ172AXjZ1J016iNLn0JrRvRkZiUbA+X1OzDUUcyi5tWE"
    "DWkvzgMz+1EHGkiZ1Xnsr6zpScAAC7yivKyvRdlduSyujFZ45qRbW5unrXbr09lFyzOyei"
    "U52VZztaNuNQd+IwdqtNYAtizy2CjwrukAeaFl3J0BY+NozMEPsl3gqeXM5+b5eT7r2l3F"
    "hOD7yIJlVc11XXjrdFZTQSAy0gUDeNpo5AsgIbgRQFoXBpB0zoI4zUQqDGKAvBCQvz/cD7"
    "IKlCdMar+qSLFOahoyrZctKDr8touXqCRx+OmmNTUoFUpg7+LlGimwhy1jySVh/NYnES8f"
    "wYiMCKsJyJqvYXedCQ3n3xcpgt5OBG1z03Gs37f2033RDYim+A+4zNlT50xuDkddJuntLo"
    "CC9swA+er4rn10OU4/wtBW5XATxPMb0OzCAPWIVwnRxNiVI9h03zo4Yl/q0I1j0ri14JxL"
    "HfJbR9UhahpBpCbXyCep+EjFpwDFh07jojUfKZvzlSTBbhUEa4RFldBFc7JD54Cru0WHdl"
    "uXdpUANYCBrGUKoqciwsunLIQnkWA9bM/TtlQmzc6a7QtPkDkfEmRYvXt/d3c/II/zjJ8G"
    "7ofmMx52hj3yrWfc+/O2e1lrPeN+76Y3uO4M/7msndd3lXsPd51+P34IAnPdTrXK/SoEtU"
    "9aFOqDURakSv7mKnkw1AcsWZxgXnJMyPrBuvnljyHUgCv2ssHpnA4e9T/pA27Fk9NWy0aG"
    "11jrD2TMWqt4VfJixuEat+TFjDff6DZ6YpGJHDy271oMPQH7mE9ebLrrugYBzqorjgmZbX"
    "P3/r4fUhavbqPa4NPdVW/47pRqjqQRsgITPG9JAjHBCZZSkoR8b1nESPC4z23l2iBIqJ1L"
    "ShIpSaQkySBJIHbgSDuBuCW7i5IA/fKKklBoihvFr+hm2lH4VAjSGIcSnYhVZzmp9kJDCu"
    "l9mjAVVnAS2JR3duat6Hi+pbKpOSGfWuJWGr4kVFrLAQVC3HAQMb3moxS7Ij4LRq4Qzhmp"
    "YeApk7GKqsAMW24V2B+LuAocmIcy+E36gKUPWEa/7T36zVNJuTxAjWxqr3QFHdCu8NbnWq"
    "nX7tcRFBwYLvUlPJBh9cWpK7EFL1FlOcqdvvi7ZWstdmToqV4N0diXCIeqiOnCY1gDyWJs"
    "LxdVKQ9761xbKVIpZM1CSp6z+bDQ4LizErsuXloweM4woSC/nHSNw0TDUTjMHdCYQ9Mksr"
    "68gNytH3AHSLzUpaXEw0vXmmouC04lHn0zMvVC+iZddCXWN0ujs+SkcEqPsfQYH6hPLhQ1"
    "bVu6aU+J/EsznAn7OyMsyourtAntoqI9LE3yZ6vHk9MsxBScPsKvXGI62D4qppk2qLE66d"
    "SSTq3jc2rxafzSrXWAumfArTUDGEOtQIDDHKqIsXR8HXZaAvqaAfZOBx7JHmwflew0oXrA"
    "SiyTExyEDM8shQhxcrZISw0vvEkGyJc8rx3QEDBztfuFToE+dSEcO4YBllnPf04uOw7gWo"
    "33X19k3oE9XpMXV3Y4d1Op6xSg60hTsQ/vRLdxUdh6tMtrOwtByfOuF1E5lPFVLkc+S2dI"
    "VWGaABM3n/vkqzFTZbqcY0srHwqj4TlSRuNuQmfK9XFSenWPYROUXt03NxttOsKzt6w5On"
    "o+5s6k/TTOpDpzf9s79YoMe93CrZLgr62Po6KjGBL4VEQfw9/IjENT6qde89+Osdgl+GQ2"
    "QhA/zIGmpc9pnvx7IvN2Qy49c6Z/H9HFO/FfZVpEbEgio/LO1b2quk5ohRezwRu+GAzyiM"
    "UvGoHKUGSEU0mjIU5qgTAJ+kkf/wsVS4ZKHEyoBGIRN/sNKuLSXN1pFIO6sEiJXSKRMnmp"
    "pPW1UM3K32WKwTdEv8IAc6hUwu6vCAthbytXWuOQ5zUxmfFvncGg17+ssX+e8dNDb3hZc3"
    "7X4xjzeWTbG/2x7ag3NrAXFgF2gPyRX2Tfu07l3Wbm1amC15+T35Zh6QuvhYxLkQrT4SpM"
    "ImmqDhQ8did7//BxJEPIpGtK0cG9DcRyABQHW4jBkQO3V5kbTnPGnbYsmBgtLnWDyeEO12"
    "tXdq8QhxyWXrmCM5ttFCOKPp8TsmQH09NEeP2Xz23np34isjNGGRUcZ8u9E+Z+prPxTphe"
    "AKA2JmKYxlmVFlWylUNORE8bn9XxZzFEw2xKiyZcIIUTTTButUXRDLMpLZoaJM+hAmPJCe"
    "mkpTZaF2KQJvAqLa5sc9NVNc01WW98FMQzwkMIy2uooDnQsnol1TWZj4zcFiyve93bu07/"
    "3flJK+KBDFxu2CSW+OBsnmcUSeVHlMoKPjRPM0ij8gNJxQQfkI1WBklUfiR96cAJp+DEjP"
    "MpF6Z7NX2EL/LvkNtiQ7wyy24hA5aPwfkqTSMHG7As01BRLjmmocKEbdGoRplUA9oFecDR"
    "RDdGbPMvDN4kRuWFOB89IKCfIfxaymRfkWxbWRJ9RaP1uHNyhiP84nk5TVrv5VuTIRgHFo"
    "Ih03vFpnTRyb3o3xy3o+D8dWmX/WarzB+yL3TlReycAbXAK6SYbMdU+OJPkH55lUSZa26j"
    "EHuLlyy595dKqWdHb2/trmiv/gdqclSg"
)
