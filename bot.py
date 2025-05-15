import discord
from discord.ext import commands
import asyncio
import os
import yt_dlp
from urllib.parse import urlparse
import concurrent.futures

intents = discord.Intents.default()
intents.message_content = True
command_prefix = '-'
bot = commands.Bot(command_prefix=command_prefix, intents=intents, help_command=None)

state_dict = {}

class State:
    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.queue = asyncio.Queue()
        self.currently_playing = ""
        self.question_callback = None
        self.search_list = []

process_pool = concurrent.futures.ProcessPoolExecutor()

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id})")

@bot.command(aliases=['j'])
async def join(ctx):
    if ctx.voice_client and ctx.voice_client.channel == ctx.author.voice.channel:
        return
    guild = get_guild(ctx)
    wipe(guild)
    channel = ctx.author.voice.channel
    await channel.connect()

    state_dict[guild] = State(guild_id=guild)

    asyncio.create_task(auto_disconnect_after_delay(ctx.guild.id))
    asyncio.create_task(player(ctx))

@bot.command(aliases=['l'])
async def leave(ctx):
    wipe(ctx.guild.id)
    if ctx.voice_client:
        await ctx.voice_client.disconnect()

@bot.command(aliases=['c'])
async def current(ctx):
    currently_playing = get_state(ctx).currently_playing

    if not ctx.voice_client or not ctx.voice_client.is_playing() or currently_playing == None:
        await ctx.send(f"Currently not playing a song.")
        return
    await ctx.send(f"Currently playing: **{currently_playing}**")

@bot.command(aliases=['p'])
async def play(ctx, *, query:str):
    voice_client = ctx.voice_client

    if not ctx.author.voice:
        await ctx.send("You need to be in a voice channel.")
        return
    
    if not voice_client or voice_client.channel != ctx.author.voice.channel:
        await join(ctx)
        voice_client = ctx.voice_client

    stream, title = await get_stream_youtube(ctx, query)
    
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
        await ctx.send(f"Skipping **{get_state(ctx).currently_playing}**.")

@bot.command(aliases=['q'])
async def queue(ctx):
    try:
        queue = get_state(ctx).queue
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

@bot.command(aliases=['h'])
async def help(ctx):
    message = f"❓\n"
    message += f"**{command_prefix}queue** or **{command_prefix}q** to see queued songs\n"
    message += f"**{command_prefix}current** or **{command_prefix}c** to see the currently playing song\n"
    message += f"**{command_prefix}play <track>** or **{command_prefix}p <track>** to play a song from youtube\n"
    message += f"**{command_prefix}playmul <track>, <track>** or **{command_prefix}pm <track>, <track>** to play multiple songs from youtube\n"
    message += f"**{command_prefix}skip** or **{command_prefix}s** to skip the currently playing song\n"
    message += f"**{command_prefix}join** or **{command_prefix}j** to have the bot join your current channel\n"
    message += f"**{command_prefix}leave** or **{command_prefix}l** to disconnect the bot from currently connected channel\n"
    await ctx.send(message)
    
@bot.command(aliases=['a'])
async def answer(ctx, *, answer:str):
    state = get_state(ctx)
    await state.question_callback(ctx, answer)

@bot.command(aliases=['s'])
async def search(ctx, *, query:str):
    if is_url(query):
        await ctx.send("You cannot search with urls.")
        return
    limit = 10
    list = search_youtube(ctx, query, limit)
    message = f"Search Results: \n"
    if len(list):
        await ctx.send("No results.")
        return
    for item in list:
        message += f"1. **{item[1]}**\n"

    message += f"\nWrite {command_prefix}answer <number> to select"
    await ctx.send(message)
    get_state(ctx).question_callback()   

async def search_callback(ctx, answer:str):
    if not str.isdigit(answer):
        await ctx.send("Searching can only be answered with (positive) numbers.")
        return
    selected = get_state(ctx).search_list[int(answer) - 1]
    await ctx.send(f"Selected **{selected[1]}**.")
    await play(ctx, selected[1])

def search_task(query, limit):
    search = {
    'extract_flat': True,
    'skip_download': True,
    'quiet': True,
    'noplaylist': True,
    }
    with yt_dlp.YoutubeDL(search) as track_search:
        result = track_search.extract_info(f"ytsearch:{query}", download=False)
        limit = min(limit, result['entries'])
        url = result['entries'][:limit]['url']
        title = result['entries'][:limit]['title']
        return zip(url, title)
    
async def search_youtube(ctx, query, limit):
    list = await asyncio.get_running_loop().run_in_executor(process_pool, search_task, query, limit)
    state = get_state(ctx)
    state.search_list = list
    return list

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

async def get_stream_youtube(ctx, query):
    queue = get_state(ctx).queue
    stream, title = await asyncio.get_running_loop().run_in_executor(process_pool, stream_task, query)
    await queue.put([stream, title])
    return stream, title

async def auto_disconnect_after_delay(ctx, delay=240):
    while True:
        await asyncio.sleep(delay)
        vc = discord.utils.get(bot.voice_clients, guild__id=ctx.guild.id)
        guild = get_guild(ctx)
        if not vc:
            return
        if vc and not vc.is_playing():
            await asyncio.sleep(2)
            if vc and not vc.is_playing():
                await vc.disconnect()
                wipe(guild)
                print(f"Disconnected from voice in guild {guild}")
                await ctx.send(f"Disconnected from the channel due to inactivity.")

async def player(ctx):
    vc = discord.utils.get(bot.voice_clients, guild__id=ctx.guild.id)
    state = get_state(ctx)
    queue = state.queue
    while True:
        [stream, title] = await queue.get()
        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn -bufsize 1M -rw_timeout 15000000',
        }
        audio = discord.FFmpegPCMAudio(stream, **ffmpeg_options)
        vc.play(audio)
        await ctx.send(f"Now playing: **{title}**")
        state.currently_playing = title
        while vc.is_playing():
            await asyncio.sleep(1)

        stream = ""

        vc = discord.utils.get(bot.voice_clients, guild__id=ctx.guild.id)
        if not vc:
            return

def wipe(guild_id):
    state_dict[guild_id] = None

def is_url(string):
    parsed = urlparse(string)
    return all([parsed.scheme, parsed.netloc])

def get_state(ctx):
    return state_dict[get_guild(ctx)]

def get_guild(ctx):
    return str(ctx.guild.id)

key = os.getenv("DISCORD_KEY")
bot.run(key)
