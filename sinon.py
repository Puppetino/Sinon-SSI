import os
import discord
import requests
from discord import Embed
from discord.ext import tasks

# Keep Alive Module
from keep_alive import keep_alive

# Get environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
TWITCH_ACCESS_TOKEN = os.getenv('TWITCH_ACCESS_TOKEN')
CATEGORY_NAME = 'BattleCore Arena'  # Your desired category

client = discord.Client(intents=discord.Intents.default())

# Function to get Twitch streams
def get_twitch_streams(category_name):
    game_url = f"https://api.twitch.tv/helix/games?name={category_name}"
    headers = {
        'Client-ID': TWITCH_CLIENT_ID,
        'Authorization': f'Bearer {TWITCH_ACCESS_TOKEN}'
    }
    game_response = requests.get(game_url, headers=headers).json()
    game_id = game_response['data'][0]['id']

    url = f"https://api.twitch.tv/helix/streams?game_id={game_id}"
    response = requests.get(url, headers=headers)
    return response.json()

@client.event
async def on_ready():
    print(f'Logged in as {client.user}')
    check_streams.start()

@tasks.loop(minutes=10)
async def check_streams():
    channel = client.get_channel(CHANNEL_ID)
    streams = get_twitch_streams(CATEGORY_NAME)
    for stream in streams['data']:
        embed = Embed(
            title=stream['title'],
            url=f"https://www.twitch.tv/{stream['user_name']}",
            description=f"{stream['user_name']} is live streaming {CATEGORY_NAME}",
            color=discord.Color.purple()
        )
        embed.set_author(name=stream['user_name'], url=f"https://www.twitch.tv/{stream['user_name']}")
        embed.add_field(name="Viewers", value=stream['viewer_count'])
        embed.set_thumbnail(url=stream['thumbnail_url'])
        await channel.send(embed=embed)

# Keep the bot alive
keep_alive()

client.run(DISCORD_TOKEN)