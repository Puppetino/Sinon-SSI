import json
import discord
import asyncio
import logging
import os

# Basic logging setup
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    handlers=[
                        logging.StreamHandler()
                    ])

# Create a logger
logger = logging.getLogger(__name__)

# Define paths for logging
LOGGING_PATH = 'logging'
GUILDS_LOGGING_PATH = os.path.join(LOGGING_PATH, 'guilds')
GENERAL_LOGGING_PATH = os.path.join(LOGGING_PATH, 'general')

# Ensure directories exist
os.makedirs(GUILDS_LOGGING_PATH, exist_ok=True)
os.makedirs(GENERAL_LOGGING_PATH, exist_ok=True)

# Create general error logger
general_error_logger = logging.getLogger('general_errors')
general_error_handler = logging.FileHandler(os.path.join(GENERAL_LOGGING_PATH, 'general_errors.log'))
general_error_handler.setLevel(logging.ERROR)
general_error_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'))
general_error_logger.addHandler(general_error_handler)

# Guild loggers dictionary
guild_loggers = {}

def get_guild_logger(guild_id):
    if guild_id not in guild_loggers:
        guild_path = os.path.join(GUILDS_LOGGING_PATH, str(guild_id))
        os.makedirs(guild_path, exist_ok=True)
        
        guild_logger = logging.getLogger(f'guild_{guild_id}')
        guild_handler = logging.FileHandler(os.path.join(guild_path, f'guild_{guild_id}.log'))
        guild_handler.setLevel(logging.INFO)
        guild_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'))
        guild_logger.addHandler(guild_handler)
        guild_logger.propagate = False  # Prevent logs from being handled by the root logger
        guild_loggers[guild_id] = guild_logger
    return guild_loggers[guild_id]

def log_with_guild_info(guild_id, level, msg, *args, **kwargs):
    guild_logger = get_guild_logger(guild_id)
    if level == 'info':
        guild_logger.info(msg, *args, **kwargs)
    elif level == 'warning':
        guild_logger.warning(msg, *args, **kwargs)
    elif level == 'error':
        guild_logger.error(msg, *args, **kwargs)
        general_error_logger.error(msg, *args, **kwargs)
    elif level == 'critical':
        guild_logger.critical(msg, *args, **kwargs)
        general_error_logger.critical(msg, *args, **kwargs)
    else:
        guild_logger.debug(msg, *args, **kwargs)

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

                            # Wait after each successful purge
                            await asyncio.sleep(1)

                        except discord.HTTPException as e:
                            if e.status == 429:
                                retry_after = float(e.response.headers.get('Retry-After', 1))
                                log_with_guild_info(guild_id, 'warning', f"Rate limited: retrying after {retry_after} seconds")
                                await asyncio.sleep(retry_after)
                            else:
                                log_with_guild_info(guild_id, 'error', f"HTTP exception when deleting messages: {e}")
                                break

                    # Clear reported streams data for the guild
                    bot.reported_streams[guild_id] = {}
                except discord.Forbidden:
                    log_with_guild_info(guild_id, 'warning', f"Missing permissions to purge messages in channel: {channel.name}")
                except discord.HTTPException as e:
                    log_with_guild_info(guild_id, 'error', f"Failed to purge messages in channel: {channel.name} - {e}")
                except Exception as e:
                    log_with_guild_info(guild_id, 'error', f"An unexpected error occurred: {e}")
            else:
                log_with_guild_info(guild_id, 'warning', f"Channel with ID {channel_id} does not exist")
        else:
            log_with_guild_info(guild_id, 'warning', f"No channel_id found for guild ID {guild_id}")

# Delete guild data
def delete_guild_data(guild_id):
    settings = load_settings()
    
    if 'guilds' in settings and guild_id in settings['guilds']:
        del settings['guilds'][guild_id]
        log_with_guild_info(guild_id, 'info', f"Deleted data for guild ID: {guild_id}")
        save_settings(settings)
    else:
        log_with_guild_info(guild_id, 'info', f"No data found for guild ID: {guild_id}")