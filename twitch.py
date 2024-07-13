import os
import discord
import asyncio
import aiohttp
from dotenv import load_dotenv
from utils import logger

# Load environment variables
load_dotenv()

# Access environment variables
TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
TWITCH_ACCESS_TOKEN = os.getenv('TWITCH_ACCESS_TOKEN')

# Twitch API helper functions
async def fetch_from_twitch(url, params=None):
    headers = {
        'Client-ID': TWITCH_CLIENT_ID,
        'Authorization': f'Bearer {TWITCH_ACCESS_TOKEN}'
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers, params=params) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            logger.error(f"HTTP error: {e}")
            return None

# Twitch API functions
async def get_game_id(category_name):
    url = "https://api.twitch.tv/helix/games"
    params = {'name': category_name}
    data = await fetch_from_twitch(url, params)
    if data and 'data' in data and data['data']:
        return data['data'][0]['id']
    return None

async def get_streams_by_game_id(game_id):
    url = "https://api.twitch.tv/helix/streams"
    params = {'game_id': game_id}
    data = await fetch_from_twitch(url, params)
    return data.get('data', []) if data else []

async def get_user_info(user_id):
    url = "https://api.twitch.tv/helix/users"
    params = {'id': user_id}
    data = await fetch_from_twitch(url, params)
    if data and 'data' in data and data['data']:
        user_info = data['data'][0]
        return {
            'id': user_info.get('id'),
            'name': user_info.get('display_name'),
            'profile_image_url': user_info.get('profile_image_url'),
            'description': user_info.get('description')
        }
    return {}

# Reports that no streams were found
async def report_no_streams(guild_id, bot, settings, category_name):
    guild_settings = settings.get('guilds', {}).get(guild_id)
    if not guild_settings:
        return

    channel_id = guild_settings.get('channel_id')
    if not channel_id:
        return

    channel = bot.get_channel(channel_id)
    if channel is None:
        logger.error(f"Channel with ID {channel_id} does not exist")
        return

    # Check if a no-streams message has already been sent
    if guild_id in bot.reported_streams and 'no_streams_message' in bot.reported_streams[guild_id]:
        return
    
    # Delete Embeds of previous streams
    for stream_id, reported_stream in bot.reported_streams[guild_id].items():
        if stream_id != 'no_streams_message':
            try:
                await reported_stream['message'].delete()
            except discord.errors.NotFound:
                pass

    embed = discord.Embed(
        title="No streams found",
        description=f"There are no streams currently live in the {category_name} category.",
        color=discord.Color(0x9900ff)
    )
    embed.set_footer(text="Sinon - Made by Puppetino")

    message = await channel.send(embed=embed)

    if guild_id not in bot.reported_streams:
        bot.reported_streams[guild_id] = {}
    bot.reported_streams[guild_id]['no_streams_message'] = message

# Send notification
async def send_notification(channel, embed):
    try:
        message = await channel.send(embed=embed)
        return message
    except discord.Forbidden:
        logger.error(f"Missing permissions to send message to channel: {channel.name}")
    except discord.HTTPException as e:
        if e.status == 429:
            retry_after = e.retry_after
            logger.error(f"Rate limited. Retrying after {retry_after} seconds.")
            await asyncio.sleep(retry_after)
            return await send_notification(channel, embed)  # Retry sending the message
        else:
            logger.error(f"Failed to send message to channel: {channel.name} - {e}")
    except Exception as e:
        logger.error(f"An error occurred: {e}")
    return None

# Create stream embed message
def create_stream_embed(stream, user_info, category_name, max_viewers=None):
    stream_title = stream['title']
    stream_url = f"https://www.twitch.tv/{stream['user_name']}"
    viewer_count = stream['viewer_count']
    description = user_info.get('description', '')

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
    if max_viewers is not None:
        embed.add_field(name="Max Viewers", value=str(max_viewers), inline=True)
    embed.set_thumbnail(url=stream['thumbnail_url'])
    embed.set_footer(text="Sinon - Made by Puppetino")

    return embed

# Update stream messages
async def update_stream_messages(bot, guild_id, channel, streams, category_name):
    current_stream_ids = {stream['id'] for stream in streams}
    
    # Clean up offline streams
    for stream_id, reported_stream in list(bot.reported_streams[guild_id].items()):
        if stream_id != 'no_streams_message' and stream_id not in current_stream_ids:
            try:
                await reported_stream['message'].delete()
            except discord.errors.NotFound:
                pass
            del bot.reported_streams[guild_id][stream_id]

    for stream in streams:
        stream_id = stream['id']
        user_id = stream['user_id']
        viewer_count = stream['viewer_count']

        user_info = await get_user_info(user_id)

        if stream_id in bot.reported_streams[guild_id]:
            message = bot.reported_streams[guild_id][stream_id]['message']
            max_viewers = bot.reported_streams[guild_id][stream_id]['max_viewers']
            if viewer_count > max_viewers:
                bot.reported_streams[guild_id][stream_id]['max_viewers'] = viewer_count

            embed = create_stream_embed(stream, user_info, category_name, max_viewers)
            try:
                await message.edit(embed=embed)
            except discord.errors.NotFound:
                pass
            except discord.errors.Forbidden as e:
                logger.error(f"Missing permissions to edit message: {e}")
        else:
            bot.reported_streams[guild_id][stream_id] = {
                'max_viewers': viewer_count
            }
            embed = create_stream_embed(stream, user_info, category_name, viewer_count)
            message = await send_notification(channel, embed)
            if message:
                bot.reported_streams[guild_id][stream_id]['message'] = message

# Check Twitch streams
async def check_twitch_streams(bot, settings, guild_id, category_name):
    guild_settings = settings.get('guilds', {}).get(guild_id)
    if not guild_settings:
        return

    channel_id = guild_settings.get('channel_id')
    if not channel_id or not category_name:
        return

    channel = bot.get_channel(channel_id)
    if channel is None:
        logger.error(f"Channel with ID {channel_id} does not exist")
        return

    game_id = await get_game_id(category_name)
    if not game_id:
        logger.error(f"Category with name {category_name} does not exist")
        await report_no_streams(guild_id, bot, settings, category_name)
        return

    streams = await get_streams_by_game_id(game_id)
    if not streams:
        await report_no_streams(guild_id, bot, settings, category_name)
        return

    # Clean up no-streams message if streams are found
    if guild_id in bot.reported_streams and 'no_streams_message' in bot.reported_streams[guild_id]:
        try:
            await bot.reported_streams[guild_id]['no_streams_message'].delete()
            del bot.reported_streams[guild_id]['no_streams_message']
        except discord.errors.NotFound:
            pass

    if guild_id not in bot.reported_streams:
        bot.reported_streams[guild_id] = {}

    await update_stream_messages(bot, guild_id, channel, streams, category_name)