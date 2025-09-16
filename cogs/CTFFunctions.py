import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta, timezone

import feedparser
import sqlite3

from dateutil import parser as dateparser

# Token
from BotOfSin import GUILD_ID

# ------------------ DB Setup ------------------
conn = sqlite3.connect("ctf_ranks.db")
cursor = conn.cursor()

# Rank database
cursor.execute(
    "CREATE TABLE IF NOT EXISTS ranks (ctf_name TEXT PRIMARY KEY, rank TEXT)"
)

# Queue database
cursor.execute(
    "CREATE TABLE IF NOT EXISTS queue (ctf_name TEXT PRIMARY KEY, start_time INTEGER, link TEXT)"
)

conn.commit()
# ------------------ DB Setup End ------------------

# ------------------ Feed Parsing ------------------
def fetch_ctfs(feed_url: str):
    """Fetch CTFs from a CTFtime RSS feed with parsed start dates"""
    feed = feedparser.parse(feed_url)
    ctfs = []
    for entry in feed.entries:
        start_date = None
        
        # Grabbing entry based on start_date
        if hasattr(entry, "start_date"):
            try:
                start_date = dateparser.parse(entry.start_date).astimezone(timezone.utc)
            except Exception:
                pass
        # If start_date was not used, use published for regex
        elif hasattr(entry, "published"):
            try:
                start_date = dateparser.parse(entry.published).astimezone(timezone.utc)
            except Exception:
                pass

        ctfs.append(
            {
                "title": entry.get("title", "Unknown"),
                "link": entry.get("link", ""),
                "start_date": start_date,
                "summary": entry.get("summary", "No summary available."),
            }
        )
    return ctfs

def fetch_upcoming_ctfs():
    return fetch_ctfs("https://ctftime.org/event/list/upcoming/rss/")

def fetch_past_ctfs():
    return fetch_ctfs("https://ctftime.org/event/list/archive/rss/")
# ------------------ Feed Parsing End ------------------

# ------------------ CTF Commands Cog ------------------
'''
Commands

/ping: Sanity Check 
/week: Shows CTFs happening within 7 days
/month: Shows CTFs happening within the current month

/rank <ctf> <rank>: Input CTF rank into DB 
/getrank <ctf>: Shows given rank for CTF
/allranks: Dumps the rank DB 

/addctf <ctf>: Adds a given CTF to the queue DB
/queue: Dumps the queue DB
/dequeue <ctf>: Removes a CTF from the queue DB

/ctfinfo <ctf>: Prints raw info for given CTF 
/debugctfs: Prints full raw RSS feed and creates file 
/debugraw; Prints raw info for the most recent CTF
'''
class CTFCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

