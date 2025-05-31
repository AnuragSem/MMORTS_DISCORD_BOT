import discord
from discord.ext import commands, tasks
import datetime
import calendar
import pytz
import humanize
import asyncio

from bot.utils.helpers import (
    make_embed,
    parse_duration_string,
    next_event_datetime,
    validate_event_day,
)
from bot.utils.storage import (
    load_all_events,
    save_all_events,
    get_guild_events,
    cleanup_invalid_event_days,
)
from bot.config_loader import load_config
from bot.logger import setup_logging

logger = setup_logging("events")

class EventsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = load_config()
        self.all_events = load_all_events()
        cleanup_invalid_event_days(self.all_events)
        self.check_events.start()
        self.cleanup_events.start()

    # ─── Background: Check and Trigger Events ────────────────────────────────
    @tasks.loop(minutes=1)
    async def check_events(self):
        now_utc = datetime.datetime.utcnow()
        for guild in self.bot.guilds:
            gid = str(guild.id)
            events = get_guild_events(self.all_events, gid)
            offset = self.config["server_offsets"].get(gid, 0)
            server_now = now_utc + datetime.timedelta(minutes=offset)
            channel_id = self.config["channels"].get(gid)
            channel = self.bot.get_channel(channel_id)

            for e in events:
                try:
                    if e.get("type") == "countdown":
                        target = datetime.datetime.fromisoformat(e["timestamp"])
                        if abs((server_now - target).total_seconds()) < 60 and channel:
                            await channel.send(content="@everyone", embed=make_embed(
                                title=f"📢 {e['name']} is Live!", description=e["info"], color=discord.Color.red()
                            ))
                            logger.info(f"[COUNTDOWN FIRED] {e['name']} for guild {gid}")
                            if e.get("auto_delete"):
                                e["last_trigger"] = now_utc.isoformat()
                                save_all_events(self.all_events)

                    elif e.get("type", "normal") == "normal" and e["day"] == server_now.strftime("%A"):
                        h, m = map(int, e["time"].split(":"))
                        event_dt = server_now.replace(hour=h, minute=m, second=0, microsecond=0)
                        if abs((server_now - event_dt).total_seconds()) < 60 and channel:
                            await channel.send(content="@everyone", embed=make_embed(
                                title=f"📢 {e['name']} is Live!", description=e["info"], color=discord.Color.red()
                            ))
                            logger.info(f"[WEEKLY FIRED] {e['name']} for guild {gid}")
                            if e.get("auto_delete"):
                                e["last_trigger"] = now_utc.isoformat()
                                save_all_events(self.all_events)

                except Exception as ex:
                    logger.error(f"❌ Failed to check or fire event: {e.get('name', '?')} — {ex}")

    # ─── Background: Auto-Delete Fired Events ────────────────────────────────
    @tasks.loop(hours=1)
    async def cleanup_events(self):
        now_utc = datetime.datetime.utcnow()
        changed = False
        for gid, events in self.all_events.items():
            for e in events[:]:
                if e.get("auto_delete") and e.get("last_trigger"):
                    last = datetime.datetime.fromisoformat(e["last_trigger"])
                    if now_utc >= last + datetime.timedelta(hours=24):
                        events.remove(e)
                        changed = True
                        logger.info(f"🗑️ Auto-deleted event '{e['name']}' from guild {gid}")
        if changed:
            save_all_events(self.all_events)

    # ─── Command: Add Weekly Event ───────────────────────────────────────────
    @commands.command(name="addevent")
    async def addevent(self, ctx, day: str = None, time: str = None, *, rest: str = None):
        if not day or not time or not rest:
            return await ctx.send(embed=make_embed(
                title="❌ Missing Parameters",
                description="Correct usage:\n`!addevent Day HH:MM Name|Info [--autodelete]`",
                color=discord.Color.red()
            ))

        day_clean = day.strip().capitalize()
        if not validate_event_day(day_clean):
            return await ctx.send(embed=make_embed(
                title="❌ Invalid Day",
                description="Use a weekday name like `Monday`, `Tuesday`, etc.",
                color=discord.Color.red()
            ))

        try:
            h, m = map(int, time.strip().split(":"))
            assert 0 <= h < 24 and 0 <= m < 60
        except:
            return await ctx.send(embed=make_embed(
                title="❌ Invalid Time Format",
                description="Time must be in 24h `HH:MM` format.",
                color=discord.Color.red()
            ))

        parts = rest.rsplit("--autodelete", 1)
        raw = parts[0].strip()
        auto = len(parts) == 2

        if "|" not in raw:
            return await ctx.send(embed=make_embed(
                title="❌ Missing Separator",
                description="Use `Name|Info` to separate the event name and its details.",
                color=discord.Color.red()
            ))

        name, info = map(str.strip, raw.split("|", 1))
        gid = str(ctx.guild.id)
        offset = self.config["server_offsets"].get(gid, 0)
        server_now = datetime.datetime.utcnow() + datetime.timedelta(minutes=offset)

        target_day = list(calendar.day_name).index(day_clean)
        event_time = server_now.replace(hour=h, minute=m, second=0, microsecond=0)
        days_ahead = (target_day - server_now.weekday()) % 7
        event_time += datetime.timedelta(days=days_ahead)

        if days_ahead == 0 and event_time < server_now:
            return await ctx.send(embed=make_embed(
                title="⚠️ Time Already Passed",
                description="This time has already passed today.",
                color=discord.Color.orange()
            ))

        entry = {
            "guild_id": gid,
            "type": "normal",
            "day": day_clean,
            "time": f"{h:02d}:{m:02d}",
            "name": name,
            "info": info,
            "auto_delete": auto
        }
        get_guild_events(self.all_events, gid).append(entry)
        save_all_events(self.all_events)
        logger.info(f"[ADD EVENT] {name} scheduled on {day_clean} {h:02d}:{m:02d} (Guild {gid})")

        await ctx.send(embed=make_embed(
            title="✅ Weekly Event Added",
            description=f"**{name}** on **{day_clean} {h:02d}:{m:02d}**",
            fields=[("Details", info, False)],
            color=discord.Color.green()
        ))

    # ─── Command: Schedule Countdown ─────────────────────────────────────────
    @commands.command(name="schedulecountdown")
    async def schedulecountdown(self, ctx, duration: str = None, *, rest: str = None):
        if not duration or not rest:
            return await ctx.send(embed=make_embed(
                title="❌ Missing Parameters",
                description="Correct usage:\n`!schedulecountdown 1d 04:30 Name|Info [--autodelete]`",
                color=discord.Color.red()
            ))

        try:
            delta = parse_duration_string(duration)
        except Exception as e:
            logger.warning(f"Invalid duration: {duration} — {e}")
            return await ctx.send(embed=make_embed(
                title="❌ Invalid Duration Format",
                description="Use format like `1d 03:30` or just `03:15`.",
                color=discord.Color.red()
            ))

        parts = rest.rsplit("--autodelete", 1)
        raw = parts[0].strip()
        auto = len(parts) == 2
        if "|" not in raw:
            return await ctx.send(embed=make_embed(
                title="❌ Missing Separator",
                description="Use `Name|Info [--autodelete]` format.",
                color=discord.Color.red()
            ))

        name, info = map(str.strip, raw.split("|", 1))
        gid = str(ctx.guild.id)
        offset = self.config["server_offsets"].get(gid, 0)
        server_now = datetime.datetime.utcnow() + datetime.timedelta(minutes=offset)
        fire_at = server_now + delta

        entry = {
            "type": "countdown",
            "timestamp": fire_at.isoformat(),
            "name": name,
            "info": info,
            "auto_delete": auto,
            "guild_id": gid
        }
        get_guild_events(self.all_events, gid).append(entry)
        save_all_events(self.all_events)
        logger.info(f"[COUNTDOWN] {name} scheduled for {fire_at} server time")

        desc = f"**{name}** will go live in `{duration}` at **{fire_at.strftime('%A %H:%M')}** server time."
        if auto:
            desc += "\n✅ Will auto-delete after firing."

        await ctx.send(embed=make_embed(
            title="✅ Countdown Scheduled", description=desc,
            fields=[("Details", info, False)], color=discord.Color.green()
        ))

    # ─── Command: Today's Events ─────────────────────────────────────────────
    @commands.command(name="todaysevents")
    async def todaysevents(self, ctx):
        gid = str(ctx.guild.id)
        offset = self.config["server_offsets"].get(gid, 0)
        server_now = datetime.datetime.utcnow() + datetime.timedelta(minutes=offset)
        today = server_now.strftime("%A")
        events = get_guild_events(self.all_events, gid)

        lines = []
        for e in events:
            if e.get("type") == "normal" and e["day"] == today:
                h, m = map(int, e["time"].split(":"))
                event_dt = server_now.replace(hour=h, minute=m)
                utc = event_dt - datetime.timedelta(minutes=offset)
                tz = self.config["user_timezones"].get(str(ctx.author.id))
                local = utc.replace(tzinfo=pytz.utc).astimezone(pytz.timezone(tz)) if tz else None
                line = f"🗓️ **{e['time']}** server | {utc.strftime('%H:%M')} UTC"
                if local:
                    line += f" | {local.strftime('%H:%M %Z')}"
                line += f" — **{e['name']}**"
                lines.append(line)
            elif e.get("type") == "countdown":
                dt = datetime.datetime.fromisoformat(e["timestamp"])
                if dt.date() == server_now.date():
                    lines.append(f"⏳ {dt.strftime('%H:%M')} server — **{e['name']}**")

        if not lines:
            return await ctx.send(embed=make_embed(
                title="📭 No Events Today",
                color=discord.Color.blue()
            ))

        await ctx.send(embed=make_embed(
            title="📅 Today's Events",
            description="\n".join(lines),
            color=discord.Color.blue()
        ))

    # ─── Command: Next Event ─────────────────────────────────────────────────
    @commands.command(name="nextevent")
    async def nextevent(self, ctx):
        gid = str(ctx.guild.id)
        offset = self.config["server_offsets"].get(gid, 0)
        server_now = datetime.datetime.utcnow() + datetime.timedelta(minutes=offset)
        events = get_guild_events(self.all_events, gid)

        upcoming = []
        for e in events:
            if e.get("type") == "normal":
                dt = next_event_datetime(e, server_now)
            else:
                dt = datetime.datetime.fromisoformat(e["timestamp"])
            if dt > server_now:
                upcoming.append((dt, e))

        if not upcoming:
            return await ctx.send(embed=make_embed(
                title="📭 No Upcoming Events",
                color=discord.Color.blue()
            ))

        next_dt, next_e = min(upcoming, key=lambda x: x[0])
        time_diff = next_dt - server_now
        human = humanize.precisedelta(time_diff, minimum_unit="seconds")
        utc_dt = next_dt - datetime.timedelta(minutes=offset)
        tz = self.config["user_timezones"].get(str(ctx.author.id))
        local_dt = utc_dt.replace(tzinfo=pytz.utc).astimezone(pytz.timezone(tz)) if tz else None

        fields = [
            ("Server Time", f"{next_e.get('day','')} {next_e.get('time', next_dt.strftime('%H:%M'))}", False),
            ("UTC Time", utc_dt.strftime("%a %H:%M UTC"), False),
            ("Starts In", human, False)
        ]
        if local_dt:
            fields.append(("Your Time", local_dt.strftime("%a %H:%M %Z"), False))

        await ctx.send(embed=make_embed(
            title=f"➡️ Next Event: {next_e['name']}",
            description=next_e["info"],
            fields=fields,
            color=discord.Color.green()
        ))

# ─── Setup ───────────────────────────────────────────────────────────────────
async def setup(bot):
    await bot.add_cog(EventsCog(bot))

