import os
import json
import discord
import requests
import subprocess
import asyncio
from discord.ext import tasks
from discord import app_commands, Intents
from dotenv import load_dotenv


# List of required packages
required_packages = ['discord.py', 'requests', 'python-dotenv']


# Function to check if a package is installed
def is_package_installed(package_name):
    result = subprocess.run(['pip', 'show', package_name], capture_output=True, text=True)
    return result.returncode == 0


# Install required packages using pip if not already installed
for package in required_packages:
    if not is_package_installed(package):
        print(f"Installing {package}...")
        subprocess.run(['pip', 'install', package])
    else:
        print(f"{package} is already installed.")

print("All required packages are installed.")


# Load environment variables from .env file
load_dotenv()


# Get environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
TWITCH_ACCESS_TOKEN = os.getenv('TWITCH_ACCESS_TOKEN')


# Initialize bot
intents = Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)
client.tree = tree


# Global variables to store settings and reported streams
settings_file = "settings.json"
settings = {}
reported_streams = {}


# Load settings from file
def load_settings():
    global settings
    if os.path.exists(settings_file) and os.path.getsize(settings_file) > 0:
        with open(settings_file, "r") as f:
            try:
                settings = json.load(f)
            except json.JSONDecodeError:
                settings = {}
    else:
        settings = {}


# Save settings to file
def save_settings():
    with open(settings_file, "w") as f:
        json.dump(settings, f)


# Event handler for when the bot is ready
@client.event
async def on_ready():
    await tree.sync()
    print(f'Logged in as {client.user}')
    load_settings()
    await delete_all_messages()
    for guild_id, guild_settings in settings.items():
        if guild_settings.get("channel_id") and guild_settings.get("category_name") and not check_streams.is_running():
            check_streams.start()
    
    # Set custom status
    #await client.change_presence(activity=discord.CustomActivity(name="Stream Sniping on Twitch"))

    # Dev status
    await client.change_presence(activity=discord.CustomActivity(name="In Dev Mode")) 


# Helper function to check if the user has the allowed role
def has_allowed_role(interaction, allowed_role_name=None):
    guild_id = str(interaction.guild_id)
    if allowed_role_name:
        user_roles = [role.name for role in interaction.user.roles]
        return allowed_role_name in user_roles
    else:
        if interaction.user.guild_permissions.administrator:
            return True
        allowed_roles = settings.get(guild_id, {}).get('allowed_roles', [])
        user_roles = [role.id for role in interaction.user.roles]
        return any(role in allowed_roles for role in user_roles)


# Decorator to check if the user has the allowed role
def has_allowed_role():
    async def predicate(interaction: discord.Interaction):
        guild_id = str(interaction.guild_id)
        role_id = settings.get(guild_id, {}).get('allowed_role')
        if role_id:
            role = interaction.guild.get_role(role_id)
            if role in interaction.user.roles or interaction.user.guild_permissions.administrator:
                return True
        else:
            if interaction.user.guild_permissions.administrator:
                return True
        return False
    return app_commands.check(predicate)


# Delete all messages sent by the bot in the report channel for all guilds
async def delete_all_messages():
    for guild_id, guild_settings in settings.items():
        channel_id = guild_settings.get('channel_id')
        if channel_id:
            channel = client.get_channel(channel_id)
            if channel:
                try:
                    async for message in channel.history(limit=None):
                        if message.author == client.user:
                            await message.delete()
                    reported_streams[guild_id] = {}
                except discord.Forbidden:
                    print(f"Missing permissions to purge messages in channel: {channel.name}")
                except discord.HTTPException as e:
                    print(f"Failed to purge messages in channel: {channel.name} - {e}")


# Helper functions to get Twitch streams
async def get_twitch_streams(category_name):
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


# Helper function to get user info
async def get_user_info(user_id):
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
    

# Command to set allowed role
@tree.command(name="set_allowed_role", description="Set roles allowed to use bot commands")
@has_allowed_role()
async def set_allowed_role(interaction: discord.Interaction, role: discord.Role):
    guild_id = str(interaction.guild_id)
    if guild_id not in settings:
        settings[guild_id] = {}
    settings[guild_id]['allowed_role'] = role.id
    save_settings()
    embed = discord.Embed(
        title="Allowed role set",
        description=f"The role {role.mention} is now allowed to use certain bot commands.",
        color=discord.Color(0x9900ff)
    )
    embed.set_footer(text="Sinon - Made by Puppetino")
    await interaction.response.send_message(embed=embed)


# Command to set report channel
@tree.command(name="set_report_channel", description="Set the channel for stream updates")
@has_allowed_role()
async def set_report_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    guild_id = str(interaction.guild_id)
    if guild_id not in settings:
        settings[guild_id] = {}
    settings[guild_id]['channel_id'] = channel.id
    save_settings()
    embed = discord.Embed(
        title="Stream updates will be posted in",
        description=channel.mention,
        color=discord.Color(0x9900ff)
    )
    embed.set_footer(text="Sinon - Made by Puppetino")
    await interaction.response.send_message(embed=embed)
    if settings[guild_id].get('category_name'):
        await check_streams_once(guild_id)
    if settings[guild_id].get('category_name') and not check_streams.is_running():
        check_streams.start()


