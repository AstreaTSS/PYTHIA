-- CreateEnum
CREATE TYPE "ItemsRelationType" AS ENUM ('CHANNEL', 'USER');

-- CreateTable
CREATE TABLE "thiaitemssystemitems" (
    "id" SERIAL NOT NULL,
    "guild_id" BIGINT NOT NULL,
    "name" TEXT NOT NULL,
    "description" TEXT NOT NULL,
    "image" TEXT,
    "takeable" BOOLEAN NOT NULL DEFAULT false,

    CONSTRAINT "thiaitemssystemitems_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "thiaitemrelation" (
    "id" SERIAL NOT NULL,
    "item_id" INTEGER NOT NULL,
    "guild_id" BIGINT NOT NULL,
    "object_id" BIGINT NOT NULL,
    "object_type" "ItemsRelationType" NOT NULL,

    CONSTRAINT "thiaitemrelation_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "thiaitemsconfig" (
    "guild_id" BIGINT NOT NULL,
    "enabled" BOOLEAN NOT NULL DEFAULT false,

    CONSTRAINT "thiaitemsconfig_pkey" PRIMARY KEY ("guild_id")
);

-- CreateIndex
CREATE INDEX "thiaitemssystemitems_guild_id_idx" ON "thiaitemssystemitems"("guild_id");

-- CreateIndex
CREATE INDEX "thiaitemssystemitems_name_idx" ON "thiaitemssystemitems"("name");

-- CreateIndex
CREATE INDEX "thiaitemrelation_item_id_idx" ON "thiaitemrelation"("item_id");

-- CreateIndex
CREATE INDEX "thiaitemrelation_guild_id_idx" ON "thiaitemrelation"("guild_id");

-- CreateIndex
CREATE INDEX "thiaitemrelation_object_id_idx" ON "thiaitemrelation"("object_id");

-- AddForeignKey
ALTER TABLE "thiaitemssystemitems" ADD CONSTRAINT "thiaitemssystemitems_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "thiaitemsconfig"("guild_id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "thiaitemrelation" ADD CONSTRAINT "thiaitemrelation_item_id_fkey" FOREIGN KEY ("item_id") REFERENCES "thiaitemssystemitems"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "thiaitemsconfig" ADD CONSTRAINT "thiaitemsconfig_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "thiaguildconfig"("guild_id") ON DELETE CASCADE ON UPDATE CASCADE;
