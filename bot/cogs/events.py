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
        now_utc = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
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
                        target = target.replace(tzinfo=pytz.utc)
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
                description="Correct usage: `!addevent Day HH:MM Name|Info [--autodelete]`",
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
        now_utc = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        server_now = now_utc + datetime.timedelta(minutes=offset)

        # Check for duplicates
        for e in get_guild_events(self.all_events, gid):
            if e['name'].lower() == name.lower():
                return await ctx.send(embed=make_embed(
                    title="⚠️ Duplicate Event",
                    description=f"An event named `{name}` already exists.",
                    color=discord.Color.orange()
                ))

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
        logger.info(f"[ADD EVENT] {name} scheduled on {day_clean} {h:02d}:{m:02d} server time (offset {offset:+} min, UTC: {now_utc})")

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
                description="Correct usage: `!schedulecountdown 1d 04:30 Name|Info [--autodelete]` or `DD:HH:MM` format.",
                color=discord.Color.red()
            ))

        try:
            if any(c.isalpha() for c in duration):
                delta = parse_duration_string(duration)
            else:
                d, h, m = map(int, duration.strip().split(":"))
                delta = datetime.timedelta(days=d, hours=h, minutes=m)
        except Exception as e:
            logger.warning(f"Invalid duration: {duration} — {e}")
            return await ctx.send(embed=make_embed(
                title="❌ Invalid Duration Format",
                description="Use format like `1d 03:30` or `DD:HH:MM`.",
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
        now_utc = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        server_now = now_utc + datetime.timedelta(minutes=offset)
        fire_at = server_now + delta

        # Reject if the scheduled time is already in the past
        if fire_at < server_now:
            return await ctx.send(embed=make_embed(
                title="⚠️ Invalid Countdown Time",
                description="This countdown would trigger in the past. Use a future duration.",
                color=discord.Color.orange()
            ))

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
        logger.info(f"[COUNTDOWN] {name} scheduled for {fire_at} server time (offset {offset:+} min, UTC: {now_utc})")

        desc = f"**{name}** will go live in `{duration}` at **{fire_at.strftime('%A %H:%M')}** server time."
        if auto:
            desc += "\n✅ Will auto-delete after firing."

        await ctx.send(embed=make_embed(
            title="✅ Countdown Scheduled", description=desc,
            fields=[("Details", info, False)], color=discord.Color.green()
        ))


    # ─── EDITING EVENTS DATE AND TIME────────────────────────────────────
    # ─── Command: Edit Weekly Event by ID ────────────────────────────────────
    @commands.command(name="editweeklybyid")
    async def editweeklybyid(self, ctx, event_id: int = None, new_day_time: str = None):
        gid = str(ctx.guild.id)
        events = get_guild_events(self.all_events, gid)

        if event_id is None or new_day_time is None:
            return await ctx.send(embed=make_embed(
                title="❌ Missing Parameters",
                description="Usage: `!editweeklybyid [ID] Day HH:MM`",
                color=discord.Color.red()
            ))

        idx = event_id - 1
        if idx < 0 or idx >= len(events) or events[idx].get("type") != "normal":
            return await ctx.send(embed=make_embed(
                title="❌ Invalid ID",
                description="That ID does not correspond to a weekly event.",
                color=discord.Color.red()
            ))

        try:
            parts = new_day_time.strip().split()
            if len(parts) != 2:
                raise ValueError("Must provide Day and HH:MM.")
            new_day, new_time = parts
            new_day = new_day.capitalize()
            if new_day not in calendar.day_name:
                raise ValueError("Invalid day name.")
            h, m = map(int, new_time.split(":"))
            assert 0 <= h < 24 and 0 <= m < 60
        except:
            return await ctx.send(embed=make_embed(
                title="❌ Invalid Time",
                description="Time must be in `HH:MM` 24-hour format.",
                color=discord.Color.red()
            ))

        events[idx]["time"] = f"{h:02d}:{m:02d}"
        events[idx]["day"] = new_day
        save_all_events(self.all_events)
        await ctx.send(embed=make_embed(
            title="✏️ Weekly Event Updated",
            description=f"Updated `{events[idx]['name']}` to `{new_day} {h:02d}:{m:02d}`.",
            color=discord.Color.green()
        ))

    # ─── Command: Edit Weekly Event by Name ─────────────────────────────────
    @commands.command(name="editweeklybyname")
    async def editweeklybyname(self, ctx, name: str = None, new_day_time: str = None):
        gid = str(ctx.guild.id)
        if not name or not new_day_time:
            return await ctx.send(embed=make_embed(
                title="❌ Missing Parameters",
                description="Usage: `!editweeklybyname EventName HH:MM` or `EventName Day HH:MM`",
                color=discord.Color.red()
            ))

        events = get_guild_events(self.all_events, gid)
        updated = 0
        for e in events:
            if e.get("type") == "normal" and e['name'].lower() == name.lower():
                try:
                    parts = new_day_time.strip().split()
                    if len(parts) == 1:
                        h, m = map(int, parts[0].split(":"))
                        e['time'] = f"{h:02d}:{m:02d}"
                    elif len(parts) == 2:
                        new_day, new_time = parts
                        new_day = new_day.capitalize()
                        if new_day not in calendar.day_name:
                            raise ValueError("Invalid day name.")
                        h, m = map(int, new_time.split(":"))
                        e['time'] = f"{h:02d}:{m:02d}"
                        e['day'] = new_day
                    else:
                        raise ValueError("Invalid format.")
                    assert 0 <= h < 24 and 0 <= m < 60
                    e['time'] = f"{h:02d}:{m:02d}"
                    updated += 1
                except:
                    return await ctx.send(embed=make_embed(
                        title="❌ Invalid Time",
                        description="Time must be in `HH:MM` format.",
                        color=discord.Color.red()
                    ))

        if updated == 0:
            return await ctx.send(embed=make_embed(
                title="❌ Event Not Found",
                description=f"No weekly event named `{name}` found.",
                color=discord.Color.red()
            ))

        save_all_events(self.all_events)
        await ctx.send(embed=make_embed(
            title="✏️ Weekly Event(s) Updated",
            description=f"Updated `{updated}` event(s) named `{name}`.",
            color=discord.Color.green()
        ))

    # ─── Command: Edit Countdown by ID ──────────────────────────────────────
    @commands.command(name="editcountdownbyid")
    async def editcountdownbyid(self, ctx, event_id: int = None, duration: str = None):
        gid = str(ctx.guild.id)
        events = get_guild_events(self.all_events, gid)

        if event_id is None or duration is None:
            return await ctx.send(embed=make_embed(
                title="❌ Missing Parameters",
                description="Usage: `!editcountdownbyid [ID] duration`",
                color=discord.Color.red()
            ))

        idx = event_id - 1
        if idx < 0 or idx >= len(events) or events[idx].get("type") != "countdown":
            return await ctx.send(embed=make_embed(
                title="❌ Invalid ID",
                description="That ID does not correspond to a countdown event.",
                color=discord.Color.red()
            ))

        try:
            if any(c.isalpha() for c in duration):
                delta = parse_duration_string(duration)
            else:
                d, h, m = map(int, duration.strip().split(":"))
                delta = datetime.timedelta(days=d, hours=h, minutes=m)
        except:
            return await ctx.send(embed=make_embed(
                title="❌ Invalid Duration",
                description="Use format like `1d 02:30` or `DD:HH:MM`.",
                color=discord.Color.red()
            ))

        offset = self.config["server_offsets"].get(gid, 0)
        now_utc = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        server_now = now_utc + datetime.timedelta(minutes=offset)
        events[idx]['timestamp'] = (server_now + delta).isoformat()
        save_all_events(self.all_events)

        await ctx.send(embed=make_embed(
            title="✏️ Countdown Updated",
            description=f"Updated `{events[idx]['name']}` to trigger at `{events[idx]['timestamp']}`.",
            color=discord.Color.green()
        ))

    # ─── Command: Edit Countdown by Name ────────────────────────────────────
    @commands.command(name="editcountdownbyname")
    async def editcountdownbyname(self, ctx, name: str = None, duration: str = None):
        gid = str(ctx.guild.id)
        if not name or not duration:
            return await ctx.send(embed=make_embed(
                title="❌ Missing Parameters",
                description="Usage: `!editcountdownbyname EventName duration`",
                color=discord.Color.red()
            ))

        try:
            if any(c.isalpha() for c in duration):
                delta = parse_duration_string(duration)
            else:
                d, h, m = map(int, duration.strip().split(":"))
                delta = datetime.timedelta(days=d, hours=h, minutes=m)
        except:
            return await ctx.send(embed=make_embed(
                title="❌ Invalid Duration",
                description="Use format like `1d 02:30` or `DD:HH:MM`.",
                color=discord.Color.red()
            ))

        updated = 0
        offset = self.config["server_offsets"].get(gid, 0)
        now_utc = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        server_now = now_utc + datetime.timedelta(minutes=offset)

        for e in get_guild_events(self.all_events, gid):
            if e.get("type") == "countdown" and e['name'].lower() == name.lower():
                e['timestamp'] = (server_now + delta).isoformat()
                updated += 1

        if updated == 0:
            return await ctx.send(embed=make_embed(
                title="❌ Countdown Not Found",
                description=f"No countdown named `{name}` was found.",
                color=discord.Color.red()
            ))

        save_all_events(self.all_events)
        await ctx.send(embed=make_embed(
            title="✏️ Countdown(s) Updated",
            description=f"Updated `{updated}` countdown(s) named `{name}`.",
            color=discord.Color.green()
        ))


    # ─── Delete Events ─────────────────────────────────────────
    # ─── Command: Delete Event By Name ───────────────────────────────────────
    @commands.command(name="deleteeventbyname")
    async def deleteeventbyname(self, ctx, *, name: str = None):
        gid = str(ctx.guild.id)
        if not name:
            return await ctx.send(embed=make_embed(
                title="❌ Missing Parameter",
                description="Usage: `!deleteeventbyname Event Name`",
                color=discord.Color.red()
            ))

        events = get_guild_events(self.all_events, gid)
        filtered = [e for e in events if e['name'].lower() == name.lower()]
        if not filtered:
            return await ctx.send(embed=make_embed(
                title="❌ Event Not Found",
                description=f"No event named `{name}` exists.",
                color=discord.Color.red()
            ))

        self.all_events[gid] = [e for e in events if e['name'].lower() != name.lower()]
        save_all_events(self.all_events)
        await ctx.send(embed=make_embed(
            title="🗑️ Event Deleted",
            description=f"Deleted event(s) named `{name}`.",
            color=discord.Color.green()
        ))


    # ─── Command: Delete Event By ID ─────────────────────────────────────────
    @commands.command(name="deleteevent")
    async def deleteevent(self, ctx, event_id: int = None):
        gid = str(ctx.guild.id)
        if event_id is None:
            return await ctx.send(embed=make_embed(
                title="❌ Missing Parameter",
                description="Usage: `!deleteevent [event_id]`",
                color=discord.Color.red()
            ))

        events = get_guild_events(self.all_events, gid)
        idx = event_id - 1
        if idx < 0 or idx >= len(events):
            return await ctx.send(embed=make_embed(
                title="❌ Invalid Event ID",
                description=f"No event found for ID `{event_id}`.",
                color=discord.Color.red()
            ))

        removed = events.pop(idx)
        save_all_events(self.all_events)
        await ctx.send(embed=make_embed(
            title="🗑️ Event Deleted",
            description=f"Deleted event `{removed['name']}`.",
            color=discord.Color.green()
        ))


    # ─── Command: Delete All Countdown Events ───────────────────────────────
    @commands.command(name="deleteallcountdowns")
    async def deleteallcountdowns(self, ctx):
        gid = str(ctx.guild.id)
        before = len(get_guild_events(self.all_events, gid))
        self.all_events[gid] = [e for e in get_guild_events(self.all_events, gid) if e.get("type") != "countdown"]
        after = len(self.all_events[gid])
        save_all_events(self.all_events)

        await ctx.send(embed=make_embed(
            title="💣 Countdown Events Deleted",
            description=f"Removed `{before - after}` countdown event(s).",
            color=discord.Color.orange()
        ))

    # ─── Command: Delete All Weekly Events ───────────────────────────────────
    @commands.command(name="deleteallweekly")
    async def deleteallweekly(self, ctx):
        gid = str(ctx.guild.id)
        before = len(get_guild_events(self.all_events, gid))
        self.all_events[gid] = [e for e in get_guild_events(self.all_events, gid) if e.get("type") == "countdown"]
        after = len(self.all_events[gid])
        save_all_events(self.all_events)

        await ctx.send(embed=make_embed(
            title="🧹 Weekly Events Deleted",
            description=f"Removed `{before - after}` weekly event(s).",
            color=discord.Color.orange()
        ))

    # ─── Command: Delete All Events ─────────────────────────────────────────
    @commands.command(name="deleteallevents")
    async def deleteallevents(self, ctx):
        gid = str(ctx.guild.id)
        count = len(get_guild_events(self.all_events, gid))
        self.all_events[gid] = []
        save_all_events(self.all_events)

        await ctx.send(embed=make_embed(
            title="🗑️ All Events Deleted",
            description=f"Successfully deleted `{count}` total event(s).",
            color=discord.Color.red()
        ))

    # ─── Command: List All Events ─────────────────────────────────────────
    @commands.command(name="listevents")
    async def listevents(self, ctx):
        gid = str(ctx.guild.id)
        events = get_guild_events(self.all_events, gid)
        offset = self.config["server_offsets"].get(gid, 0)
        now_utc = datetime.datetime.utcnow()
        server_now = now_utc + datetime.timedelta(minutes=offset)

        weekly = []
        countdowns = []

        for e in events:
            try:
                if e.get("type") == "countdown":
                    fire_time = datetime.datetime.fromisoformat(e["timestamp"])
                    if fire_time > now_utc:
                        server_fire = fire_time + datetime.timedelta(minutes=offset)
                        countdowns.append(f"⏳ **{e['name']}** — {server_fire.strftime('%A %H:%M')} | {e.get('info', '')}")
                elif e.get("type") == "normal":
                    next_dt = next_event_datetime(e, server_now)
                    weekly.append(f"📆 **{e['name']}** — {e['day']} {e['time']} → {next_dt.strftime('%A %H:%M')}")
            except Exception as err:
                logger.warning(f"❌ Failed to parse event `{e.get('name')}`: {err}")

        if not weekly and not countdowns:
            return await ctx.send(embed=make_embed(
                title="📭 No Events Found",
                description="No countdown or weekly events scheduled.",
                color=discord.Color.red()
            ))

        description = ""
        if weekly:
            description += "**📆 Weekly Events:**\n" + "\n".join(weekly) + "\n\n"
        if countdowns:
            description += "**⏳ Countdown Events:**\n" + "\n".join(countdowns)

        await ctx.send(embed=make_embed(
            title="📋 Scheduled Events",
            description=description.strip(),
            color=discord.Color.blue()
        ))

    # ─── Command: Today's Events ─────────────────────────────────────────────
    @commands.command(name="todaysevents")
    async def todaysevents(self, ctx):
        gid = str(ctx.guild.id)
        offset = self.config["server_offsets"].get(gid, 0)
        server_now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc) + datetime.timedelta(minutes=offset)
        today = server_now.strftime("%A")
        events = get_guild_events(self.all_events, gid)

        lines = []
        for e in events:
            if e.get("type") == "normal" and e["day"] == today:
                h, m = map(int, e["time"].split(":"))
                event_dt = server_now.replace(hour=h, minute=m)
                utc_dt = event_dt - datetime.timedelta(minutes=offset)
                tz = self.config["user_timezones"].get(str(ctx.author.id))
                local = utc_dt.replace(tzinfo=pytz.utc).astimezone(pytz.timezone(tz)) if tz else None
                line = f"🗓️ **{e['time']}** server | {utc_dt.strftime('%H:%M')} UTC"
                if local:
                    line += f" | {local.strftime('%H:%M %Z')}"
                line += f" — **{e['name']}**"
                lines.append(line)
            elif e.get("type") == "countdown":
                dt = datetime.datetime.fromisoformat(e["timestamp"]).replace(tzinfo=pytz.utc)
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
        server_now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc) + datetime.timedelta(minutes=offset)
        events = get_guild_events(self.all_events, gid)

        upcoming = []
        for e in events:
            if e.get("type") == "normal":
                dt = next_event_datetime(e, server_now)
            else:
                dt = datetime.datetime.fromisoformat(e["timestamp"]).replace(tzinfo=pytz.utc)
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

        utc_dt = next_dt.astimezone(pytz.utc)
        tz = self.config["user_timezones"].get(str(ctx.author.id))
        local_dt = utc_dt.astimezone(pytz.timezone(tz)) if tz else None

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

