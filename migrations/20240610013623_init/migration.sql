-- CreateTable
CREATE TABLE "uinewconfig" (
    "guild_id" BIGSERIAL NOT NULL,
    "bullet_chan_id" BIGINT,
    "best_bullet_finder_role" BIGINT,
    "player_role" BIGINT,
    "bullets_enabled" BOOLEAN NOT NULL DEFAULT false,
    "investigation_type" SMALLINT NOT NULL DEFAULT 1,

    CONSTRAINT "uinewconfig_pkey" PRIMARY KEY ("guild_id")
);

-- CreateTable
CREATE TABLE "uinewtruthbullets" (
    "id" SERIAL NOT NULL,
    "trigger" VARCHAR(100) NOT NULL,
    "aliases" VARCHAR(40)[],
    "description" TEXT NOT NULL,
    "channel_id" BIGINT NOT NULL,
    "guild_id" BIGINT NOT NULL,
    "found" BOOLEAN NOT NULL,
    "finder" BIGINT,
    "hidden" BOOLEAN NOT NULL DEFAULT false,

    CONSTRAINT "uinewtruthbullets_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "idx_uinewtruthb_name_37580d" ON "uinewtruthbullets"("trigger", "channel_id", "guild_id", "found");
