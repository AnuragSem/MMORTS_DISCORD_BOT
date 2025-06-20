import discord
from discord.ext import commands
import datetime
import pytz
import calendar

from bot.utils.helpers import make_embed
from bot.config_loader import load_config, save_config
from bot.logger import setup_logging

logger = setup_logging("time")

class TimeCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()

    # ─── Command: Set Server Clock (Day Optional) ─────────────────────────────
    @commands.command(name="setserverclock")
    async def set_server_clock(self, ctx, *args):
        try:
            if len(args) == 1:
                # Format: !setserverclock HH:MM
                time_str = args[0]
                day_name = None
            elif len(args) == 2:
                # Format: !setserverclock Friday 00:00
                day_name, time_str = args
                day_name = day_name.capitalize()
                if day_name not in calendar.day_name:
                    raise ValueError("Invalid day name.")
            else:
                raise ValueError("Wrong number of arguments.")

            h, m = map(int, time_str.split(":"))
            assert 0 <= h < 24 and 0 <= m < 60

            now_utc = datetime.datetime.utcnow().replace(second=0, microsecond=0)

            # Calculate target datetime based on provided time and (optional) day
            if day_name:
                target_weekday = list(calendar.day_name).index(day_name)
                current_weekday = now_utc.weekday()
                days_ahead = (target_weekday - current_weekday) % 7
            else:
                days_ahead = 0

            # Create target datetime safely
            target = (now_utc + datetime.timedelta(days=days_ahead)).replace(hour=h, minute=m)

            # Final offset in minutes
            offset_minutes = int((target - now_utc).total_seconds() / 60)

            self.config["server_offsets"][str(ctx.guild.id)] = offset_minutes
            save_config(self.config)

            logger.info(f"✅ Set server offset for {ctx.guild.name} to {offset_minutes:+} mins")

            embed = make_embed(
                title="✅ Server Clock Set",
                fields=[
                    ("Requested", f"{day_name or now_utc.strftime('%A')} {time_str}", False),
                    ("Offset", f"{offset_minutes:+} minutes from UTC", False)
                ],
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

        except Exception as e:
            logger.warning(f"❌ Error in setserverclock: {e}")
            await ctx.send(embed=make_embed(
                title="❌ Invalid Format",
                description="Usage: `!setserverclock HH:MM` or `!setserverclock Day HH:MM` (24-hour).",
                color=discord.Color.red()
            ))

    # ─── Command: Set Server Day ─────────────────────────────
    @commands.command(name="setserverday")
    async def set_server_day(self, ctx, day: str = None):
        if not day:
            return await ctx.send(embed=make_embed(
                title="❌ Missing Parameter",
                description="Usage: `!setserverday Monday`",
                color=discord.Color.red()
            ))

        day = day.capitalize()
        if day not in calendar.day_name:
            return await ctx.send(embed=make_embed(
                title="❌ Invalid Day",
                description="Day must be a valid weekday name (e.g., Monday, Friday).",
                color=discord.Color.red()
            ))

        now_utc = datetime.datetime.utcnow()
        target_weekday = list(calendar.day_name).index(day)
        current_weekday = now_utc.weekday()

        # Calculate how many days to shift to get to target weekday
        delta_days = (target_weekday - current_weekday) % 7
        shifted_time = now_utc + datetime.timedelta(days=delta_days)

        # Maintain current time (HH:MM), shift the day
        new_offset = int((shifted_time - now_utc).total_seconds() / 60)

        gid = str(ctx.guild.id)
        self.config["server_offsets"][gid] = self.config["server_offsets"].get(gid, 0) + new_offset
        save_config(self.config)

        logger.info(f"✅ Set server day for guild {gid} to {day} (offset adjusted by {new_offset} mins)")

        await ctx.send(embed=make_embed(
            title="📅 Server Day Adjusted",
            fields=[
                ("Target Day", day, False),
                ("Offset Change", f"{new_offset:+} minutes", False),
                ("New Total Offset", f"{self.config['server_offsets'][gid]:+} minutes", False)
            ],
            color=discord.Color.green()
        ))

    # ─── Command: Get Server Time ────────────────────────────────────────────
    @commands.command(name="getservertime")
    async def get_server_time(self, ctx):
        gid = str(ctx.guild.id)
        offset = self.config["server_offsets"].get(gid)
        if offset is None:
            return await ctx.send(embed=make_embed(
                title="❌ Not Set",
                description="Use `!setserverclock HH:MM` first.",
                color=discord.Color.red()
            ))

        now_utc = datetime.datetime.utcnow()
        server_now = now_utc + datetime.timedelta(minutes=offset)

        logger.debug(f"🕒 Server time checked by {ctx.author.name} in {ctx.guild.name}")

        embed = make_embed(
            title="🕒 Server Time",
            fields=[
                ("Offset", f"{offset:+} minutes", False),
                ("Current", server_now.strftime("%A %H:%M"), False)
            ],
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)

    # ─── Command: Set User Timezone ──────────────────────────────────────────
    @commands.command(name="settimezone")
    async def set_timezone(self, ctx, tz: str):
        try:
            pytz.timezone(tz)  # Validate timezone
            self.config["user_timezones"][str(ctx.author.id)] = tz
            save_config(self.config)
            logger.info(f"✅ {ctx.author.name} set their timezone to {tz}")
            await ctx.send(embed=make_embed(
                title="✅ Timezone Set",
                description=f"Your timezone is now **{tz}**.",
                color=discord.Color.green()
            ))

        except pytz.UnknownTimeZoneError:
            await ctx.send(embed=make_embed(
                title="❌ Invalid Timezone",
                description="Use a valid tz string like `Asia/Kolkata`.",
                color=discord.Color.red()
            ))

    # ─── Command: Get User Timezone ──────────────────────────────────────────
    @commands.command(name="gettimezone")
    async def get_timezone(self, ctx):
        uid = str(ctx.author.id)
        tz = self.config["user_timezones"].get(uid)
        if not tz:
            return await ctx.send(embed=make_embed(
                title="❌ No Timezone Set",
                description="Use `!settimezone Region/City`.",
                color=discord.Color.red()
            ))

        now = datetime.datetime.now(pytz.timezone(tz))
        await ctx.send(embed=make_embed(
            title="🌐 Your Timezone",
            fields=[
                ("Timezone", tz, False),
                ("Local Time", now.strftime("%A %H:%M %Z"), False)
            ],
            color=discord.Color.blue()
        ))

# ─── Setup ───────────────────────────────────────────────────────────────────
async def setup(bot):
    await bot.add_cog(TimeCog(bot))
