import discord
import feedparser
import re

from html import unescape
from datetime import datetime, timezone, timedelta  
from dateutil import parser as dateparser

# ------------------ HTML Cleaners ------------------
def clean_summary(summary: str, max_length: int = 1000) -> str:
    '''
    Cleans up html tags in the given RSS source and returns a clean version
    
    Args:
        summary (str): Provided summary of the RSS source
        max_length (Optional [int]): Maximum of length of summary to be used
    
    Returns:
        str: Cleaned up summary with no tags
    '''
    
    if not summary:
        return "No summary available."

    summary = unescape(summary)
    summary = re.sub(r"<[^>]+>", "", summary)
    summary = re.sub(r"\n\s*\n", "\n\n", summary).strip()
    if len(summary) > max_length:
        summary = summary[:max_length] + "..."

    return summary

# Does not work properly 
def clean_ctbb_summary(summary: str, max_length: int = 800) -> str:
    '''
    Specialized cleaner for CTBB to get rid of footer notes
    
    Args:
        summary (str): Provided summary of the RSS source
        max_length (Optional [int]): Maximum of length of summary to be used
    
    Returns:
        str: Cleaned up summary with no tags and no footer
    '''
    
    if not summary:
        return "No summary available."
    summary = unescape(summary)
    summary = re.sub(r"<[^>]+>", "", summary)

    # Remove everything after the "======" 
    summary = re.split(r"={2,}.*", summary, maxsplit=1)[0]
    summary = re.sub(r"\s*\n\s*", "\n", summary).strip()

    if len(summary) > max_length:
        summary = summary[:max_length] + "..."

    return summary
# ------------------ HTML Cleaners End------------------

# ------------------ Feed Parsing ------------------
def parse_feed(feed_url: str, include_audio: bool = False):
    '''
    Grabs the feed for a given RSS source and retreives all needed information:
        title, link, summary, published, audio, and raw entry
    
    Args:
        feed_url (str): The RSS source to be parsed through
        include_audio (Optional [bool]): True if given source uses audio, False if audio is not used
    
    Returns:
        dictionary: The title, link, summary, published date, audio link, and raw entry of each entry in the feed  
    '''
    
    feed = feedparser.parse(feed_url)
    results = []
    for entry in feed.entries:
        # Attempt to parse published/updated date
        published = None
        if hasattr(entry, "published"):
            try:
                published = dateparser.parse(entry.published).astimezone(timezone.utc)
            except Exception:
                pass
        elif hasattr(entry, "updated"):
            try:
                published = dateparser.parse(entry.updated).astimezone(timezone.utc)
            except Exception:
                pass

        audio_link = ""
        
        # For the podcast sources
        if include_audio and hasattr(entry, "enclosures") and entry.enclosures:
            try:
                for e in entry.enclosures:
                    href = e.get("href") if isinstance(e, dict) else getattr(e, "href", None)
                    if href:
                        audio_link = href
                        break
            except Exception:
                pass

        results.append({
            "title": entry.get("title", "No title"),
            "link": entry.get("link", ""),
            "summary": entry.get("summary", "") or entry.get("description", ""),
            "published": published,
            "audio": audio_link if include_audio else None,
            
            # Keep raw entry in case needed later
            "raw": entry
        })
    return results

def parse_ctf_feed(feed_url: str):
    '''
    Specific handler for CTFtime source
    
    Args:
        feed_url (str): The RSS source to be parsed through
    
    Returns:
        dictionary: The title, link, summary, start date, and raw entry of each ctf entry 
    '''
    
    feed = feedparser.parse(feed_url)
    results = []
    for entry in feed.entries:
        start_date = None
        if hasattr(entry, "start_date"):
            try:
                start_date = dateparser.parse(entry.start_date).astimezone(timezone.utc)
            except Exception:
                pass
        elif hasattr(entry, "published"):
            try:
                start_date = dateparser.parse(entry.published).astimezone(timezone.utc)
            except Exception:
                pass
        
        results.append({
            "title": entry.get("title", "Unknown"),
            "link": entry.get("link", ""),
            "summary": entry.get("summary", ""),
            "start_date": start_date,
            "raw": entry
        })
    return results
# ------------------ Feed Parsing End ------------------

# ------------------ Filtering ------------------
def filter_recent(entries, days: int = 30):
    '''
    Search filter for the given RSS source
    
    Args:
        entries (dictionary): Dictionary of entries to filter out
        days (int): How many days to filter by
    
    Returns:
        list: A list of entries before the cutoff date
    '''
    
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=days)
    return [e for e in entries if e["published"] and e["published"] >= cutoff]
# ------------------ Filtering ------------------

