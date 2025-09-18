import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta, timezone
import feedparser

from dateutil import parser as dateparser

# Token
from BotOfSin import GUILD_ID

# News Feeds
PORTSWIGGER_FEED = "https://portswigger.net/research/rss"
# CTBB Podcast Feed
CTBB_FEED = "https://media.rss.com/ctbbpodcast/feed.xml"


# ------------------ Portswigger Feed Parsing ------------------
def fetch_port_articles():
    feed = feedparser.parse(PORTSWIGGER_FEED)
    articles = []
    for entry in feed.entries:
        # Attempt to parse published/updated date
        published = None
        if hasattr(entry, "published"):
            try:
                published = dateparser.parse(entry.published).astimezone(timezone.utc)
            except Exception:
                published = None
        elif hasattr(entry, "updated"):
            try:
                published = dateparser.parse(entry.updated).astimezone(timezone.utc)
            except Exception:
                published = None

        articles.append({
            "title": entry.get("title", "No title"),
            "link": entry.get("link", ""),
            "summary": entry.get("summary", "") or entry.get("description", ""),
            "published": published,
            
            # Keep raw entry in case needed later
            "raw": entry
        })
    return articles

def articles_from_past_days(days: int = 30):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    articles = fetch_port_articles()
    recent = [a for a in articles if a["published"] and a["published"] >= cutoff]
    return sorted(recent, key=lambda x: x["published"], reverse=True)
# ------------------ Portswigger Feed Parsing End------------------

# ------------------ CTBB Podcast Parsing ------------------
def fetch_ctbb_episodes():
    """
    Parse the CTBB podcast RSS feed and return a list of episode dicts:
    { title, link, summary, published, audio }
    """
    feed = feedparser.parse(CTBB_FEED)
    episodes = []
    for entry in feed.entries:
        # parse published/updated date
        published = None
        if hasattr(entry, "published"):
            try:
                published = dateparser.parse(entry.published).astimezone(timezone.utc)
            except Exception:
                published = None
        elif hasattr(entry, "updated"):
            try:
                published = dateparser.parse(entry.updated).astimezone(timezone.utc)
            except Exception:
                published = None

        # Try to find audio enclosure (common for podcasts)
        audio_link = ""
        if hasattr(entry, "enclosures") and entry.enclosures:
            # pick first enclosure with href
            try:
                for e in entry.enclosures:
                    href = e.get("href") if isinstance(e, dict) else getattr(e, "href", None)
                    if href:
                        audio_link = href
                        break
            except Exception:
                audio_link = ""
        # fallback: sometimes media:content or links contain audio
        if not audio_link:
            try:
                if "media_content" in entry and entry.media_content:
                    for m in entry.media_content:
                        if m.get("url"):
                            audio_link = m.get("url")
                            break
            except Exception:
                pass

        # As a final fallback, use the entry link
        link = entry.get("link", "") or audio_link

        episodes.append({
            "title": entry.get("title", "No title"),
            "link": link,
            "audio": audio_link,
            "summary": entry.get("summary", "") or entry.get("description", ""),
            "published": published,
            "raw": entry
        })
    return episodes

def ctbb_episodes_from_past_days(days: int = 30):
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    episodes = fetch_ctbb_episodes()
    recent = [e for e in episodes if e["published"] and e["published"] >= cutoff]
    return sorted(recent, key=lambda x: x["published"], reverse=True)
# ------------------ CTBB Podcast Parsing End------------------

# ------------------ News Commands Cog ------------------
class NewsCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot


