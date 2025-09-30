# Imports
import os
import discord
import sqlite3

from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta, timezone

# Token
from BotOfSin import GUILD_ID
from .FeedUtils import parse_ctf_feed, make_ctf_paginated_view

# ------------------ Queue DB Setup ------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "ctfs.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute(
    "CREATE TABLE IF NOT EXISTS queue (ctf_name TEXT PRIMARY KEY, start_time INTEGER, link TEXT)"
)
conn.commit()
# ------------------ DB Setup End ------------------

# ------------------ Feed Sources ------------------
UPCOMING_FEED = "https://ctftime.org/event/list/upcoming/rss/"
PAST_FEED = "https://ctftime.org/event/list/archive/rss/"

def fetch_upcoming_ctfs():
    return parse_ctf_feed(UPCOMING_FEED)

def fetch_past_ctfs():
    return parse_ctf_feed(PAST_FEED)
# ------------------ Feed Sources End ------------------

# ------------------ CTF Commands Cog ------------------
class CTFCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # /ping - sanity check
    @app_commands.command(name="ping", description="Sanity check")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("Pong!")

    # /week - shows CTFs happening within 7 days
    @app_commands.command(name="week", description="Show CTFs in the next 7 days")
    async def week(self, interaction: discord.Interaction):
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=7)
        ctfs = [c for c in fetch_upcoming_ctfs() if c["start_date"] and now <= c["start_date"] <= end]

        if not ctfs:
            await interaction.response.send_message("No CTFs in next 7 days.")
            return

        embed, view = make_ctf_paginated_view(ctfs, "CTFs in Next 7 Days", discord.Color.fuchsia())
        await interaction.response.send_message(embed=embed, view=view)

    # /month - shows CTFs happening in the current month
    @app_commands.command(name="month", description="Show CTFs this month")
    async def month(self, interaction: discord.Interaction):
        now = datetime.now(timezone.utc)
        ctfs = [
            c for c in fetch_upcoming_ctfs()
            if c["start_date"] and c["start_date"].month == now.month and c["start_date"].year == now.year
        ]

        if not ctfs:
            await interaction.response.send_message("No CTFs this month.")
            return

        embed, view = make_ctf_paginated_view(ctfs, "CTFs This Month", discord.Color.fuchsia())
        await interaction.response.send_message(embed=embed, view=view)

    # /addctf - searching for the given CTF, grabbing the name, start date, and calculating the time till it starts
    @app_commands.command(name="addctf", description="Add a CTF to the signup queue")
    async def addctf(self, interaction: discord.Interaction, ctf_name: str):
        ctfs = fetch_upcoming_ctfs()
        match = next((c for c in ctfs if ctf_name.lower() in c["title"].lower()), None)

        if not match:
            await interaction.response.send_message(f"No upcoming CTF found for: {ctf_name}")
            return

        if not match["start_date"]:
            await interaction.response.send_message(f"{match['title']} has no known start date.")
            return

        ts = int(match["start_date"].timestamp())
        try:
            cursor.execute(
                "REPLACE INTO queue (ctf_name, start_time, link) VALUES (?, ?, ?)",
                (match["title"], ts, match["link"]),
            )
            conn.commit()
            await interaction.response.send_message(
                f"Added **{match['title']}** to queue! Starts <t:{ts}:R> (<t:{ts}:F>)"
            )
        except Exception as e:
            await interaction.response.send_message(f"Error adding to queue: {e}")

    # /queue - dumps the entire queue DB 
    @app_commands.command(name="queue", description="Show queued CTFs")
    async def queue(self, interaction: discord.Interaction):
        cursor.execute("SELECT ctf_name, start_time, link FROM queue ORDER BY start_time ASC")
        rows = cursor.fetchall()

        if not rows:
            await interaction.response.send_message("The queue is empty.")
            return

        msg = "**Queued CTFs:**\n"
        for name, ts, link in rows:
            msg += f"- {name} | <t:{ts}:R> | <t:{ts}:F> | {link}\n"
        await interaction.response.send_message(msg)

    # /dequeue - removes a given CTF from the DB
    @app_commands.command(name="dequeue", description="Remove a CTF from the signup queue")
    async def dequeue(self, interaction: discord.Interaction, ctf_name: str):
        cursor.execute("SELECT ctf_name FROM queue WHERE LOWER(ctf_name) LIKE ?", (f"%{ctf_name.lower()}%",))
        row = cursor.fetchone()

        if not row:
            await interaction.response.send_message(f"No CTF in queue matching: {ctf_name}")
            return

        cursor.execute("DELETE FROM queue WHERE ctf_name = ?", (row[0],))
        conn.commit()
        await interaction.response.send_message(f"Removed **{row[0]}** from the queue.")
# ------------------ CTF Commands Cog End ------------------

# Discord Setup
async def setup(bot):
    await bot.add_cog(CTFCommands(bot), guild = discord.Object(id = GUILD_ID))
