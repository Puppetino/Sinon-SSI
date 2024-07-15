import os
import discord
from discord.ext import tasks, commands
from dotenv import load_dotenv
from utils import load_settings, delete_all_messages, delete_guild_data, logger
from twitch import check_twitch_streams
from commands import setup_commands

# Load environment variables
load_dotenv()

# Get environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# Initialize bot
intents = discord.Intents.default()
intents.message_content = True  # Request the message content intent
bot = commands.Bot(command_prefix='/', intents=intents)

# Initialize reported_streams
bot.reported_streams = {}

# Load settings
settings = load_settings()

# Call the setup_commands function to define the tree variable
tree = bot.tree

# Define the periodic task
@tasks.loop(minutes=2.5)
async def check_streams():
    for guild_id, guild_settings in settings.get('guilds', {}).items():
        category_name = guild_settings.get('category_name')
        await check_twitch_streams(bot, settings, guild_id, category_name)

# Define on_ready
@bot.event
async def on_ready():
    await bot.tree.sync()
    settings = load_settings()  # Load settings from settings.json
    dev_mode = settings.get('dev_mode', False)  # Default to False if 'dev_mode' is not found or is False
    logger.info('Logged in as {0.user}'.format(bot))

    if dev_mode:
        await bot.change_presence(activity=discord.CustomActivity(name="!!! In Developer Mode !!!"))
    else:
        await bot.change_presence(activity=discord.CustomActivity(name="Stream Sniping on Twitch"))
    
    await delete_all_messages(bot, settings)  # Clear messages as needed
    
    for guild_id, guild_settings in settings.get('guilds', {}).items():
        channel_id = guild_settings.get('channel_id')
        category_name = guild_settings.get('category_name')
        
        if channel_id and category_name:
            # Start the periodic task if not already running
            if not check_streams.is_running():
                check_streams.start()
        else:
            if not channel_id:
                logger.error(f"Missing channel_id for guild ID {guild_id}")
            if not category_name:
                logger.error(f"Missing category_name for guild ID {guild_id}")

# Define on_guild_remove
@bot.event
async def on_guild_remove(guild):
    guild_id = str(guild.id)
    delete_guild_data(guild_id)
    logger.info(f"Bot was removed from guild: {guild.name} (ID: {guild_id})")

# Set up commands
setup_commands(bot, settings)

# Run the bot
bot.run(DISCORD_TOKEN)