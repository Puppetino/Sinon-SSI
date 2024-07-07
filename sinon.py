import os
import json
import discord
import requests
from discord import app_commands, Intents
from discord.ext import tasks

# Get environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
TWITCH_ACCESS_TOKEN = os.getenv('TWITCH_ACCESS_TOKEN')

# Initialize bot
intents = Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

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

@client.event
async def on_ready():
    await tree.sync()
    print(f'Logged in as {client.user}')
    load_settings()
    await delete_all_messages()
    for guild_id, guild_settings in settings.items():
        if guild_settings.get("channel_id") and guild_settings.get("category_name") and not check_streams.is_running():
            check_streams.start()

# Delete all messages in the report channel for all guilds
async def delete_all_messages():
    for guild_id, guild_settings in settings.items():
        channel_id = guild_settings.get('channel_id')
        if channel_id:
            channel = client.get_channel(channel_id)
            if channel:
                try:
                    await channel.purge()
                    reported_streams[guild_id] = {}
                except discord.Forbidden:
                    print(f"Missing permissions to purge messages in channel: {channel.name}")
                except discord.HTTPException as e:
                    print(f"Failed to purge messages in channel: {channel.name} - {e}")

# Helper functions
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

@tree.command(name="set_report_channel", description="Set the channel for stream updates")
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

@tree.command(name="set_twitch_category", description="Set the Twitch category to monitor")
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
    await interaction.response.send_message(embed=embed)
    if settings[guild_id].get('channel_id'):
        await check_streams_once(guild_id)
    if settings[guild_id].get('channel_id') and not check_streams.is_running():
        check_streams.start()

@tree.command(name="setup", description="Guide through setting up the bot")
async def setup_command(interaction: discord.Interaction):
    setup_text = discord.Embed(
        title="Setup Guide",
        description="To set the channel for stream updates, use the `/set_report_channel` command.\n"
                    "To set the Twitch category to monitor, use the `/set_twitch_category` command.",
        color=discord.Color(0x9900ff)
    )
    setup_text.set_footer(text="Sinon - Made by Puppetino")
    await interaction.response.send_message(embed=setup_text)

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
              "`/setup` - Guide through setting up the bot\n"
              "`/help` - List all commands\n"
              "`/about` - Information about the bot\n"
              "`/delete_all_messages` - Delete all messages in the report channel",
        inline=False)
    help_text.set_footer(text="Sinon - Made by Puppetino")
    await interaction.response.send_message(embed=help_text)

@tree.command(name="about", description="About the bot")
async def about_command(interaction: discord.Interaction):
    about_text = discord.Embed(
        title="About the bot",
        description="This bot was created by Puppetino to monitor Twitch streams.",
        color=discord.Color(0x9900ff)
    )
    about_text.set_footer(text="Sinon - Made by Puppetino")
    await interaction.response.send_message(embed=about_text)



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

            message = await channel.send(embed=embed)
            reported_streams[guild_id][stream_id]['message'] = message

client.run(DISCORD_TOKEN)
