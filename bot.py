import discord
from discord.ext import commands
import asyncio
import subprocess
import os
import yt_dlp
import shutil
from urllib.parse import urlparse
import fcntl
import concurrent.futures

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

queue_dict = {}

process_pool = concurrent.futures.ProcessPoolExecutor()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")

@bot.command()
async def join(ctx):
    if ctx.voice_client and ctx.voice_client.channel == ctx.author.voice.channel:
        return
    wipe(ctx.guild.id)
    channel = ctx.author.voice.channel
    await channel.connect()

    queue = asyncio.Queue()
    queue_dict[str(ctx.guild.id)] = queue

    asyncio.create_task(auto_disconnect_after_delay(ctx.guild.id))
    asyncio.create_task(player(ctx))

@bot.command()
async def leave(ctx):
    wipe(ctx.guild.id)
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

    stream, title = await get_stream_youtube(ctx.guild.id, query)
    
    await ctx.send(f"Added to the list: {title}")

@bot.command()
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Stopped playback.")

def stream_task(query):
    ydl_opts = {
    'quiet': True,
    'noplaylist': True,
    'format': 'bestaudio/best',
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        url = query
        if not is_url(query):
            result = ydl.extract_info(f"ytsearch:{query}", download=False)
            url = result['entries'][0]['url']
            title = result['entries'][0]['title']
            info = ydl.extract_info(url, download=False)
            stream_url = info['url']
        else:
            info = ydl.extract_info(url, download=False)
            title = info['title']
            stream_url = info['url']
        
        return stream_url, title

async def get_stream_youtube(guild_id, query):
    queue = queue_dict[str(guild_id)]
    stream, title = await asyncio.get_running_loop().run_in_executor(process_pool, stream_task, query)
    await queue.put([stream, title])
    return stream, title

async def auto_disconnect_after_delay(guild_id, delay=240):
    while True:
        await asyncio.sleep(delay)
        vc = discord.utils.get(bot.voice_clients, guild__id=guild_id)
        if not vc:
            return
        if vc and not vc.is_playing():
            await asyncio.sleep(2)
            if vc and not vc.is_playing():
                await vc.disconnect()
                wipe(guild_id)
                print(f"Disconnected from voice in guild {guild_id}")

async def player(ctx):
    vc = discord.utils.get(bot.voice_clients, guild__id=ctx.guild.id)
    queue = queue_dict[str(ctx.guild.id)]
    while True:
        [stream, title] = await queue.get()

        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn -bufsize 1M -rw_timeout 15000000',
        }
        audio = discord.FFmpegPCMAudio(stream, **ffmpeg_options)
        vc.play(audio)
        await ctx.send(f"Now playing: {title}")
        while vc.is_playing():
            await asyncio.sleep(1)

        stream = ""

        vc = discord.utils.get(bot.voice_clients, guild__id=ctx.guild.id)
        if not vc:
            return

def wipe(guild_id):
    queue_dict[str(guild_id)] = None

def is_url(string):
    parsed = urlparse(string)
    return all([parsed.scheme, parsed.netloc])

key = os.getenv("DISCORD_KEY")
bot.run(key)
