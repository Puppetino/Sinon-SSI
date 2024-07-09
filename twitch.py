import os
import discord
import asyncio
import aiohttp
from dotenv import load_dotenv


load_dotenv()

# Access environment variables
TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
TWITCH_ACCESS_TOKEN = os.getenv('TWITCH_ACCESS_TOKEN')


async def get_twitch_streams(category_name):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.twitch.tv/helix/games?name={category_name}",
                                   headers={'Client-ID': TWITCH_CLIENT_ID,
                                            'Authorization': f'Bearer {TWITCH_ACCESS_TOKEN}'}) as game_response:
                game_data = await game_response.json()
                if 'data' in game_data and game_data['data']:
                    game_id = game_data['data'][0]['id']
                    async with session.get(f"https://api.twitch.tv/helix/streams?game_id={game_id}",
                                           headers={'Client-ID': TWITCH_CLIENT_ID,
                                                    'Authorization': f'Bearer {TWITCH_ACCESS_TOKEN}'}) as streams_response:
                        streams_data = await streams_response.json()
                        return streams_data
                else:
                    print(f"No game data found for category: {category_name}")
                    return {'data': []}
    except Exception as e:
        print(f"Error fetching streams for {category_name}: {e}")
        return {'data': []}

async def get_user_info(user_id):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"https://api.twitch.tv/helix/users?id={user_id}",
                                   headers={'Client-ID': TWITCH_CLIENT_ID,
                                            'Authorization': f'Bearer {TWITCH_ACCESS_TOKEN}'}) as user_response:
                user_data = await user_response.json()
                user_info = user_data.get('data', [])
                if user_info:
                    user_info = user_info[0]
                    return {
                        'id': user_info.get('id'),
                        'name': user_info.get('display_name'),
                        'profile_image_url': user_info.get('profile_image_url'),
                        'description': user_info.get('description')
                    }
                else:
                    return {}
    except Exception as e:
        print(f"Error fetching user info: {e}")
        return {}
    
async def send_notification(channel, embed):
    try:
        message = await channel.send(embed=embed)
        return message
    except discord.Forbidden:
        print(f"Missing permissions to send message to channel: {channel.name}")
    except discord.HTTPException as e:
        if e.status == 429:
            retry_after = e.retry_after
            print(f"Rate limited. Retrying after {retry_after} seconds.")
            await asyncio.sleep(retry_after)
            await send_notification(channel, embed)  # Retry sending the message
        else:
            print(f"Failed to send message to channel: {channel.name} - {e}")
    except Exception as e:
        print(f"An error occurred: {e}")
    return None


# Define the once-off check streams function
async def check_streams_once(bot, settings, guild_id, category_name):
    guild_settings = settings.get('guilds', {}).get(guild_id)
    if not guild_settings:
        return

    channel_id = guild_settings.get('channel_id')
    if not channel_id or not category_name:
        return

    channel = bot.get_channel(channel_id)
    if channel is None:
        print(f"Channel with ID {channel_id} does not exist")
        return

    streams = await get_twitch_streams(category_name)

    if not streams.get('data'):
        print(f"No streams found for category {category_name}")
        return

    if guild_id not in bot.reported_streams:
        bot.reported_streams[guild_id] = {}

    current_stream_ids = {stream['id'] for stream in streams['data']}

    for stream_id, reported_stream in list(bot.reported_streams[guild_id].items()):
        if stream_id not in current_stream_ids:
            try:
                await reported_stream['message'].delete()
            except discord.errors.NotFound:
                pass
            del bot.reported_streams[guild_id][stream_id]

    for stream in streams['data']:
        stream_title = stream['title']
        stream_url = f"https://www.twitch.tv/{stream['user_name']}"
        stream_id = stream['id']
        user_id = stream['user_id']
        viewer_count = stream['viewer_count']

        user_info = await get_user_info(user_id)
        description = user_info.get('description', '')

        if stream_id in bot.reported_streams[guild_id]:
            message = bot.reported_streams[guild_id][stream_id]['message']
            max_viewers = bot.reported_streams[guild_id][stream_id]['max_viewers']
            if viewer_count > max_viewers:
                bot.reported_streams[guild_id][stream_id]['max_viewers'] = viewer_count

            embed = discord.Embed(
                title=stream_title,
                url=stream_url,
                description=f"{stream['user_name']} is live streaming {category_name} on Twitch.\n\n{description}",
                color=discord.Color(0x9900ff)
            )
            embed.set_author(
                name=stream['user_name'],
                url=stream_url,
                icon_url=user_info.get('profile_image_url')
            )
            embed.add_field(name="Viewers", value=str(viewer_count), inline=True)
            embed.add_field(
                name="Max Viewers",
                value=str(bot.reported_streams[guild_id][stream_id]['max_viewers']),
                inline=True
            )
            embed.set_thumbnail(url=stream['thumbnail_url'])
            embed.set_footer(text="Sinon - Made by Puppetino")

            try:
                await message.edit(embed=embed)
            except discord.errors.NotFound:
                pass
            except discord.errors.Forbidden as e:
                print(f"Missing permissions to edit message in channel: {channel.name} - {e}")
        else:
            bot.reported_streams[guild_id][stream_id] = {
                'max_viewers': viewer_count
            }
            embed = discord.Embed(
                title=stream_title,
                url=stream_url,
                description=f"{stream['user_name']} is live streaming {category_name} on Twitch.\n\n{description}",
                color=discord.Color(0x9900ff)
            )
            embed.set_author(
                name=stream['user_name'],
                url=stream_url,
                icon_url=user_info.get('profile_image_url')
            )
            embed.add_field(name="Viewers", value=str(viewer_count), inline=True)
            embed.add_field(name="Max Viewers", value=str(viewer_count), inline=True)
            embed.set_thumbnail(url=stream['thumbnail_url'])
            embed.set_footer(text="Sinon - Made by Puppetino")

            message = await send_notification(channel, embed)
            if message:
                bot.reported_streams[guild_id][stream_id]['message'] = message
