import discord
from discord.ext import commands
import asyncio
import subprocess
import os
import yt_dlp
import shutil
from urllib.parse import urlparse
import threading
from concurrent.futures import ThreadPoolExecutor

download_dir = "./.downloads"

executor = ThreadPoolExecutor(max_workers=4)

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="//", intents=intents)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")

@bot.command()
async def join(ctx):
    wipe(ctx)
    channel = ctx.author.voice.channel
    await channel.connect()

    asyncio.create_task(auto_disconnect_after_delay(ctx.guild.id))
    asyncio.create_task(player(ctx))

@bot.command()
async def leave(ctx):
    wipe(ctx)
    if ctx.voice_client:
        await ctx.voice_client.disconnect()

@bot.command()
async def play(ctx, *, query:str):
    voice_client = ctx.voice_client

    if not ctx.author.voice:
        await ctx.send("You need to be in a voice channel.")
        return
    
    if not voice_client or voice_client.channel != ctx.author.voice.channel:
        await join(ctx)
        voice_client = ctx.voice_client

    await download_file(ctx.guild.id, query)
    
    await ctx.send(f"Added to the list: {query}")

@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Stopped playback.")
    
async def download_file(guild_id, query):
    path = os.path.join(download_dir, str(guild_id))
    if not os.path.exists(path):
        os.mkdir(path)
    await download_file_youtube(path, query)

async def download_file_youtube(path, query):
    def task():
        ydl_opts = {
            'quiet': True,
            'noplaylist': True,
            'outtmpl': f"{path}/%(title)s.%(ext)s",
            'format': 'bestaudio/best',
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            url = query
            if not is_url(query):
                result = ydl.extract_info(f"ytsearch:{query}", download=False)
                url = result['entries'][0]['url']
            ydl.download([url])
            
    await asyncio.to_thread(task)

async def auto_disconnect_after_delay(guild_id, delay=360):
    while True:
        await asyncio.sleep(delay)
        vc = discord.utils.get(bot.voice_clients, guild__id=guild_id)
        if not vc:
            return
        if vc and not vc.is_playing():
            await asyncio.sleep(2)
            if vc and not vc.is_playing():
                vc.disconnect()
                print(f"Disconnected from voice in guild {guild_id}")

async def player(ctx):
    vc = discord.utils.get(bot.voice_clients, guild__id=ctx.guild.id)
    files = []
    path = os.path.join(download_dir, str(ctx.guild.id))
    while True:
        files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)) and not f.endswith('.part')]
        while not files:
            await asyncio.sleep(1)
            files = [f for f in os.listdir(path) if os.path.isfile(os.path.join(path, f)) and not f.endswith('.part')]
        
        files.sort(key=lambda f: os.path.getmtime(os.path.join(path, f)), reverse=False)
    
        audio = discord.FFmpegPCMAudio(os.path.join(path, files[0]))

        vc.play(audio)
        await ctx.send(f"Now playing {os.path.basename(files[0])}")
        while vc.is_playing():
            await asyncio.sleep(1)

        os.remove(os.path.join(path, files[0]))

        vc = discord.utils.get(bot.voice_clients, guild__id=ctx.guild.id)
        if not vc:
            return

def wipe(ctx):
    path = os.path.join(download_dir, str(ctx.guild.id))
    if os.path.isdir(path):
        shutil.rmtree(path)

def is_url(string):
    parsed = urlparse(string)
    return all([parsed.scheme, parsed.netloc])

key = os.getenv("DISCORD_KEY")
bot.run(key)
