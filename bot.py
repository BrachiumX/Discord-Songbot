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
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

queue_dict = {}
currently_playing = {}

process_pool = concurrent.futures.ProcessPoolExecutor()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")

@bot.command(aliases=['j'])
async def join(ctx):
    if ctx.voice_client and ctx.voice_client.channel == ctx.author.voice.channel:
        return
    wipe(ctx.guild.id)
    channel = ctx.author.voice.channel
    await channel.connect()

    queue = asyncio.Queue()
    queue_dict[str(ctx.guild.id)] = queue
    currently_playing[str(ctx.guild.id)] = ""

    asyncio.create_task(auto_disconnect_after_delay(ctx.guild.id))
    asyncio.create_task(player(ctx))

@bot.command(aliases=['l'])
async def leave(ctx):
    wipe(ctx.guild.id)
    if ctx.voice_client:
        await ctx.voice_client.disconnect()

@bot.command(aliases=['c'])
async def current(ctx):
    if not ctx.voice_client or not ctx.voice_client.is_playing() or currently_playing[str(ctx.guild.id)] == None:
        await ctx.send(f"Currently not playing a song.")
        return
    await ctx.send(f"Currently playing: **{currently_playing[str(ctx.guild.id)]}**")

@bot.command(aliases=['p'])
async def play(ctx, *, query:str):
    voice_client = ctx.voice_client

    if not ctx.author.voice:
        await ctx.send("You need to be in a voice channel.")
        return
    
    if not voice_client or voice_client.channel != ctx.author.voice.channel:
        await join(ctx)
        voice_client = ctx.voice_client

    stream, title = await get_stream_youtube(ctx.guild.id, query)
    
    await ctx.send(f"Added to the list: **{title}**")

@bot.command(aliases=['pm'])
async def playmul(ctx, *, query:str):
    voice_client = ctx.voice_client

    if not ctx.author.voice:
        await ctx.send("You need to be in a voice channel.")
        return
    
    if not voice_client or voice_client.channel != ctx.author.voice.channel:
        await join(ctx)
        voice_client = ctx.voice_client
    items = [item.strip() for item in query.split(",")]
    for item in items:
        asyncio.create_task(play(ctx, query=item))

@bot.command(aliases=['s'])
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Stopped playback.")

@bot.command(aliases=['q'])
async def queue(ctx):
    try:
        queue = queue_dict[str(ctx.guild.id)]
        items = list(queue._queue)
    except:
        await ctx.send("Queue not found.")
        return
    count = 0
    message = f"📋\n"
    message += f"Song Queue:\n"
    if len(items) == 0:
        await ctx.send(f"Song queue is empty.")
        return
    for i in items:
        message += f"{count}. **{i[1]}**\n"

    await ctx.send(message)

@bot.command()
async def help(ctx):
    message = f"❓\n"
    message += f"**!queue** or **!q** to see queued songs\n"
    message += f"**!current** or **!c** to see the currently playing song\n"
    message += f"**!play <track>** or **!p <track>** to play a song from youtube\n"
    message += f"**!playmul <track>, <track>** or **!pm <track>, <track>** to play multiple songs from youtube\n"
    message += f"**!skip** or **!s** to skip the currently playing song\n"
    message += f"**!join** or **!j** to have the bot join your current channel\n"
    message += f"**!leave** or **!l** to disconnect the bot from currently connected channel\n"
    await ctx.send(message)

def stream_task(query):
    search = {
    'extract_flat': True,
    'skip_download': True,
    'quiet': True,
    'noplaylist': True,
    }
    stream = {
    'extract_flat': False,
    'skip_download': True,
    'quiet': True,
    'noplaylist': True,
    'format': 'bestaudio/best',
    }
    
    with yt_dlp.YoutubeDL(stream) as stream_search:
        url = query
        if not is_url(query):
            with yt_dlp.YoutubeDL(search) as track_search:
                result = track_search.extract_info(f"ytsearch:{query}", download=False)
            url = result['entries'][0]['url']
            title = result['entries'][0]['title']
            info = stream_search.extract_info(url, download=False)
            stream_url = info['url']
        else:
            info = stream_search.extract_info(url, download=False)
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
        await ctx.send(f"Now playing: **{title}**")
        currently_playing[str(ctx.guild.id)] = title
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
