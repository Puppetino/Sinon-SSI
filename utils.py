import json
import discord
import asyncio
import logging

# Basic logging setup
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    handlers=[
                        logging.FileHandler('bot.log'), 
                        logging.StreamHandler()
                        ])

# create a logger
logger = logging.getLogger(__name__)

# Load settings
def load_settings():
    try:
        with open('settings.json', 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {'dev_mode': False, 'guilds': {}}
    
# Save settings
def save_settings(settings):
    with open('settings.json', 'w') as f:
        json.dump(settings, f, indent=4)

# Check if user has allowed role
def has_allowed_role(interaction, settings):
    guild_id = str(interaction.guild_id)
    if interaction.user.guild_permissions.administrator:
        return True
    role_id = settings.get(guild_id, {}).get('allowed_role')
    if role_id:
        role = interaction.guild.get_role(role_id)
        return role in interaction.user.roles
    return False

# Purge all messages in a channel
async def delete_all_messages(bot, settings):
    for guild_id, guild_settings in settings.get('guilds', {}).items():
        channel_id = guild_settings.get('channel_id')
        if channel_id:
            channel = bot.get_channel(channel_id)
            if channel:
                try:
                    while True:
                        # Fetch messages authored by the bot, up to 100 at a time
                        messages = [msg async for msg in channel.history(limit=100) if msg.author == bot.user]

                        if not messages:
                            # No more messages to delete
                            break

                        try:
                            # Attempt to bulk delete messages
                            await channel.purge(limit=100, check=lambda m: m.author == bot.user)
                            logger.info(f"Deleted {len(messages)} messages in channel: {channel.name}")

                            # Wait after each successful purge
                            await asyncio.sleep(1)

                        except discord.HTTPException as e:
                            if e.status == 429:
                                retry_after = float(e.response.headers.get('Retry-After', 1))
                                logger.warning(f"Rate limited: retrying after {retry_after} seconds")
                                await asyncio.sleep(retry_after)
                            else:
                                logger.error(f"HTTP exception when deleting messages: {e}")
                                break

                    # Clear reported streams data for the guild
                    bot.reported_streams[guild_id] = {}
                except discord.Forbidden:
                    logger.warning(f"Missing permissions to purge messages in channel: {channel.name}")
                except discord.HTTPException as e:
                    logger.error(f"Failed to purge messages in channel: {channel.name} - {e}")
                except Exception as e:
                    logger.error(f"An unexpected error occurred: {e}")
            else:
                logger.warning(f"Channel with ID {channel_id} does not exist")
        else:
            logger.warning(f"No channel_id found for guild ID {guild_id}")

# Delete guild data
def delete_guild_data(guild_id):
    settings = load_settings()
    
    if 'guilds' in settings and guild_id in settings['guilds']:
        del settings['guilds'][guild_id]
        print(f"Deleted data for guild ID: {guild_id}")
        save_settings(settings)
    else:
        print(f"No data found for guild ID: {guild_id}")