# ------------------ Portswigger Source Section ------------------
    # /portarticles
    @app_commands.command(name="portarticles", description="List PortSwigger research articles from the past 60 days")
    
    # Returns articles over a given period of time
    async def portarticles(self, interaction: discord.Interaction):
        articles = articles_from_past_days(60)  # Adjust for days
        if not articles:
            await interaction.response.send_message("No recent PortSwigger research articles in the past 60 days.")
            return

        # Five articles 
        per_page = 1
        pages = [articles[i:i+per_page] for i in range(0, len(articles), per_page)]

        def build_embed(page_index: int):
            page = pages[page_index]
            embed = discord.Embed(
                title=f"PortSwigger Research - Past 60 Days",
                color=discord.Color.green(),
            )
            for a in page:
                pub_str = a["published"].strftime("%Y-%m-%d") if a["published"] else "Unknown date"
                embed.add_field(
                    name=a["title"],
                    value=f"{pub_str} → [Read here]({a['link']})",
                    inline=False
                )
            return embed

        # Paginator for article view
        class ArticlePaginator(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=500)  # Timeout for page
                self.page = 0

            @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
            async def previous(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
                if self.page > 0:
                    self.page -= 1
                else:
                    self.page = len(pages) - 1 
                await interaction_btn.response.edit_message(embed=build_embed(self.page), view=self)

            @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
            async def next(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
                if self.page < len(pages) - 1:
                    self.page += 1
                else:
                    self.page = 0
                await interaction_btn.response.edit_message(embed=build_embed(self.page), view=self)

        view = ArticlePaginator()
        await interaction.response.send_message(embed=build_embed(0), view=view)
    
    # /portsearch 
    @app_commands.command(name="portsearch", description="Show info for a specific PortSwigger article")
    
    # Searches for a given article (or articles)
    async def portsearch(self, interaction: discord.Interaction, article_name: str):
        articles = fetch_port_articles()
        matches = [a for a in articles if article_name.lower() in a["title"].lower()]

        if not matches:
            matches = [a for a in articles if article_name.lower() in (a["summary"] or "").lower()]

        if not matches:
            await interaction.response.send_message(f"No PortSwigger article found matching: {article_name}")
            return

        # Creates pages for each article found 
        if len(matches) > 1:
            per_page = 1 
            pages = [matches[i:i+per_page] for i in range(0, len(matches), per_page)]

            # Embedded info for each page
            def build_embed(page_index: int):
                match = pages[page_index][0]
                summary = match["summary"] or ""
                summary = summary.replace("<br />", "\n").replace("<br/>", "\n").replace("<br>", "\n")
                summary = summary.replace("&mdash;", "—").replace("&nbsp;", " ")
                summary = summary.replace("<b>", "").replace("</b>", "")
                summary = summary.replace("<i>", "").replace("</i>", "")

                while "<a " in summary:
                    start = summary.find("<a ")
                    end = summary.find(">", start)
                    if end == -1:
                        break
                    summary = summary[:start] + summary[end+1:]
                summary = summary.replace("</a>", "")

                if len(summary) > 800:
                    summary = summary[:800] + "..."

                if match["published"]:
                    ts = int(match["published"].timestamp())
                    published_str = f"<t:{ts}:F> (<t:{ts}:R>)"
                else:
                    published_str = "Unknown"

                embed = discord.Embed(
                    title=match["title"],
                    url=match["link"],
                    description=summary.strip() if summary.strip() else "No summary available.",
                    color=discord.Color.green(),
                )
                embed.add_field(name="Published", value=published_str, inline=False)
                embed.add_field(name="Article Link", value=match["link"], inline=False)
                embed.set_footer(text=f"Result {page_index+1}/{len(pages)} for search: {article_name}")
                return embed

            # The search paginator 
            class InfoPaginator(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=500)
                    self.page = 0

                @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
                async def previous(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
                    if self.page > 0:
                        self.page -= 1
                    else:
                        self.page = len(pages) - 1
                    await interaction_btn.response.edit_message(embed=build_embed(self.page), view=self)

                @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
                async def next(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
                    if self.page < len(pages) - 1:
                        self.page += 1
                    else:
                        self.page = 0
                    await interaction_btn.response.edit_message(embed=build_embed(self.page), view=self)

            view = InfoPaginator()
            await interaction.response.send_message(embed=build_embed(0), view=view)
            return

        # For specific search (i.e. exact title) - Show full embedded response
        match = matches[0]

        # Clean and shorten summary similar to ctfinfo
        summary = match["summary"] or ""
        summary = summary.replace("<br />", "\n").replace("<br/>", "\n").replace("<br>", "\n")
        summary = summary.replace("&mdash;", "—").replace("&nbsp;", " ")
        summary = summary.replace("<b>", "").replace("</b>", "")
        summary = summary.replace("<i>", "").replace("</i>", "")

        while "<a " in summary:
            start = summary.find("<a ")
            end = summary.find(">", start)
            if end == -1:
                break
            summary = summary[:start] + summary[end+1:]
        summary = summary.replace("</a>", "")

        if len(summary) > 800:
            summary = summary[:800] + "..."

        if match["published"]:
            ts = int(match["published"].timestamp())
            published_str = f"<t:{ts}:F> (<t:{ts}:R>)"
        else:
            published_str = "Unknown"

        embed = discord.Embed(
            title=match["title"],
            url=match["link"],
            description=summary.strip() if summary.strip() else "No summary available.",
            color=discord.Color.green(),
        )
        
        embed.add_field(name="Published", value=published_str, inline=False)
        embed.add_field(name="Article Link", value=match["link"], inline=False)

        await interaction.response.send_message(embed=embed)
# ------------------ Portswigger Source Section End ------------------

# ------------------ CTBB Podcast Source Section ------------------
    # /ctbepisodes
    @app_commands.command(name="ctbepisodes", description="List CTBB podcast episodes from the past 30 days")
    async def ctbepisodes(self, interaction: discord.Interaction):
        await interaction.response.defer()  # Prevents timeout

        episodes = ctbb_episodes_from_past_days(30)
        if not episodes:
            await interaction.followup.send("No recent CTBB podcast episodes in the past 30 days.")
            return

        per_page = 1
        pages = [episodes[i:i+per_page] for i in range(0, len(episodes), per_page)]

        def build_embed(page_index: int):
            page = pages[page_index]
            embed = discord.Embed(
                title=f"CTBB Podcast - Past 30 Days",
                color=discord.Color.purple(),
            )
            for e in page:
                pub_str = e["published"].strftime("%Y-%m-%d") if e["published"] else "Unknown date"
                link_display = e["audio"] if e["audio"] else e["link"]
                embed.add_field(
                    name=e["title"],
                    value=f"{pub_str} → [Listen/Details]({link_display})",
                    inline=False
                )
            return embed

        # Paginator for episodes
        class EpisodePaginator(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=500)
                self.page = 0

            @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
            async def previous(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
                if self.page > 0:
                    self.page -= 1
                else:
                    self.page = len(pages) - 1
                await interaction_btn.response.edit_message(embed=build_embed(self.page), view=self)

            @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
            async def next(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
                if self.page < len(pages) - 1:
                    self.page += 1
                else:
                    self.page = 0
                await interaction_btn.response.edit_message(embed=build_embed(self.page), view=self)

        view = EpisodePaginator()
        await interaction.followup.send(embed=build_embed(0), view=view)

    # /ctbsearch
    @app_commands.command(name="ctbsearch", description="Search CTBB podcast episodes by title or summary")
    async def ctbsearch(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()  # Prevents timeout

        episodes = fetch_ctbb_episodes()
        matches = [e for e in episodes if query.lower() in e["title"].lower()]

        if not matches:
            matches = [e for e in episodes if query.lower() in (e["summary"] or "").lower()]

        if not matches:
            await interaction.followup.send(f"No CTBB episode found matching: {query}")
            return

        # Ya get it by now
        if len(matches) > 1:
            per_page = 1
            pages = [matches[i:i+per_page] for i in range(0, len(matches), per_page)]

            def build_embed(page_index: int):
                match = pages[page_index][0]
                summary = match["summary"] or ""
                summary = summary.replace("<br />", "\n").replace("<br/>", "\n").replace("<br>", "\n")
                summary = summary.replace("&mdash;", "—").replace("&nbsp;", " ")
                summary = summary.replace("<b>", "").replace("</b>", "")
                summary = summary.replace("<i>", "").replace("</i>", "")

                while "<a " in summary:
                    start = summary.find("<a ")
                    end = summary.find(">", start)
                    if end == -1:
                        break
                    summary = summary[:start] + summary[end+1:]
                summary = summary.replace("</a>", "")

                if len(summary) > 800:
                    summary = summary[:800] + "..."

                if match["published"]:
                    ts = int(match["published"].timestamp())
                    published_str = f"<t:{ts}:F> (<t:{ts}:R>)"
                else:
                    published_str = "Unknown"

                embed = discord.Embed(
                    title=match["title"],
                    url=match["link"],
                    description=summary.strip() if summary.strip() else "No summary available.",
                    color=discord.Color.purple(),
                )
                embed.add_field(name="Published", value=published_str, inline=False)
                audio_val = match["audio"] if match["audio"] else match["link"]
                embed.add_field(name="Listen / Link", value=audio_val, inline=False)
                embed.set_footer(text=f"Result {page_index+1}/{len(pages)} for search: {query}")
                return embed

            class EpisodeInfoPaginator(discord.ui.View):
                def __init__(self):
                    super().__init__(timeout=500)
                    self.page = 0

                @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
                async def previous(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
                    if self.page > 0:
                        self.page -= 1
                    else:
                        self.page = len(pages) - 1
                    await interaction_btn.response.edit_message(embed=build_embed(self.page), view=self)

                @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
                async def next(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
                    if self.page < len(pages) - 1:
                        self.page += 1
                    else:
                        self.page = 0
                    await interaction_btn.response.edit_message(embed=build_embed(self.page), view=self)

            view = EpisodeInfoPaginator()
            await interaction.followup.send(embed=build_embed(0), view=view)
            return

        # Specific search pages
        match = matches[0]
        summary = match["summary"] or ""
        summary = summary.replace("<br />", "\n").replace("<br/>", "\n").replace("<br>", "\n")
        summary = summary.replace("&mdash;", "—").replace("&nbsp;", " ")
        summary = summary.replace("<b>", "").replace("</b>", "")
        summary = summary.replace("<i>", "").replace("</i>", "")

        while "<a " in summary:
            start = summary.find("<a ")
            end = summary.find(">", start)
            if end == -1:
                break
            summary = summary[:start] + summary[end+1:]
        summary = summary.replace("</a>", "")

        if len(summary) > 800:
            summary = summary[:800] + "..."

        if match["published"]:
            ts = int(match["published"].timestamp())
            published_str = f"<t:{ts}:F> (<t:{ts}:R>)"
        else:
            published_str = "Unknown"

        embed = discord.Embed(
            title=match["title"],
            url=match["link"],
            description=summary.strip() if summary.strip() else "No summary available.",
            color=discord.Color.purple(),
        )
        embed.add_field(name="Published", value=published_str, inline=False)
        audio_val = match["audio"] if match["audio"] else match["link"]
        embed.add_field(name="Listen / Link", value=audio_val, inline=False)

        await interaction.followup.send(embed=build_embed(0), view=view)
        
# ------------------ CTBB Podcast Source Section End ------------------

# ------------------ News Commands Cog End ------------------

# Discord Setup
async def setup(bot):
    await bot.add_cog(NewsCommands(bot), guild=discord.Object(id=GUILD_ID))

