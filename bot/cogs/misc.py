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
    @commands.command(name="help", help="Show all available bot commands.")
    async def help_cmd(self, ctx):
        try:
            sections = [
                ("🕹️ Setup & Time Commands", [
                    "`!setchannel` - Set current channel for announcements.",
                    "`!setserverclock HH:MM` - Set current in-game server time.",
                    "`!setserverclock Day HH:MM` - Optional day setting too.",
                    "`!setserverday Day` - Force server day manually.",
                    "`!getservertime` - View current server time + offset.",
                    "`!settimezone Region/City` - Set your local timezone.",
                    "`!gettimezone` - View your current local timezone."
                ]),
                ("📅 Event Scheduling", [
                    "`!addevent Day HH:MM Name|Info [--autodelete]` - Weekly event.",
                    "`!schedulecountdown duration Name|Info [--autodelete]` - Countdown event.",
                    "`!listevents` - Show all events.",
                    "`!todaysevents` - Events happening today.",
                    "`!nextevent` - The next upcoming event."
                ]),
                ("✏️ Edit Events", [
                    "`!editweeklybyid ID [Day] HH:MM` - Edit by ID.",
                    "`!editweeklybyname Name [Day] HH:MM` - Edit by name.",
                    "`!editcountdownbyid ID duration` - Edit countdown by ID.",
                    "`!editcountdownbyname Name duration` - Edit countdown by name."
                ]),
                ("🗑️ Delete Events", [
                    "`!deleteevent ID` - Delete one event.",
                    "`!deleteeventbyname Name` - Delete all with matching name.",
                    "`!deleteallweekly` - Delete all weekly events.",
                    "`!deleteallcountdowns` - Delete all countdowns.",
                    "`!deleteallevents` - Nuke all events."
                ]),
                ("🔁 Auto-Delete Tools", [
                    "`!toggleautodelete ID` - Toggle for event.",
                    "`!checkautodelete ID` - Check auto-delete status."
                ]),
                ("🧠 Tips", [
                    "`!addtip Text` - Add a new tip.",
                    "`!removetip Index` - Remove by number.",
                    "`!listalltips` - Show all saved tips."
                ])
            ]

            for title, lines in sections:
                await ctx.send(embed=make_embed(
                    title=title,
                    description="\n".join(lines),
                    color=discord.Color.blue()
                ))

        except Exception as e:
            await ctx.send(embed=make_embed(
                title="❌ Help Error",
                description=f"Something went wrong.\n```{str(e)}```",
                color=discord.Color.red()
            ))

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
