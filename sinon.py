import asyncio
import discord
import requests
import os
import logging
from discord import Embed
from keep_alive import keep_alive

# Set up logging
logging.basicConfig(level=logging.INFO)

# Access environment variables using Heroku's environment management
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')
TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
TWITCH_ACCESS_TOKEN = os.getenv('TWITCH_ACCESS_TOKEN')
CATEGORY_NAME = 'BattleCore Arena

# Debug prints to verify environment variables (optional, for development)
logging.info(f'DISCORD_TOKEN: {DISCORD_TOKEN}')
logging.info(f'CHANNEL_ID: {CHANNEL_ID}')
logging.info(f'TWITCH_CLIENT_ID: {TWITCH_CLIENT_ID}')
logging.info(f'TWITCH_CLIENT_SECRET: {TWITCH_CLIENT_SECRET}')
logging.info(f'TWITCH_ACCESS_TOKEN: {TWITCH_ACCESS_TOKEN}')

# Convert CHANNEL_ID to an integer if it is not None
if CHANNEL_ID:
    CHANNEL_ID = int(CHANNEL_ID)
else:
    logging.error("CHANNEL_ID is not set.")
    exit(1)

# Create an Intents object and enable the necessary intents
intents = discord.Intents.default()
intents.messages = True

client = discord.Client(intents=intents)

# Dictionary to keep track of reported streams and their corresponding message IDs
reported_streams = {}

def get_twitch_streams(category_name):
    logging.info(f"Fetching streams for category: {category_name}")
    # Fetch the game ID for the category name
    game_url = f"https://api.twitch.tv/helix/games?name={category_name}"
    headers = {
        'Client-ID': TWITCH_CLIENT_ID,
        'Authorization': f'Bearer {TWITCH_ACCESS_TOKEN}'
    }
    game_response = requests.get(game_url, headers=headers).json()
    game_id = game_response['data'][0]['id']
    logging.info(f"Fetched game ID: {game_id}")

    # Fetch streams for the game ID
    url = f"https://api.twitch.tv/helix/streams?game_id={game_id}"
    response = requests.get(url, headers=headers)
    return response.json()

@client.event
async def on_ready():
    logging.info(f'Logged in as {client.user}')
    channel = client.get_channel(CHANNEL_ID)
    while True:
        try:
            current_streams = get_twitch_streams(CATEGORY_NAME)
            current_stream_ids = {stream['id'] for stream in current_streams['data']}
            
            # Identify streams that have gone offline
            offline_streams = set(reported_streams.keys()) - current_stream_ids
            
            # Delete messages for streams that have gone offline
            for stream_id in offline_streams:
                message_id = reported_streams.pop(stream_id)
                try:
                    msg = await channel.fetch_message(message_id)
                    await msg.delete()
                except discord.NotFound:
                    pass  # Message already deleted
            
            # Report new streams
            for stream in current_streams['data']:
                stream_id = stream['id']
                if stream_id not in reported_streams:
                    embed = discord.Embed(
                        title=f"{stream['user_name']} is live!",
                        description=f"{stream['title']}",
                        url=f"https://www.twitch.tv/{stream['user_name']}",
                        color=discord.Color.blue()
                    )
                    embed.set_thumbnail(url=stream['thumbnail_url'])
                    embed.add_field(name="Game", value=CATEGORY_NAME, inline=True)
                    embed.add_field(name="Viewers", value=stream['viewer_count'], inline=True)
                    embed.set_footer(text="Stream Notification Bot")
                    message = await channel.send(embed=embed)
                    reported_streams[stream_id] = message.id  # Track the message ID for the stream

            await asyncio.sleep(150)  # Wait for 2.5 minutes before checking again
        except Exception as e:
            logging.error(f"Error in on_ready loop: {e}")

# Keep the bot alive
keep_alive()

# Run the bot
try:
    client.run(DISCORD_TOKEN)
except Exception as e:
    logging.error(f"Error running the bot: {e}")