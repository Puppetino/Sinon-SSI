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

# Global dictionary to track reported categories and streams for each guild
reported_categories = {}
reported_streams = {}

# Twitch API helper functions
async def fetch_from_twitch(url, params=None, retries=3, backoff_factor=1):
    headers = {
        'Client-ID': TWITCH_CLIENT_ID,
        'Authorization': f'Bearer {TWITCH_ACCESS_TOKEN}'
    }
    async with aiohttp.ClientSession() as session:
        for attempt in range(retries):
            try:
                async with session.get(url, headers=headers, params=params) as response:
                    response.raise_for_status()
                    data = await response.json()
                    logger.info(f"Fetched data from Twitch: {data}")
                    return data
            except aiohttp.ClientError as e:
                logger.error(f"HTTP error while fetching Twitch data: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(backoff_factor * (2 ** attempt))  # Exponential backoff
            except Exception as e:
                logger.error(f"An unexpected error occurred: {e}")
                if attempt < retries - 1:
                    await asyncio.sleep(backoff_factor * (2 ** attempt))
    return None

# Twitch API functions
async def get_game_id(category_name):
    url = "https://api.twitch.tv/helix/games"
    params = {'name': category_name}
    data = await fetch_from_twitch(url, params)
    if data is None:
        logger.error(f"Failed to fetch game ID for category: {category_name} due to connection issues.")
        return None
    if 'data' in data and data['data']:
        game_id = data['data'][0]['id']
        logger.info(f"Game ID for category '{category_name}': {game_id}")
        return game_id
    logger.warning(f"Game ID not found for category: {category_name}")
    return None

async def get_streams_by_game_id(game_id):
    url = "https://api.twitch.tv/helix/streams"
    params = {'game_id': game_id}
    data = await fetch_from_twitch(url, params)
    if data:
        logger.info(f"Streams for game ID {game_id}: {data.get('data', [])}")
        return data.get('data', [])
    return []

async def get_user_info(user_id):
    url = "https://api.twitch.tv/helix/users"
    params = {'id': user_id}
    data = await fetch_from_twitch(url, params)
    if data and 'data' in data and data['data']:
        user_info = data['data'][0]
        logger.info(f"User info for user ID '{user_id}': {user_info}")
        return {
            'id': user_info.get('id'),
            'name': user_info.get('display_name'),
            'profile_image_url': user_info.get('profile_image_url'),
            'description': user_info.get('description')
        }
    logger.warning(f"User info not found for user ID: {user_id}")
    return {}

# Notify when a category does not exist
async def report_non_existent_category(channel, category_name):
    embed = discord.Embed(
        title="Category Not Found",
        description=f"The category '{category_name}' does not exist on Twitch. Please check the name and try again. Make sure you are using the correct category name, twitch category names are case-sensitive.",
        color=discord.Color(0x9900ff)
    )
    embed.set_footer(text="Sinon - Made by Puppetino")
    try:
        await channel.send(embed=embed)
        logger.info(f"Sent 'Category Not Found' message to channel: {channel.id}")
    except discord.errors.Forbidden:
        logger.error(f"Missing permissions to send message to channel: {channel.id}")
    except discord.errors.HTTPException as e:
        logger.error(f"Failed to send message to channel: {channel.id} - {e}")

# Reports that no streams were found
async def report_no_streams(guild_id, bot, settings, category_name):
    guild_settings = settings.get('guilds', {}).get(guild_id)
    if not guild_settings:
        logger.warning(f"No settings found for guild ID: {guild_id}")
        return

    channel_id = guild_settings.get('channel_id')
    if not channel_id:
        logger.warning(f"No channel ID found in settings for guild ID: {guild_id}")
        return

    channel = bot.get_channel(channel_id)
    if channel is None:
        logger.error(f"Channel with ID {channel_id} does not exist")
        return

    # Check if a no-streams message has already been sent
    if guild_id in reported_streams and 'no_streams_message' in reported_streams[guild_id]:
        logger.info(f"No-streams message already sent for guild ID: {guild_id}")
        return
    
    # Delete Embeds of previous streams
    for stream_id, reported_stream in list(reported_streams[guild_id].items()):
        if stream_id != 'no_streams_message':
            try:
                await reported_stream['message'].delete()
                logger.info(f"Deleted message for stream {stream_id} in guild ID {guild_id}")
            except discord.errors.NotFound:
                logger.warning(f"Stream message for {stream_id} not found for deletion in guild ID {guild_id}")
            except discord.errors.Forbidden as e:
                logger.error(f"Missing permissions to delete message for stream {stream_id}: {e}")

    embed = discord.Embed(
        title="No streams found",
        description=f"There are no streams currently live in the {category_name} category.",
        color=discord.Color(0x9900ff)
    )
    embed.set_footer(text="Sinon - Made by Puppetino")

    try:
        message = await channel.send(embed=embed)
        logger.info(f"Sent 'No streams found' message to channel: {channel.id}")
    except discord.errors.Forbidden:
        logger.error(f"Missing permissions to send 'No streams found' message to channel: {channel.id}")
        return
    except discord.errors.HTTPException as e:
        logger.error(f"Failed to send 'No streams found' message to channel: {channel.id} - {e}")
        return

    if guild_id not in reported_streams:
        reported_streams[guild_id] = {}
    reported_streams[guild_id]['no_streams_message'] = message

# Send notification
async def send_notification(channel, embed):
    try:
        message = await channel.send(embed=embed)
        logger.info(f"Message sent to channel: {channel.name}")
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
async def create_stream_embed(stream, user_info, category_name, max_viewers=None):
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

    # Clean up offline streams only if the current API call confirms they are offline
    for stream_id, reported_stream in list(reported_streams[guild_id].items()):
        if stream_id != 'no_streams_message' and stream_id not in current_stream_ids:
            try:
                await reported_stream['message'].delete()
                logger.info(f"Deleted message for stream {stream_id} in channel {channel.id}")
            except discord.errors.NotFound:
                logger.warning(f"Message for stream {stream_id} not found for deletion in channel {channel.id}")
            except discord.errors.Forbidden as e:
                logger.error(f"Missing permissions to delete message for stream {stream_id}: {e}")
            del reported_streams[guild_id][stream_id]

    for stream in streams:
        stream_id = stream['id']
        user_id = stream['user_id']
        viewer_count = stream['viewer_count']

        user_info = await get_user_info(user_id)

        if stream_id in reported_streams[guild_id]:
            # Get the current message and max viewers
            message = reported_streams[guild_id][stream_id]['message']
            max_viewers = reported_streams[guild_id][stream_id]['max_viewers']
            
            # Update the max viewers if the current count is greater
            if viewer_count > max_viewers:
                max_viewers = viewer_count
                reported_streams[guild_id][stream_id]['max_viewers'] = max_viewers

            # Create a new embed with the updated viewer counts
            embed = await create_stream_embed(stream, user_info, category_name, max_viewers)
            try:
                await message.edit(embed=embed)
                logger.info(f"Updated message for stream {stream_id} in channel {channel.id}")
            except discord.errors.NotFound:
                logger.warning(f"Message for stream {stream_id} not found for editing in channel {channel.id}")
            except discord.errors.Forbidden as e:
                logger.error(f"Missing permissions to edit message for stream {stream_id}: {e}")
        else:
            # Create new entry for the stream
            reported_streams[guild_id][stream_id] = {
                'max_viewers': viewer_count
            }
            embed = await create_stream_embed(stream, user_info, category_name, viewer_count)
            message = await send_notification(channel, embed)
            if message:
                reported_streams[guild_id][stream_id]['message'] = message
                logger.info(f"Sent new message for stream {stream_id} in channel {channel.id}")

# Check Twitch streams
async def check_twitch_streams(bot, settings, guild_id, category_name):
    # Helper function to safely get nested dictionary values
    def get_nested(d, keys, default=None):
        for key in keys:
            d = d.get(key, {})
            if not d:
                return default
        return d

    # Retrieve guild settings safely
    guild_settings = get_nested(settings, ['guilds', guild_id])
    if not guild_settings:
        logger.warning(f"No settings found for guild ID: {guild_id}")
        return

    channel_id = guild_settings.get('channel_id')
    if not channel_id or not category_name:
        logger.warning(f"Channel ID or category name missing for guild ID: {guild_id}")
        return

    # Check if bot can access the channel
    channel = bot.get_channel(channel_id)
    if channel is None:
        logger.error(f"Channel with ID {channel_id} does not exist")
        return

    # Initialize reported categories for the guild if not present
    if guild_id not in reported_categories:
        reported_categories[guild_id] = set()

    # Initialize reported streams for the guild if not present
    if guild_id not in reported_streams:
        reported_streams[guild_id] = {}

    try:
        # Fetch game ID specific to the guild
        game_id = await get_game_id(category_name)
        if not game_id:
            # Check if we've already reported this category as non-existent
            if category_name not in reported_categories[guild_id]:
                await report_non_existent_category(channel, category_name)
                reported_categories[guild_id].add(category_name)
            logger.error(f"Category with name {category_name} does not exist")
            return

        # If the category is valid, remove it from the reported categories set
        reported_categories[guild_id].discard(category_name)

        # Fetch streams specific to the game ID
        streams = await get_streams_by_game_id(game_id)
        
        if streams:
            # Reset no-streams message state if streams are found
            no_streams_message = reported_streams[guild_id].get('no_streams_message')
            if no_streams_message:
                try:
                    await no_streams_message.delete()
                    del reported_streams[guild_id]['no_streams_message']
                    logger.info(f"Deleted 'No streams' message for guild ID: {guild_id}")
                except discord.errors.NotFound:
                    logger.warning(f"No streams message not found for deletion in guild ID: {guild_id}")
            # Update stream messages
            await update_stream_messages(bot, guild_id, channel, streams, category_name)
        else:
            # Log that no streams were found
            logger.info(f"No streams found in category {category_name} for guild ID: {guild_id}")
            # Ensure all messages for streams are deleted
            for stream_id, reported_stream in list(reported_streams[guild_id].items()):
                if stream_id != 'no_streams_message':
                    try:
                        await reported_stream['message'].delete()
                        logger.info(f"Deleted message for stream {stream_id} in guild ID {guild_id}")
                    except discord.errors.NotFound:
                        logger.warning(f"Stream message for {stream_id} not found for deletion in guild ID {guild_id}")
                    except discord.errors.Forbidden as e:
                        logger.error(f"Missing permissions to delete message for stream {stream_id}: {e}")
                    del reported_streams[guild_id][stream_id]
            # Only send the no-streams message if it's confirmed that no streams are live
            if not any(s for s in reported_streams[guild_id] if s != 'no_streams_message'):
                logger.info(f"Sending 'No streams' message for guild ID: {guild_id}")
                await report_no_streams(guild_id, bot, settings, category_name)
    except Exception as e:
        logger.error(f"Error fetching data from Twitch for guild {guild_id}: {str(e)}")
        return