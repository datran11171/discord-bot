import os
import discord
from discord.ext import commands
from discord import app_commands
from dotenv import load_dotenv
import yt_dlp
import asyncio
from collections import deque



load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

SONG_QUEUES = {}

GUILD_ID = 749579527239499826

async def search_ytdlp_async(query, ydl_opts):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: _extract(query, ydl_opts))

def _extract(query, ydl_opts):
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        return ydl.extract_info(query, download=False)


intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    test_guild = discord.Object(id=GUILD_ID)
    await bot.tree.sync(guild=test_guild)
    
    print(f"{bot.user} is online!")
    
@bot.event
async def on_message(msg):
    print(msg.guild.id)
#     if msg.author.id != bot.user.id:
#         await msg.channel.send(f"Interesting message, {msg.author.mention}")

# @bot.tree.command(name="greet", description="Sends a greeting to the user")
# async def greet(intereaction: discord.Interaction):
#     username = intereaction.user.mention
#     await intereaction.response.send_message(f"Hello there, {username}")

@bot.tree.command(name="play", description="Play a song or add it to the queue.")
@app_commands.describe(song_query="Search query")
async def play(interaction: discord.Interaction, song_query: str):
    await interaction.response.defer()
    
    voice_channel = interaction.user.voice.channel
    
    if voice_channel is None:
        await interaction.followup.send("You must be in a voice channel.")
        return
    
    voice_client = interaction.guild.voice_client
    
    if voice_client is None:
        voice_client = await voice_channel.connect()
    elif voice_channel != voice_client.channel:
        await voice_client.move_to(voice_channel)

    ydl_options = {
            "format": "bestaudio[abr<=96]/bestaudio",
            "noplaylist": True,
            "youtube_include_dash_manifest": False,
            "youtube_include_hls_manifest": False,
        }
    
    query = "ytsearch1: " + song_query
    results = await search_ytdlp_async(query, ydl_options)
    tracks = results.get("entries", [])
    
    if tracks is None:
        await interaction.followup.send("No results found.")
        return
    
    first_track = tracks[0]
    audio_url = first_track["url"]
    title = first_track.get("title", "Untitled")
    
    guild_id = str(interaction.guild.id)
    if SONG_QUEUES.get(guild_id) is None:
        SONG_QUEUES[guild_id] = deque()
    SONG_QUEUES[guild_id].append((audio_url, title))
    
    if voice_client.is_playing() or voice_client.is_paused():
        await interaction.followup.send(f"Added to queue: **{title}**")
    else:
        await interaction.followup.send(f"Now playing: **{title}**")
        await play_next_song(voice_client, guild_id, interaction.channel)
        
        
@bot.tree.command(name="skip", description="Skip the current playing song.")
async def skip(interaction: discord.Interaction):
    if interaction.guild.voice_client and (intereaction.guild.voice_client.is_playing() or interaction.guild.voice_client.is_paused()):
        interaction.guild.voice_client.stop()
        await interaction.response.send_message("Skipped the current song.")
    else:
        await interaction.response.send_message("Not playing anything to skip.")
        
@bot.tree.command(name="pause", description="Pause the current playing song.")
async def pause(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    
    if voice_client is None:
        return await interaction.response.send_message("Not connected to a voice channel.")
    
    if not voice_client.is_playing():
        return await interaction.response.send_message("Not playing anything to pause.")
    
    voice_client.pause()
    await interaction.response.send_message("Paused the current song.")
    
@bot.tree.command(name="resume", description="Resume the paused song.")
async def resume(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    
    if voice_client is None:
        return await interaction.response.send_message("Not connected to a voice channel.")
    
    if not voice_client.is_paused():
        return await interaction.response.send_message("Not paused, nothing to resume.")
    
    voice_client.resume()
    await interaction.response.send_message("Resumed the current song.")
    
@bot.tree.command(name="stop", description="Stop the current playing song and clear the queue.")
async def stop(interaction: discord.Interaction):
    voice_client = interaction.guild.voice_client
    
    if not voice_client or not voice_client.is_connected():
        return await interaction.response.send_message("Not connected to a voice channel.")
    
    guild_id_str = str(interaction.guild.id)
    if guild_id_str in SONG_QUEUES:
        SONG_QUEUES[guild_id_str].clear()
    
    if voice_client.is_playing() or voice_client.is_paused():
        voice_client.stop()
        
    await voice_client.disconnect()
    await interaction.response.send_message("Stopped playback and disconnected!")

async def play_next_song(voice_client, guild_id, channel):
    if SONG_QUEUES[guild_id]:
        audio_url, title = SONG_QUEUES[guild_id].popleft()
        ffmpeg_options = {
            "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            "options": "-vn -c:a libopus -b:a 96k"
        }
        
        source = discord.FFmpegOpusAudio(audio_url, **ffmpeg_options, executable="bin/ffmpeg/ffmpeg")
        
        def after_play(error):
            if error:
                print(f"Error playing audio: {error}")
            asyncio.run_coroutine_threadsafe(play_next_song(voice_client, guild_id, channel), bot.loop)
        
        voice_client.play(source, after=after_play)
        asyncio.create_task(channel.send(f"Now playing: **{title}**"))
    else:
        await voice_client.disconnect()
        SONG_QUEUES[guild_id] = deque()

    
bot.run(TOKEN)