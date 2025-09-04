import discord
from discord.ext import commands
from discord import app_commands

import feedparser

# Token
from BotOfSin import GUILD_ID

# ------------------ Feed Parsing ------------------
def fetch_cyber_news():
    url = "https://feeds.megaphone.fm/cyberwire-daily-podcast"
    feed = feedparser.parse(url)
    news = []
    for entry in feed.entries[:5]:  # latest 5
        title = entry.get("title", "No title")
        link = entry.get("link", "")
        news.append({"title": title, "link": link})
    return news
# ------------------ Feed Parsing End------------------

# ------------------ News Commands Cog ------------------
'''
Commands

/cybernews: Prints recent CyberWire episodes and links
'''
class NewsCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    # /cybernews
    @app_commands.command(name="cybernews", description="Show latest CyberWire Daily episodes")
    async def cybernews(self, interaction: discord.Interaction):
        news = fetch_cyber_news()
        if not news:
            await interaction.response.send_message("No cyber news available.")
            return

        msg = "**Latest CyberWire Daily Episodes:**\n"
        for n in news:
            msg += f"- {n['title']} → {n['link']}\n"
        await interaction.response.send_message(msg)
# ------------------ News Commands Cog ------------------

# Discord Setup
async def setup(bot):
    await bot.add_cog(NewsCommands(bot), guild=discord.Object(id=GUILD_ID))
