import discord
from discord.ext import commands
import asyncio
import os
import concurrent.futures
import tasks
import utils


# Setup


intents = discord.Intents.default()
intents.message_content = True
command_prefix = '-'
bot = commands.Bot(command_prefix=command_prefix, intents=intents, help_command=None)



# Main stateholding object and class for guilds


state_dict = {}

class State:
    def __init__(self, guild_id):
        self.guild_id = guild_id
        self.queue = asyncio.Queue()
        self.currently_playing = ""
        self.question_callback = None
        self.search_list = []
        self.is_processing = utils.AsyncSafeInt()

process_pool = concurrent.futures.ProcessPoolExecutor()



# Commands


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user.name} ({bot.user.id}).")


@bot.command(aliases=['j'])
async def join(ctx):
    if in_same_vc(ctx):
        return

    guild = get_guild(ctx)
    wipe(guild)
    channel = ctx.author.voice.channel
    state_dict[guild] = State(guild_id=guild)

    is_processing = get_state(ctx).is_processing
    await is_processing.increment()

    await channel.connect()

    asyncio.create_task(auto_disconnect_after_delay(ctx))
    asyncio.create_task(player(ctx))
    print(f"Joined channel in guild {get_guild(ctx)}.")
    await is_processing.decrement()


@bot.command(aliases=['l'])
async def leave(ctx):
    wipe(ctx.guild.id)
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        print(f"Left channel in {get_guild(ctx)}.")


@bot.command(aliases=['c'])
async def current(ctx):
    result = await assert_same_voice(ctx)
    if not result:
        return
    
    currently_playing = get_state(ctx).currently_playing

    if not ctx.voice_client or not ctx.voice_client.is_playing() or currently_playing == None:
        await ctx.send(f"Currently not playing a song.")
        return
    await ctx.send(f"Currently playing: **{currently_playing}**")


@bot.command(aliases=['cl'])
async def clear(ctx):
    result = await assert_same_voice(ctx)
    if not result:
        return
    get_state(ctx).queue = asyncio.Queue()
    await ctx.send(f"Cleared queue.")


@bot.command(aliases=['p'])
async def play(ctx, *, query:str=""):
    if not query.strip():
        await ctx.send(f"Please enter a track after the command.")
        return

    items = [item.strip() for item in query.split(",") if item.strip()]

    if len(items) == 0:
        await ctx.send(f"Please enter a valid track after the command.")    
        return

    result = await get_or_join_voice(ctx)
    if result == None:
        return
    
    is_processing = get_state(ctx).is_processing
    await is_processing.increment()

    for item in items:
        if utils.is_url(item) and utils.get_link_type(item) == "list":
            playlist = await get_playlist(item)
            await ctx.send(f"Adding requested playlist {item}")
            for i in playlist:
                asyncio.create_task(play_internal(ctx, i[0], quiet=True))
        else:
            asyncio.create_task(play_internal(ctx, item))

    await is_processing.decrement()


@bot.command(aliases=['s'])
async def skip(ctx):
    if not in_same_vc(ctx):
        return

    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send(f"Skipping **{get_state(ctx).currently_playing}**.")


@bot.command(aliases=['q'])
async def queue(ctx):
    result = await assert_same_voice(ctx)
    if not result:
        return

    try:
        queue = get_state(ctx).queue
        items = list(queue._queue)
    except:
        await ctx.send("Queue not found.")
        return
    message = f"📋\n"
    message += f"Song Queue:\n"
    if len(items) == 0:
        await ctx.send(f"Song queue is empty.")
        return
    for i, item in enumerate(items):
        if len(message + f"{i}. **{item[1]}**\n") > 2000:
            break
        message += f"{i}. **{item[1]}**\n"
    await ctx.send(message)


@bot.command(aliases=['h'])
async def help(ctx):
    message = f"❓\n"
    message += f"**{command_prefix}queue** or **{command_prefix}q** to see queued songs\n"
    message += f"**{command_prefix}current** or **{command_prefix}c** to see the currently playing song\n"
    message += f"**{command_prefix}play <track>** or **{command_prefix}p <track>** to play a song from youtube\n"
    message += f"**{command_prefix}play <track>, <track>** or **{command_prefix}p <track>, <track>** to play multiple songs\n"
    message += f"**{command_prefix}skip** or **{command_prefix}s** to skip the currently playing song\n"
    message += f"**{command_prefix}join** or **{command_prefix}j** to have the bot join your current channel\n"
    message += f"**{command_prefix}leave** or **{command_prefix}l** to disconnect the bot from currently connected channel\n"
    message += f"**{command_prefix}search <track>** or **{command_prefix}se <track>** to search for songs\n"
    await ctx.send(message)


@bot.command(aliases=['a'])
async def answer(ctx, *, answer:str):
    result = await assert_same_voice(ctx)
    if not result:
        return

    state = get_state(ctx)
    if state.question_callback == None:
        return

    is_processing = get_state(ctx).is_processing
    await is_processing.increment()

    await state.question_callback(ctx, answer)
    await is_processing.decrement()


@bot.command(aliases=['se'])
async def search(ctx, *, query:str=""):
    if not query.strip():
        await ctx.send(f"Please enter a track after the command.")
        return

    result = await get_or_join_voice(ctx)
    if result == None:
        return

    if utils.is_url(query):
        await ctx.send("You cannot search with urls.")
        return

    is_processing = get_state(ctx).is_processing
    await is_processing.increment()

    get_state(ctx).question_callback = search_callback
    limit = 10
    result_list = await search_youtube(ctx, query, limit)
    message = f"Search Results: \n"
    
    if len(result_list) == 0:
        await ctx.send("No results.")
        await is_processing.decrement()
        return
    for i, item in enumerate(result_list):
        message += f"{i}. **{item[1]}**"
        if utils.get_link_type(item[0]) == 'playlist':
            message += f" (This is a playlist.)"
        message += "\n"
    message += f"\nWrite {command_prefix}**answer <number>** to select"
    print(f"Completed search for query {query} in guild {get_guild(ctx)}")
    await ctx.send(message)
    await is_processing.decrement()



