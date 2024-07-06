import os
import discord
import requests
from discord import Embed
from discord.ext import tasks

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
        self.reported_streams = {}  # Cache for reported streams

    async def on_ready(self):
        print(f'Logged in as {self.user}')
        self.channel = self.get_channel(CHANNEL_ID)
        check_streams.start()  # Start the task

    async def get_twitch_streams(self, category_name):
        try:
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
        except Exception as e:
            print(f"Error fetching streams: {e}")
            return {'data': []}

    async def get_user_info(self, user_id):
        try:
            url = f"https://api.twitch.tv/helix/users?id={user_id}"
            headers = {
                'Client-ID': TWITCH_CLIENT_ID,
                'Authorization': f'Bearer {TWITCH_ACCESS_TOKEN}'
            }
            response = requests.get(url, headers=headers).json()

            user_data = response.get('data', [])
            if user_data:
                user_info = user_data[0]
                followers_url = f"https://api.twitch.tv/helix/users/follows?to_id={user_id}&from_id={user_id}"
                followers_response = requests.get(followers_url, headers=headers).json()

                if followers_response.get('total', 0) > 0:
                    follower_count = followers_response['total']
                else:
                    follower_count = 0

                return {
                    'id': user_info.get('id'),
                    'name': user_info.get('display_name'),
                    'profile_image_url': user_info.get('profile_image_url'),
                    'description': user_info.get('description'),
                    'follower_count': follower_count
                }
            else:
                return {}
        except Exception as e:
            print(f"Error fetching user info: {e}")
            return {}

@tasks.loop(minutes=2.5)
async def check_streams():
    streams = await client.get_twitch_streams(CATEGORY_NAME)

    for stream_id, reported_stream in list(client.reported_streams.items()):
        if stream_id not in [stream['id'] for stream in streams['data']]:
            await reported_stream['message'].delete()
            del client.reported_streams[stream_id]

    for stream in streams['data']:
        stream_title = stream['title']
        stream_url = f"https://www.twitch.tv/{stream['user_name']}"
        stream_id = stream['id']
        user_id = stream['user_id']

        user_info = await client.get_user_info(user_id)
        follower_count = user_info.get('view_count', 0)
        description = user_info.get('description', '')

        if stream_id in client.reported_streams:
            message = client.reported_streams[stream_id]['message']

            if stream['type'] != 'live':
                await message.delete()
                del client.reported_streams[stream_id]
            else:
                embed = discord.Embed(
                    title=stream_title,
                    url=stream_url,
                    description=f"{stream['user_name']} is live streaming {CATEGORY_NAME} on Twitch.\n\n{description}",
                    color=discord.Color(0x9900ff)
                )
                embed.set_author(name=stream['user_name'], url=stream_url, icon_url=user_info.get('profile_image_url'))
                embed.add_field(name="Viewers", value=stream['viewer_count'])
                embed.add_field(name="Followers", value=user_info['follower_count'], inline=True)
                embed.set_thumbnail(url=stream['thumbnail_url'])
                embed.set_footer(text="Sinon - Made by Puppetino")

                await message.edit(embed=embed)
        else:
            embed = discord.Embed(
                title=stream_title,
                url=stream_url,
                description=f"{stream['user_name']} is live streaming {CATEGORY_NAME} on Twitch.\n\n{description}",
                color=discord.Color(0x9900ff)
            )
            embed.set_author(name=stream['user_name'], url=stream_url, icon_url=user_info.get('profile_image_url'))
            embed.add_field(name="Viewers", value=stream['viewer_count'])
            embed.add_field(name="Followers", value=user_info['follower_count'], inline=True)
            embed.set_thumbnail(url=stream['thumbnail_url'])
            embed.set_footer(text="Sinon - Made by Puppetino")

            message = await client.channel.send(embed=embed)
            client.reported_streams[stream_id] = {'message': message}


client = MyClient()
client.run(DISCORD_TOKEN)