# ------------------ Embed Pagination ------------------
def make_paginated_view(entries, list_title: str, color: discord.Color, link_label: str = "Read/Listen"):
    '''
    Creates a paginated entry for each given RSS source
    
    Args:
        entries (dictionary): Dictionary of entries to add to page
        list_title (str): Title of given source
        color (discord.Color): Color used for the paginator
        link_label (str): Label for the link to the source
    '''
    
    per_page = 1
    pages = [entries[i:i+per_page] for i in range(0, len(entries), per_page)]

    def build_embed(page_index: int):
        entry = pages[page_index][0]
        summary = clean_summary(entry["summary"], max_length=800)

        # Published time formatting
        if entry["published"]:
            ts = int(entry["published"].timestamp())
            published_str = f"<t:{ts}:F> (<t:{ts}:R>)"
        else:
            published_str = "Unknown"

        # Build embed
        embed = discord.Embed(
            title=entry["title"],
            url=entry["link"],
            description=summary,
            color=color
        )
        embed.add_field(name="Published", value=published_str, inline=False)

        link_display = entry.get("audio") or entry["link"]
        embed.add_field(name=link_label, value=link_display, inline=False)

        embed.set_footer(text=f"Result {page_index+1}/{len(pages)} — {list_title}")
        return embed

    # Good ole paginator
    class Paginator(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=1000)
            self.page = 0

        @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
        async def previous(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
            self.page = (self.page - 1) % len(pages)
            await interaction_btn.response.edit_message(embed=build_embed(self.page), view=self)

        @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
        async def next(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
            self.page = (self.page + 1) % len(pages)
            await interaction_btn.response.edit_message(embed=build_embed(self.page), view=self)

    return build_embed(0), Paginator()

def make_ctf_paginated_view(entries, list_title: str, color: discord.Color):
    '''
    Creates a paginated entry for each given RSS source
    
    Args:
        entries (dictionary): Dictionary of entries to add to page
        list_title (str): Title of given source
        color (discord.Color): Color used for the paginator
    '''
    
    per_page = 3
    pages = [entries[i:i+per_page] for i in range(0, len(entries), per_page)]

    def extract_field(summary: str, label: str):
        pattern = rf"{label}:\s*([^\n\r<]+)"
        match = re.search(pattern, summary, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return "Unknown"

    def extract_official_url(entry, summary: str):
        pattern = r"Official URL:\s*([^\n\r<]+)"
        match = re.search(pattern, summary, re.IGNORECASE)
        if match:
            return match.group(1).strip()

        raw = entry.get("raw")
        if raw:
            if "official_url" in raw:
                return raw["official_url"]
            if "url" in raw:
                return raw["url"]
            if "link" in raw and "ctftime.org/event" not in raw["link"]:
                return raw["link"]

        return "Unknown"

    def build_embed(page_index: int):
        embed = discord.Embed(title=list_title, color=color)

        for entry in pages[page_index]:
            summary = clean_summary(entry["summary"], max_length=400)

            if entry.get("start_date"):
                ts = int(entry["start_date"].timestamp())
                date_str = f"<t:{ts}:F> (<t:{ts}:R>)"
            elif entry.get("published"):
                ts = int(entry["published"].timestamp())
                date_str = f"<t:{ts}:F> (<t:{ts}:R>)"
            else:
                date_str = "Unknown"

            weight = extract_field(summary, "Weight")
            format_ = extract_field(summary, "Format")
            official_url = extract_official_url(entry, summary)

            if official_url != "Unknown":
                official_url_val = f"[Visit Site]({official_url})"
            else:
                official_url_val = "Unknown"

            field_val = (
                f"**Date:** {date_str}\n"
                f"**Weight:** {weight}\n"
                f"**Format:** {format_}\n"
                f"**Official URL:** {official_url_val}\n"
                f"[CTFTime Link]({entry['link']})"
            )

            embed.add_field(name=entry["title"], value=field_val, inline=False)

        embed.set_footer(text=f"Page {page_index+1}/{len(pages)} — {list_title}")
        return embed

    class Paginator(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=500)
            self.page = 0

        @discord.ui.button(label="⬅️", style=discord.ButtonStyle.secondary)
        async def previous(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
            self.page = (self.page - 1) % len(pages)
            await interaction_btn.response.edit_message(embed=build_embed(self.page), view=self)

        @discord.ui.button(label="➡️", style=discord.ButtonStyle.secondary)
        async def next(self, interaction_btn: discord.Interaction, button: discord.ui.Button):
            self.page = (self.page + 1) % len(pages)
            await interaction_btn.response.edit_message(embed=build_embed(self.page), view=self)

    return build_embed(0), Paginator()
# ------------------ Embed Pagination End ------------------
