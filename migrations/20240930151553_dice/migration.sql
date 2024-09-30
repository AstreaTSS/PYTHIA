-- CreateTable
CREATE TABLE "thiadicenetry" (
    "id" SERIAL NOT NULL,
    "guild_id" BIGINT NOT NULL,
    "user_id" BIGINT NOT NULL,
    "name" TEXT NOT NULL,
    "value" TEXT NOT NULL,

    CONSTRAINT "thiadicenetry_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "thiadiceconfig" (
    "guild_id" BIGINT NOT NULL,
    "visible" BOOLEAN NOT NULL DEFAULT false,

    CONSTRAINT "thiadiceconfig_pkey" PRIMARY KEY ("guild_id")
);

-- CreateIndex
CREATE INDEX "thiadicenetry_guild_id_idx" ON "thiadicenetry"("guild_id");

-- CreateIndex
CREATE INDEX "thiadicenetry_guild_id_user_id_idx" ON "thiadicenetry"("guild_id", "user_id");

-- AddForeignKey
ALTER TABLE "thiadicenetry" ADD CONSTRAINT "thiadicenetry_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "thiadiceconfig"("guild_id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "thiadiceconfig" ADD CONSTRAINT "thiadiceconfig_guild_id_fkey" FOREIGN KEY ("guild_id") REFERENCES "thiaguildconfig"("guild_id") ON DELETE CASCADE ON UPDATE CASCADE;