# ------------------ General Commands Section ------------------
    # /ping
    @app_commands.command(name="ping", description="Sanity check")
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("Pong!")

    # /week
    @app_commands.command(name="week", description="Show CTFs in the next 7 days")
    async def week(self, interaction: discord.Interaction):
        
        # Grabbing current time and end of week variable
        now = datetime.now(timezone.utc)
        end = now + timedelta(days=7)
        
        # Putting all CTFs happening within a week into a list using comprehension
        ctfs = [
            c for c in fetch_upcoming_ctfs()
            if c["start_date"] and now <= c["start_date"] <= end
        ]
        
        # If no CTFs happening within a week
        if not ctfs:
            await interaction.response.send_message("No CTFs in next 7 days.")
            return
        
        # Creating message variable that outputs all results in a clean format 
        msg = "**CTFs in next 7 days:**\n"
        for c in sorted(ctfs, key=lambda x: x["start_date"]):
            ts = int(c['start_date'].timestamp())
            msg += f"- {c['title']} | <t:{ts}:R> | <t:{ts}:F> | {c['link']}\n" # Title | Time Left | CTF Date | Link
        await interaction.response.send_message(msg)

    # /month
    @app_commands.command(name="month", description="Show CTFs this month")
    async def month(self, interaction: discord.Interaction):
        now = datetime.now(timezone.utc)
        
        # Using list comprehension to grab all CTFs happening in this current month & year
        ctfs = [
            c for c in fetch_upcoming_ctfs()
            if c["start_date"]
            and c["start_date"].month == now.month
            and c["start_date"].year == now.year
        ]
        
        # If no CTFs are happening within this month
        if not ctfs:
            await interaction.response.send_message("No CTFs this month.")
            return
        
        # Creating message variable that outputs all results in a clean format 
        msg = "**CTFs this month:**\n"
        for c in sorted(ctfs, key=lambda x: x["start_date"]):
            ts = int(c['start_date'].timestamp())
            msg += f"- {c['title']} | <t:{ts}:R> | <t:{ts}:F> | {c['link']}\n" # Title | Time Left | CTF Date | Link
        await interaction.response.send_message(msg)

    # /rank
    @app_commands.command(name="rank", description="Save rank for a CTF")
    
    # Saves CTF rank in DB and replaces rank if there is an existing one
    async def rank(self, interaction: discord.Interaction, ctf_name: str, rank: str):
        cursor.execute(
            "REPLACE INTO ranks (ctf_name, rank) VALUES (?, ?)", (ctf_name, rank)
        )
        conn.commit()
        await interaction.response.send_message(f"Saved {ctf_name}: {rank}")

    # /getrank
    @app_commands.command(name="getrank", description="Get rank for a CTF")
    
    # Gets a given CTF rank from the DB 
    async def getrank(self, interaction: discord.Interaction, ctf_name: str):
        cursor.execute("SELECT rank FROM ranks WHERE ctf_name = ?", (ctf_name,))
        r = cursor.fetchone()
        if r:
            await interaction.response.send_message(f"{ctf_name}: {r[0]}")
        else:
            await interaction.response.send_message(f"No rank found for {ctf_name}.")

    # /allranks
    @app_commands.command(name="allranks", description="Show all saved CTF ranks")
    
    # Dumps the entire rank DB 
    async def allranks(self, interaction: discord.Interaction):
        cursor.execute("SELECT ctf_name, rank FROM ranks")
        rows = cursor.fetchall()
        
        # Incase a DB has not been created
        if not rows:
            await interaction.response.send_message("No ranks saved yet.")
            return
        
        # Creating message variable that outputs all ranks in a clean format 
        msg = "**Saved CTF Ranks:**\n"
        for ctf, rank in rows:
            msg += f"- {ctf}: {rank}\n"
        await interaction.response.send_message(msg)
    
    # /addctf
    @app_commands.command(name="addctf", description="Add a CTF to the signup queue")

    # Searching for the given CTF, grabbing the name, start date, and calculating the time till it starts
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

        # Adding the CTF into the DB along with the other information
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

    # /queue
    @app_commands.command(name="queue", description="Show queued CTFs")
    
    # Dumps the entire queue DB 
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

    # /dequeue
    @app_commands.command(name="dequeue", description="Remove a CTF from the signup queue")
    
    # Removes a given CTF from the DB
    async def dequeue(self, interaction: discord.Interaction, ctf_name: str):
        cursor.execute("SELECT ctf_name FROM queue WHERE LOWER(ctf_name) LIKE ?", (f"%{ctf_name.lower()}%",))
        row = cursor.fetchone()

        if not row:
            await interaction.response.send_message(f"No CTF in queue matching: {ctf_name}")
            return

        cursor.execute("DELETE FROM queue WHERE ctf_name = ?", (row[0],))
        conn.commit()

        await interaction.response.send_message(f"Removed **{row[0]}** from the queue.")
    
    # /ctfinfo
    @app_commands.command(name="ctfinfo", description="Get info about a specific CTF")
    async def ctfinfo(self, interaction: discord.Interaction, ctf_name: str):
        
        # Search upcoming first, then past events
        ctfs = fetch_upcoming_ctfs()
        match = next((c for c in ctfs if ctf_name.lower() in c["title"].lower()), None)
        if not match:
            ctfs = fetch_past_ctfs()
            match = next((c for c in ctfs if ctf_name.lower() in c["title"].lower()), None)

        if not match:
            await interaction.response.send_message(f"No CTF found for: {ctf_name}")
            return

        # Using discord date formatting
        if match["start_date"]:
            ts = int(match["start_date"].timestamp())
            start_str = f"<t:{ts}:F> (<t:{ts}:R>)"
        else:
            start_str = "Unknown"

        # Cleaning up the raw HTML for the CTF summary
        summary = match["summary"]
        summary = summary.replace("<br />", "\n").replace("<br/>", "\n").replace("<br>", "\n")
        summary = summary.replace("&mdash;", "—").replace("&nbsp;", " ")
        summary = summary.replace("<b>", "").replace("</b>", "")
        summary = summary.replace("<i>", "").replace("</i>", "")
        
        # A long and drawn out way to remove the <a> tag and fix links
        while "<a " in summary:
            start = summary.find("<a ")
            end = summary.find(">", start)
            if end == -1:
                break
            summary = summary[:start] + summary[end+1:]
        summary = summary.replace("</a>", "")

        # Cutting the summary down
        if len(summary) > 500:
            summary = summary[:500] + "..."
            
        embed = discord.Embed(
            title=match["title"],
            url=match["link"],  # main event link
            description=summary.strip(),
            color=discord.Color.fuchsia(),
        )
        
        embed.add_field(name="Start Date", value=start_str, inline=False)
        embed.add_field(name="Event Link", value=match["link"], inline=False)

        await interaction.response.send_message(embed=embed)

# ------------------ Debugging Section ------------------
    # /debugctfs
    @app_commands.command(name = "debugctfs", description = "Dump all feed CTFs")
    async def debugctfs(self, interaction: discord.Interaction):
        ctfs = fetch_upcoming_ctfs()
        if not ctfs:
            await interaction.response.send_message("No CTFs found.")
            return
        msg = "Debug: Feed dump\n"
        for c in ctfs:
            d = (
                c["start_date"].strftime("%Y-%m-%d %H:%M UTC")
                if c["start_date"]
                else "Unknown"
            )
            msg += f"- {c['title']} | {d} | {c['link']}\n"
        if len(msg) > 2000:
            with open("debug_ctfs.txt", "w", encoding="utf-8") as f:
                f.write(msg)
            await interaction.response.send_message(file = discord.File("debug_ctfs.txt"))
        else:
            await interaction.response.send_message(msg)

    # /debugraw
    @app_commands.command(name="debugraw", description="Show raw fields of first feed entry")
    async def debugraw(self, interaction: discord.Interaction):
        ctfs = feedparser.parse("https://ctftime.org/event/list/upcoming/rss/").entries
        if not ctfs:
            await interaction.response.send_message("No entries found.")
            return
        first = ctfs[0]
        keys = "\n".join(
            [f"{k}: {first[k]}" for k in first.keys() if k not in ["summary_detail", "content"]]
        )
        await interaction.response.send_message(f"**First entry raw dump:**\n```{keys[:1900]}```")
# ------------------ CTF Commands Cog End ------------------

# Discord Setup
async def setup(bot):
    await bot.add_cog(CTFCommands(bot), guild = discord.Object(id = GUILD_ID))
