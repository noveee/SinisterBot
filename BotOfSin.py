import discord
from discord.ext import commands

import json

# Load config for Token/ID Setup
with open("config.json", "r") as f:
    CONFIG = json.load(f)

DISCORD_TOKEN = CONFIG["DISCORD_TOKEN"]
GUILD_ID = CONFIG["GUILD_ID"]
CHANNEL_ID = CONFIG["CHANNEL_ID"]


intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# Logging
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        print(f"Synced {len(synced)} commands to guild {GUILD_ID}")
    except Exception as e:
        print(f"Sync error: {e}")

async def main():
    '''
    Commands

    /ping: Sanity Check 
    /week: Shows CTFs happening within 7 days
    /month: Shows CTFs happening within the current month
    

    /addctf <ctf>: Adds a given CTF to the queue DB
    /queue: Dumps the queue DB
    /dequeue <ctf>: Removes a CTF from the queue DB

    /ctfinfo <ctf>: Prints raw info for given CTF 
    /debugctfs: Prints full raw RSS feed and creates file 
    /debugraw; Prints raw info for the most recent CTF

    '''
    
    await bot.load_extension("cogs.CTFFunctions")
    await bot.load_extension("cogs.RSS")
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
