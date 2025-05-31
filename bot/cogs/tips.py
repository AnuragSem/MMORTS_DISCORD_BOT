import discord
from discord.ext import commands, tasks
import random

from bot.utils.helpers import make_embed
from bot.utils.storage import load_all_tips, save_all_tips, get_guild_tips
from bot.config_loader import load_config, save_config

class TipsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        self.all_tips = load_all_tips()
        self.send_daily_tip.start()

    # ─── Background Task: Daily Tip ──────────────────────────────────────────
    @tasks.loop(hours=24)
    async def send_daily_tip(self):
        for guild_id, channel_id in self.config.get("channels", {}).items():
            channel = self.bot.get_channel(channel_id)
            tips = get_guild_tips(self.all_tips, guild_id)
            if channel and tips:
                tip = random.choice(tips)
                embed = make_embed(
                    title="🧠 Daily Tip",
                    description=tip,
                    color=discord.Color.gold()
                )
                await channel.send(embed=embed)

    # ─── Tip Commands ────────────────────────────────────────────────────────
    @commands.command(name="listalltips", help="List all tips for this server.")
    async def listalltips(self, ctx):
        guild_id = str(ctx.guild.id)
        tips = get_guild_tips(self.all_tips, guild_id)
        if not tips:
            embed = make_embed(
                title="📝 No Tips Available",
                description="There are currently no tips for this server.",
                color=discord.Color.blue()
            )
            return await ctx.send(embed=embed)

        # Paginate if too many
        pages = [tips[i:i+10] for i in range(0, len(tips), 10)]
        for page_num, chunk in enumerate(pages, start=1):
            lines = [f"**{i+1 + (page_num-1)*10}.** {tip}" for i, tip in enumerate(chunk)]
            embed = make_embed(
                title=f"📝 Tips (Page {page_num}/{len(pages)})",
                description="\n".join(lines),
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)

    @commands.command(name="addtip", help="(Admin) Add a new daily tip.")
    @commands.has_permissions(administrator=True)
    async def addtip(self, ctx, *, tip: str):
        guild_id = str(ctx.guild.id)
        tips = get_guild_tips(self.all_tips, guild_id)
        tips.append(tip)
        save_all_tips(self.all_tips)
        embed = make_embed(
            title="✅ Tip Added",
            description=tip,
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

    @commands.command(name="removetip", help="(Admin) Remove a tip by its index.")
    @commands.has_permissions(administrator=True)
    async def removetip(self, ctx, index: int):
        guild_id = str(ctx.guild.id)
        tips = get_guild_tips(self.all_tips, guild_id)
        idx = index - 1
        if idx < 0 or idx >= len(tips):
            embed = make_embed(
                title="❌ Invalid Index",
                description=f"No tip at position {index}.",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed)

        removed = tips.pop(idx)
        save_all_tips(self.all_tips)
        embed = make_embed(
            title="🗑️ Tip Removed",
            description=removed,
            color=discord.Color.green()
        )
        await ctx.send(embed=embed)

# ─── Setup Function ─────────────────────────────────────────────────────────
async def setup(bot):
    await bot.add_cog(TipsCog(bot))
