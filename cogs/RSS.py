# Imports
import discord
from discord.ext import commands
from discord import app_commands

# Token
from BotOfSin import GUILD_ID
from .FeedUtils import parse_feed, filter_recent, make_paginated_view, clean_summary, clean_ctbb_summary

# Feeds
PORTSWIGGER_FEED = "https://portswigger.net/research/rss"
CTBB_FEED = "https://media.rss.com/ctbbpodcast/feed.xml"

class NewsCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ------------------ PortSwigger Commands ------------------
    # /portarticles
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

    # /portsearch
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

    # ------------------ CTBB Podcast Commands ------------------
    # /ctbepisodes
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

    # /ctbsearch
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
