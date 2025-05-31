import discord
from discord.ext import commands
import os
from bot.config_loader import TOKEN
from bot.logger import setup_logging

logger = setup_logging("main")

# ─── Intents and Bot ─────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ─── Dynamic Cog Loader ──────────────────────────────────────────────────────
async def load_cogs():
    for filename in os.listdir("./bot/cogs"):
        if filename.endswith(".py") and not filename.startswith("_"):
            extension = f"bot.cogs.{filename[:-3]}"
            try:
                await bot.load_extension(extension)
                logger.info(f"✅ Loaded cog: {extension}")
            except Exception as e:
                logger.error(f"❌ Failed to load {extension}: {e}")

# ─── Bot Events ──────────────────────────────────────────────────────────────
@bot.event
async def on_ready():
    logger.info(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")
    logger.info("Bot is ready and running.")

# ─── Main Entry ──────────────────────────────────────────────────────────────
async def main():
    await load_cogs()
    await bot.start(TOKEN)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
