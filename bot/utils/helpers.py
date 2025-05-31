import discord
import datetime
import calendar
from calendar import day_name

# ─── Embed Generator ─────────────────────────────────────────────────────────
def make_embed(
    title=None,
    description=None,
    color=discord.Color.blue(),
    fields: list[tuple[str, str, bool]] = None,
    footer: str = None
) -> discord.Embed:
    embed = discord.Embed(color=color)
    if title:
        embed.title = title
    if description:
        embed.description = description
    if fields:
        for name, value, inline in fields:
            embed.add_field(name=name, value=value, inline=inline)
    if footer:
        embed.set_footer(text=footer)
    return embed

# ─── Duration Parser ─────────────────────────────────────────────────────────
def parse_duration_string(duration_str):
    parts = duration_str.strip().lower().split()
    days, hours, minutes = 0, 0, 0

    for part in parts:
        if 'd' in part:
            days = int(part.replace('d', ''))
        elif ':' in part:
            h, m = map(int, part.split(':'))
            hours = h
            minutes = m

    return datetime.timedelta(days=days, hours=hours, minutes=minutes)

# ─── Next Weekly Event Calculation ───────────────────────────────────────────
def next_event_datetime(event, server_now):
    target_weekday = list(calendar.day_name).index(event["day"])
    h, m = map(int, event["time"].split(":"))
    candidate = server_now.replace(hour=h, minute=m, second=0, microsecond=0)
    days_ahead = (target_weekday - server_now.weekday()) % 7
    candidate += datetime.timedelta(days=days_ahead)
    if candidate <= server_now:
        candidate += datetime.timedelta(days=7)
    return candidate

# ─── Day Validator ───────────────────────────────────────────────────────────
def validate_event_day(day):
    return day.capitalize() in day_name