# Background tasks


async def auto_disconnect_after_delay(ctx, delay=240):
    print(f"Auto disconnect task is initialized in {get_guild(ctx)}.")
    while True:
        await asyncio.sleep(delay)
        vc = discord.utils.get(bot.voice_clients, guild__id=ctx.guild.id)
        guild = get_guild(ctx)
        if not vc:
            return
        processing = await is_processing(ctx)
        if vc and (not vc.is_playing() or vc_is_empty(vc)) and not processing:
            await asyncio.sleep(2)
            processing = await is_processing(ctx)
            if vc and (not vc.is_playing() or vc_is_empty(vc)) and not processing:
                await vc.disconnect()
                wipe(guild)
                print(f"Disconnected from voice in guild {guild}.")
                print(f"[AUTO_DISCONNECT] Playing: {vc.is_playing()}, Empty: {vc_is_empty(vc)}, Processing: {processing}")
                await ctx.send(f"Disconnected from the channel due to inactivity.")


async def player(ctx):
    vc = discord.utils.get(bot.voice_clients, guild__id=ctx.guild.id)
    state = get_state(ctx)
    queue = state.queue
    print(f"Player task is initialized in guild {get_guild(ctx)}.")
    while True:
        [stream, title] = await queue.get()
        
        is_processing = get_state(ctx).is_processing
        await is_processing.increment()

        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn -bufsize 1M -rw_timeout 15000000',
        }
        audio = discord.FFmpegPCMAudio(stream, **ffmpeg_options)
        vc.play(audio)
        print(f"Now playing: {title} in guild {get_guild(ctx)}.")
        await ctx.send(f"Now playing: **{title}**")
        state.currently_playing = title
        while vc.is_playing():
            await asyncio.sleep(1)


        await is_processing.decrement()
        stream = ""

        vc = discord.utils.get(bot.voice_clients, guild__id=ctx.guild.id)
        if not vc:
            return



# State related functions


def wipe(guild_id):
    if state_dict.get(guild_id) != None:
        state_dict[guild_id] = None


def get_state(ctx):
    return state_dict.get(get_guild(ctx))


def get_guild(ctx):
    return str(ctx.guild.id)


async def is_processing(ctx):
    if get_state(ctx) == None:
        return False
    result = await get_state(ctx).is_processing.get()
    return result != 0



# Checking related helper functions


async def get_or_join_voice(ctx):
    if ctx.author.voice == None:
        await ctx.send("You need to be in a voice channel.")
        return None
        
    if not in_same_vc(ctx):
        await join(ctx)
    
    return ctx.voice_client


def in_same_vc(ctx):
    return ctx.author.voice != None and ctx.voice_client != None and ctx.voice_client.channel == ctx.author.voice.channel


async def assert_same_voice(ctx):
    if not in_same_vc(ctx):
        await ctx.send("You need to be in the same voice chat as the bot.")
        return False
    return True


def vc_is_empty(vc):
    channel = vc.channel
    members = channel.members
    return len([member for member in members if not member.bot]) == 0



# Callback functions for answers


async def search_callback(ctx, answer:str):
    answer_list = [int(item.strip()) for item in answer.split(',') if item.strip().isdigit()]
    if len(answer_list) == 0:
        await ctx.send("Searching can only be answered with (positive) numbers.")
        return

    if len(get_state(ctx).search_list) == 0:
        await ctx.send("Ask a question first or wait for it to complete processing.")
        return

    if len(answer_list) >= 20:
        await ctx.send("Too many answers.")
        return

    search_list = get_state(ctx).search_list
    length = len(search_list)
    for answer in answer_list:
        if answer > length or answer < 1:
            await ctx.send(f"Your answers should be between 1 and {length}.")
            return
    
    for answer in answer_list:
        selected = get_state(ctx).search_list[answer - 1]
        print(f"Search callback function is called in guild {get_guild(ctx)}.")
        await ctx.send(f"Selected **{selected[1]}**.")
        asyncio.create_task(play_internal(ctx, selected[0]))
    get_state(ctx).question_callback = None



# Helper functions for commands


async def get_playlist(query):
    result = await asyncio.get_running_loop().run_in_executor(process_pool, tasks.playlist_task, query)
    return result


async def add_stream_to_queue(ctx, query):
    if utils.is_url(query):
        result = await asyncio.get_running_loop().run_in_executor(process_pool, tasks.stream_task, query)
    else:
        result = await asyncio.get_running_loop().run_in_executor(process_pool, tasks.search_task, query, 1)
        result = await asyncio.get_running_loop().run_in_executor(process_pool, tasks.stream_task, result[0][0])

    queue = get_state(ctx).queue
    await queue.put([result[0], result[1]])
    return result


async def search_youtube(ctx, query, limit):
    result_list = await asyncio.get_running_loop().run_in_executor(process_pool, tasks.search_task, query, limit, False)
    state = get_state(ctx)
    state.search_list = result_list
    return result_list


async def play_internal(ctx, query, quiet=False):
    is_processing = get_state(ctx).is_processing
    await is_processing.increment()
    result = await add_stream_to_queue(ctx, query)
    print(f"Done processing song {result[1]} in guild {get_guild(ctx)}.")
    if not quiet:
        await ctx.send(f"Added to the list: **{result[1]}**")
    await is_processing.decrement()



# Running the bot


key = os.getenv("DISCORD_KEY")
bot.run(key)