# Command to set Twitch category
@tree.command(name="set_twitch_category", description="Set the Twitch category to monitor")
@has_allowed_role()
async def set_twitch_category(interaction: discord.Interaction, category: str):
    guild_id = str(interaction.guild_id)
    if guild_id not in settings:
        settings[guild_id] = {}
    settings[guild_id]['category_name'] = category
    save_settings()
    embed = discord.Embed(
        title="Twitch category set to",
        description=category,
        color=discord.Color(0x9900ff)
    )
    embed.set_footer(text="Sinon - Made by Puppetino")
    
    try:
        await interaction.response.send_message(embed=embed)
    except discord.errors.NotFound as e:
        print(f"Ignoring NotFound error: {e}")

    if settings[guild_id].get('channel_id'):
        await check_streams_once(guild_id)
    if settings[guild_id].get('channel_id') and not check_streams.is_running():
        check_streams.start()


# Setup command
@tree.command(name="setup", description="Guide through setting up the bot")
@has_allowed_role()
async def setup_command(interaction: discord.Interaction, channel: str, category: str):
    guild_id = str(interaction.guild_id)
    if guild_id not in settings:
        settings[guild_id] = {}

    channel_id = int(''.join(filter(str.isdigit, channel)))
    settings[guild_id]['channel_id'] = channel_id
    settings[guild_id]['category_name'] = category
    save_settings()
    embed = discord.Embed(
        title="Setup Complete",
        description=f"Sinon will now report streams in {channel} and monitor any updates in the {category} category.\n"
                    f"Enjoy!",
        color=discord.Color(0x9900ff)
    )
    embed.set_footer(text="Sinon - Made by Puppetino")
    await interaction.response.send_message(embed=embed)


# Command to list all commands
@tree.command(name="help", description="List all commands")
async def help_command(interaction: discord.Interaction):
    help_text = discord.Embed(
        title="Available Commands",
        description="",
        color=discord.Color(0x9900ff)
    )
    help_text.add_field(
        name="List of available commands:",
        value="`/set_report_channel` - Set the channel for stream updates\n"
              "`/set_twitch_category` - Set the Twitch category to monitor\n"
              "`/set_allowed_role` - Set roles allowed to use bot commands\n"
              "`/setup` - Guide through setting up the bot\n"
              "`/help` - List all commands\n"
              "`/about` - Information about the bot\n",
        inline=False)
    help_text.set_footer(text="Sinon - Made by Puppetino")
    await interaction.response.send_message(embed=help_text)


# Command to get information about the bot
@tree.command(name="about", description="About the bot")
async def about_command(interaction: discord.Interaction):
    about_text = discord.Embed(
        title="About Sinon Bot",
        description=(
            "Welcome to Sinon, your dedicated Twitch stream monitor bot! 🎮\n\n"
            "Sinon was created with the purpose of helping communities stay updated with the latest streams "
            "in their favorite categories on Twitch. Whether you're a streamer, viewer, or community manager, "
            "Sinon offers a seamless way to keep your Discord server informed about ongoing live streams.\n\n"
            "Features include:\n"
            "• Real-time updates on Twitch streams\n"
            "• Customizable report channels\n"
            "• Specific Twitch category monitoring\n"
            "• User-friendly setup commands\n\n"
            "To get started, use the `/setup` command to configure the bot for your server. "
            "Need help? Use the `/help` command to see a list of all available commands and their descriptions.\n\n"
            "Created by Puppetino, Sinon is here to ensure you never miss a live stream again. Happy streaming! 🚀"
        ),
        color=discord.Color(0x9900ff)
    )
    about_text.set_footer(text="Sinon - Made by Puppetino")
    await interaction.response.send_message(embed=about_text)


# Check for new streams every 2.5 minutes
@tasks.loop(minutes=2.5)
async def check_streams():
    for guild_id, guild_settings in settings.items():
        await check_streams_once(guild_id)

async def check_streams_once(guild_id):
    guild_settings = settings.get(guild_id)
    if not guild_settings:
        return

    channel_id = guild_settings.get('channel_id')
    category_name = guild_settings.get('category_name')
    if not channel_id or not category_name:
        return

    channel = client.get_channel(channel_id)
    if channel is None:
        print(f"Channel with ID {channel_id} does not exist")
        return
    
    streams = await get_twitch_streams(category_name)

    if guild_id not in reported_streams:
        reported_streams[guild_id] = {}

    current_stream_ids = [stream['id'] for stream in streams['data']]

    for stream_id, reported_stream in list(reported_streams[guild_id].items()):
        if stream_id not in current_stream_ids:
            try:
                await reported_stream['message'].delete()
            except discord.errors.NotFound:
                pass
            del reported_streams[guild_id][stream_id]

    for stream in streams['data']:
        stream_title = stream['title']
        stream_url = f"https://www.twitch.tv/{stream['user_name']}"
        stream_id = stream['id']
        user_id = stream['user_id']
        viewer_count = stream['viewer_count']

        user_info = await get_user_info(user_id)
        description = user_info.get('description', '')

        if stream_id in reported_streams[guild_id]:
            message = reported_streams[guild_id][stream_id]['message']
            max_viewers = reported_streams[guild_id][stream_id]['max_viewers']
            if viewer_count > max_viewers:
                reported_streams[guild_id][stream_id]['max_viewers'] = viewer_count

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
                value=str(reported_streams[guild_id][stream_id]['max_viewers']),
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
            reported_streams[guild_id][stream_id] = {
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
            embed.add_field(name="Viewers", value=viewer_count, inline=True)
            embed.add_field(name="Max Viewers", value=viewer_count, inline=True)
            embed.set_thumbnail(url=stream['thumbnail_url'])
            embed.set_footer(text="Sinon - Made by Puppetino")

            try:
                message = await channel.send(embed=embed)
                reported_streams[guild_id][stream_id]['message'] = message
            except discord.errors.Forbidden as e:
                print(f"Missing permissions to send message in channel: {channel.name} - {e}")


client.run(DISCORD_TOKEN)
