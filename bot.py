import os
import discord
from discord.ext import tasks, commands
from dotenv import load_dotenv
from commands import setup_commands
from utils import load_settings, delete_all_messages, save_settings
from twitch import check_streams_once

load_dotenv()

# Get environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# Initialize bot
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='/', intents=intents)


# Initialize reported_streams
bot.reported_streams = {}

# Load settings
settings = load_settings()

@bot.event
async def on_ready():
    global dev_mode
    settings = load_settings()  # Load settings from settings.json
    dev_mode = settings.get('dev_mode', False)  # Default to False if 'dev_mode' is not found or is False
    print('Logged in as {0.user}'.format(bot))

    if dev_mode:
        await bot.change_presence(activity=discord.CustomActivity(name="In Developer Mode"))
    
    await delete_all_messages(bot, settings)  # Clear messages as needed
    
    for guild_id, guild_settings in settings.get('guilds', {}).items():
        channel_id = guild_settings.get('channel_id')
        category_name = guild_settings.get('category_name')
        
        if channel_id and category_name:
            await check_streams.start()  # Start the periodic task
        else:
            if not channel_id:
                print(f"Missing channel_id for guild ID {guild_id}")
            if not category_name:
                print(f"Missing category_name for guild ID {guild_id}")

    await bot.change_presence(activity=discord.CustomActivity(name="Stream Sniping on Twitch"))


# Define the periodic task
@tasks.loop(minutes=2.5)
async def check_streams():
    for guild_id, guild_settings in settings.get('guilds', {}).items():
        category_name = guild_settings.get('category_name')
        await check_streams_once(bot, settings, guild_id, category_name)


# Set up commands
setup_commands(bot, settings)

# Run bot
bot.run(DISCORD_TOKEN)