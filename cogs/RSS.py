# Imports
import discord
import asyncio
import sqlite3
from discord.ext import commands
from discord import app_commands

# Token
from BotOfSin import GUILD_ID, CHANNEL_ID
from .FeedUtils import parse_feed, filter_recent, make_paginated_view, clean_summary, clean_ctbb_summary, init_db

# Feeds
PORTSWIGGER_FEED = "https://portswigger.net/research/rss"
CYBERWIRE_FEED = "https://feeds.megaphone.fm/cyberwire-daily-podcast"
CTBB_FEED = "https://media.rss.com/ctbbpodcast/feed.xml"

class NewsCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
     
    # ------------------ Feed DB Setup ------------------
    async def feed_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            await self.check_feeds()
            await asyncio.sleep(60 * 60 * 12)  # every 12h

    async def check_feeds(self):
        conn = sqlite3.connect(feed_db.DB_PATH)
        cur = conn.cursor()
        cur.execute("SELECT id, name, url FROM feeds")
        feeds = cur.fetchall()

        for feed_id, name, url in feeds:
            entries = parse_feed(url, include_audio=True)
            for e in entries:
                guid = e["raw"].get("id") or e["link"]
                cur.execute("SELECT 1 FROM entries WHERE guid = ?", (guid,))
                if cur.fetchone():
                    continue  # Entry already in DB

                # Insert old entry into DB
                cur.execute("""INSERT INTO entries
                    (feed_id, guid, title, link, summary, published, audio, posted)
                    VALUES (?, ?, ?, ?, ?, ?, ?, 0)""",
                    (feed_id, guid, e["title"], e["link"], e["summary"],
                     e["published"].isoformat() if e["published"] else None,
                     e["audio"])
                )
                conn.commit()

                # Post update 
                channel = self.bot.get_channel(CHANNEL_ID)
                await channel.send(f"**{name}** just released: {e['title']} {e['link']}")
                cur.execute("UPDATE entries SET posted = 1 WHERE guid = ?", (guid,))
                conn.commit()

        conn.close()
    # ------------------ Feed DB Setup End ------------------

    # ------------------ PortSwigger Commands ------------------
    # /portarticles - shows all portswigger articles from a given a date
    @app_commands.command(name="portarticles", description="List PortSwigger research articles from the past 60 days")
    async def portarticles(self, interaction: discord.Interaction):
        await interaction.response.defer()
        articles = parse_feed(PORTSWIGGER_FEED)
        recent = filter_recent(articles, 60)
        if not recent:
            await interaction.followup.send("No recent PortSwigger research articles.")
            return
        embed, view = make_paginated_view(recent, "PortSwigger Research - Past 60 Days", discord.Color.orange(), "Read")
        await interaction.followup.send(embed=embed, view=view)

    # /portsearch - searches all portswigger articles for a given term
    @app_commands.command(name="portsearch", description="Search PortSwigger articles")
    async def portsearch(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        articles = parse_feed(PORTSWIGGER_FEED)
        matches = [a for a in articles if query.lower() in a["title"].lower() or query.lower() in (a["summary"] or "").lower()]
        if not matches:
            await interaction.followup.send(f"No PortSwigger articles found matching: {query}")
            return

        def build_embed(article):
            summary = clean_summary(article["summary"])
            ts = int(article["published"].timestamp()) if article["published"] else None
            published_str = f"<t:{ts}:F> (<t:{ts}:R>)" if ts else "Unknown"
            embed = discord.Embed(title=article["title"], url=article["link"], description=summary, color=discord.Color.orange())
            embed.add_field(name="Published", value=published_str, inline=False)
            embed.add_field(name="Article Link", value=article["link"], inline=False)
            return embed

        if len(matches) > 1:
            embeds = [build_embed(m) for m in matches]
            embed, view = make_paginated_view(matches, "PortSwigger Search Results", discord.Color.orange(), "Read")
            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.followup.send(embed=build_embed(matches[0]))
    # ------------------ PortSwigger Commands End ------------------

    # ------------------ CyberWire Podcast Commands ------------------
    # /cyberepisodes - shows CyberWire Daily episodes from a given date
    @app_commands.command(name="cyberepisodes", description="List CyberWire Daily podcast episodes from the past 30 days")
    async def cyberepisodes(self, interaction: discord.Interaction):
        await interaction.response.defer()
        episodes = parse_feed(CYBERWIRE_FEED, include_audio=True)
        recent = filter_recent(episodes, 7)
        if not recent:
            await interaction.followup.send("No recent CyberWire Daily episodes.")
            return
        embed, view = make_paginated_view(recent, "CyberWire Daily - Past 7 Days", discord.Color.blurple(), "Listen")
        await interaction.followup.send(embed=embed, view=view)

    # /cybersearch - searches all CyberWire Daily episodes for a given term
    @app_commands.command(name="cybersearch", description="Search CyberWire Daily podcast episodes")
    async def cybersearch(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        episodes = parse_feed(CYBERWIRE_FEED, include_audio=True)
        matches = [e for e in episodes if query.lower() in e["title"].lower() or query.lower() in (e["summary"] or "").lower()]
        if not matches:
            await interaction.followup.send(f"No CyberWire Daily episodes found matching: {query}")
            return

        def build_embed(ep):
            summary = clean_summary(ep["summary"]) 
            ts = int(ep["published"].timestamp()) if ep["published"] else None
            published_str = f"<t:{ts}:F> (<t:{ts}:R>)" if ts else "Unknown"
            embed = discord.Embed(
                title=ep["title"],
                url=ep["link"],
                description=summary,
                color=discord.Color.blurple()
            )
            embed.add_field(name="Published", value=published_str, inline=False)
            audio_val = ep["audio"] if ep["audio"] else ep["link"]
            embed.add_field(name="Listen / Link", value=audio_val, inline=False)
            return embed

        if len(matches) > 1:
            embed, view = make_paginated_view(matches, "CyberWire Daily Search Results", discord.Color.blurple(), "Listen")
            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.followup.send(embed=build_embed(matches[0]))
    # ------------------ CyberWire Podcast Commands End ------------------

    # ------------------ CTBB Podcast Commands ------------------
    # /ctbepisodes - shows all ctbb episodes from a given a date
    @app_commands.command(name="ctbepisodes", description="List CTBB podcast episodes from the past 30 days")
    async def ctbepisodes(self, interaction: discord.Interaction):
        await interaction.response.defer()
        episodes = parse_feed(CTBB_FEED, include_audio=True, )
        recent = filter_recent(episodes, 30)
        if not recent:
            await interaction.followup.send("No recent CTBB episodes.")
            return
        embed, view = make_paginated_view(recent, "CTBB Podcast - Past 30 Days", discord.Color.brand_red(), "Listen")
        await interaction.followup.send(embed=embed, view=view)

    # /ctbsearch - searches all ctbb episodes for a given term
    @app_commands.command(name="ctbsearch", description="Search CTBB podcast episodes")
    async def ctbsearch(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()
        episodes = parse_feed(CTBB_FEED, include_audio=True)
        matches = [e for e in episodes if query.lower() in e["title"].lower() or query.lower() in (e["summary"] or "").lower()]
        if not matches:
            await interaction.followup.send(f"No CTBB episodes found matching: {query}")
            return

        def build_embed(ep):
            summary = clean_ctbb_summary(ep["summary"]) 
            ts = int(ep["published"].timestamp()) if ep["published"] else None
            published_str = f"<t:{ts}:F> (<t:{ts}:R>)" if ts else "Unknown"
            embed = discord.Embed(
                title=ep["title"],
                url=ep["link"],
                description=summary,
                color=discord.Color.purple()
            )
            embed.add_field(name="Published", value=published_str, inline=False)
            audio_val = ep["audio"] if ep["audio"] else ep["link"]
            embed.add_field(name="Listen / Link", value=audio_val, inline=False)
            return embed

        if len(matches) > 1:
            embed, view = make_paginated_view(matches, "CTBB Search Results", discord.Color.brand_red(), "Listen")
            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.followup.send(embed=build_embed(matches[0]))
    # ------------------ CTBB Podcast Commands End ------------------
    
# Discord Setup
async def setup(bot):
    await bot.add_cog(NewsCommands(bot), guild=discord.Object(id=GUILD_ID))
