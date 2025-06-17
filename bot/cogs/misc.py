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
            ("🕹️ Setup & Time Commands", "\u200b"),
            ("`!setchannel`", "Set current channel for bot announcements."),
            ("`!setserverclock HH:MM`", "Set your in-game server time."),
            ("`!setserverclock Day HH:MM`", "Optionally set day as well."),
            ("`!setserverday Day`", "Shift the in-game day to desired one."),
            ("`!getservertime`", "Shows server time + offset from UTC."),
            ("`!settimezone Region/City`", "Set your local timezone."),
            ("`!gettimezone`", "View your local time info."),

            ("📅 Event Scheduling", "\u200b"),
            ("`!addevent Day HH:MM Name|Info [--autodelete]`", "Add a weekly recurring event."),
            ("`!schedulecountdown [duration] Name|Info [--autodelete]`", "Add a one-time countdown event. Duration supports `1d 03:00` or `2:04:30`."),
            ("`!listevents`", "List all weekly and countdown events."),
            ("`!todaysevents`", "List events happening today."),
            ("`!nextevent`", "Show the next event and time remaining."),

            ("✏️ Edit Events", "\u200b"),
            ("`!editweeklybyid ID [Day] HH:MM`", "Edit a weekly event’s time and/or day."),
            ("`!editweeklybyname Name [Day] HH:MM`", "Edit all matching weekly events by name."),
            ("`!editcountdownbyid ID [duration]`", "Edit countdown (1d 03:30 or 1:01:00)."),
            ("`!editcountdownbyname Name [duration]`", "Edit all matching countdowns."),

            ("🗑️ Delete Events", "\u200b"),
            ("`!deleteevent ID`", "Delete a specific event by index."),
            ("`!deleteeventbyname Name`", "Delete all events by name."),
            ("`!deleteallweekly`", "Remove all weekly events."),
            ("`!deleteallcountdowns`", "Remove all countdown events."),
            ("`!deleteallevents`", "Remove all events (confirmation free)."),

            ("🔁 Auto-Delete Tools", "\u200b"),
            ("`!toggleautodelete ID`", "Enable/disable auto-delete for an event."),
            ("`!checkautodelete ID`", "Check if an event has auto-delete on."),

            ("🧠 Daily Tips", "\u200b"),
            ("`!listalltips`", "Show all saved tips."),
            ("`!addtip Tip text...`", "Add a new tip."),
            ("`!removetip Index`", "Remove a tip by number."),
        ]

        embed = make_embed(
            title="📚 Command Reference",
            description="Here are all available commands grouped by category.",
            fields=[(name, desc, False) for name, desc in commands_list],
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
