import os
import discord
import requests
from discord import Embed
from discord.ext import tasks  # Import the tasks module

# Get environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))
TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
TWITCH_ACCESS_TOKEN = os.getenv('TWITCH_ACCESS_TOKEN')
CATEGORY_NAME = 'BattleCore Arena'  # Your desired category


class MyClient(discord.Client):

    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.channel = None

    async def on_ready(self):
        print(f'Logged in as {self.user}')
        self.channel = self.get_channel(CHANNEL_ID)
        check_streams.start()  # Start the task

    async def get_twitch_streams(self, category_name):
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


@tasks.loop(minutes=2.5)
async def check_streams():
    channel = client.get_channel(CHANNEL_ID)
    streams = await client.get_twitch_streams(CATEGORY_NAME)

    # Check if each stream is already reported
    for stream in streams['data']:
        stream_title = stream['title']
        stream_url = f"https://www.twitch.tv/{stream['user_name']}"

        # Check if the stream is already reported
        already_reported = False
        async for message in channel.history(limit=100):
            if message.embeds and message.embeds[
                    0].title == stream_title and message.embeds[
                        0].url == stream_url:
                already_reported = True
                break

        if already_reported:
            # Update the viewer count for the already reported stream
            embed = discord.Embed(
                title=stream_title,
                url=stream_url,
                description=
                f"{stream['user_name']} is live streaming {CATEGORY_NAME}",
                color=discord.Color(0x9900ff))
            embed.set_author(name=stream['user_name'], url=stream_url)
            embed.add_field(name="Viewers", value=stream['viewer_count'])
            embed.set_thumbnail(url=stream['thumbnail_url'])
            embed.set_footer(text="Sinon - Made by Puppetino")

            # Find the message with the already reported stream
            async for message in channel.history(limit=100):
                if message.embeds and message.embeds[
                        0].title == stream_title and message.embeds[
                            0].url == stream_url:
                    await message.edit(embed=embed)
                    break
        else:
            # Report the new stream
            embed = discord.Embed(
                title=stream_title,
                url=stream_url,
                description=
                f"{stream['user_name']} is live streaming {CATEGORY_NAME}",
                color=discord.Color(0x9900ff))
            embed.set_author(name=stream['user_name'], url=stream_url)
            embed.add_field(name="Viewers", value=stream['viewer_count'])
            embed.set_thumbnail(url=stream['thumbnail_url'])
            embed.set_footer(text="Sinon - Made by Puppetino")
            await channel.send(embed=embed)


client = MyClient()
client.run(DISCORD_TOKEN)