import discord
from discord.ext import commands
from discord.utils import find

from bot.utils.helpers import make_embed
from bot.config_loader import load_config, save_config
from bot.logger import setup_logging

logger = setup_logging("misc")

class MiscCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()

    # ─── Command: Set Default Channel ────────────────────────────────────────
    @commands.command(name="setchannel")
    async def set_channel(self, ctx):
        gid = str(ctx.guild.id)
        self.config["channels"][gid] = ctx.channel.id
        save_config(self.config)

        logger.info(f"✅ Channel set for guild {ctx.guild.name} to #{ctx.channel.name}")

        await ctx.send(embed=make_embed(
            title="✅ Channel Set",
            description=f"Announcements will be posted in {ctx.channel.mention}.",
            color=discord.Color.green()
        ))

    # ─── Command: Help ────────────────────────────────────────────────────────
    @commands.command(name="help", help="Show all commands.")
    async def help_cmd(self, ctx):
        commands_list = [
            "`!setchannel` – Set this channel for all announcements.",
            "`!setserverclock HH:MM` – Set your server's current time.",
            "`!setserverclock <DAY> HH:MM` – (Alt format) Set time + day.",
            "`!setserverday <DAY>` – Adjust the server clock to treat today as Monday.",
            "`!getservertime` – Check server time and UTC offset.",
            "`!settimezone Region/City` – Set your personal timezone.",
            "`!gettimezone` – View your timezone and local time.",
            "`!addevent Day HH:MM Name|Info [--autodelete]` – Weekly event.",
            "`!schedulecountdown <duration> Name|Info [--autodelete]` – One-time event.",
            "`!editeventtime <ID> HH:MM` – Change time of weekly event.",
            "`!editcountdown <ID> <duration>` – Change countdown duration.",
            "`!listevents` – List all scheduled events.",
            "`!todaysevents` – Show events scheduled for today only.",
            "`!nextevent` – Show the next upcoming event.",
            "`!checkautodelete <ID>` – Check if auto-delete is on.",
            "`!toggleautodelete <ID>` – Toggle auto-delete for an event.",
            "`!deleteevent <ID>` – Remove one event.",
            "`!deleteallevents` – Wipe all events with confirmation.",
            "`!nukeevents` – Instantly delete all events (no confirm).",
            "`!listalltips` – Show all tips in this server.",
            "`!addtip <tip>` – Add a tip (anyone can do it).",
            "`!removetip <index>` – Remove tip by index (no restrictions)."
        ]

        embed = make_embed(
            title="📚 Bot Commands",
            description="Here’s everything I support:",
            fields=[(cmd, "\u200b", False) for cmd in commands_list],
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    # ─── Auto Assign Default Channel on Guild Join ────────────────────────────
    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        gid = str(guild.id)
        default = guild.system_channel or find(
            lambda c: c.permissions_for(guild.me).send_messages,
            guild.text_channels
        )
        if default:
            self.config["channels"][gid] = default.id
            save_config(self.config)
            logger.info(f"🔧 Auto-set default channel for {guild.name} to #{default.name}")

    # ─── Global Error Handler ────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(embed=make_embed(
                title="⚠️ Missing Parameters",
                description=f"Correct usage: try `!help` to see how this command works.",
                color=discord.Color.orange()
            ))
            logger.warning(f"[MISSING ARG] {ctx.command} used by {ctx.author}")

        elif isinstance(error, commands.CommandNotFound):
            return  # Silently ignore unknown commands

        elif isinstance(error, commands.CommandInvokeError):
            await ctx.send(embed=make_embed(
                title="❌ Error",
                description="An error occurred while running that command.",
                color=discord.Color.red()
            ))
            logger.error(f"[INVOKE ERROR] {error.original}")

        else:
            await ctx.send(embed=make_embed(
                title="⚠️ Unknown Error",
                description="Something unexpected happened.",
                color=discord.Color.red()
            ))
            logger.error(f"[UNKNOWN ERROR] {error}")

# ─── Cog Setup ───────────────────────────────────────────────────────────────
async def setup(bot):
    await bot.add_cog(MiscCog(bot))
