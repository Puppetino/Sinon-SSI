import os
import discord
import json
import aiohttp
import asyncio
import traceback
import random
from pathlib import Path
from discord.ext import tasks
from discord import app_commands
from dotenv import load_dotenv
from datetime import datetime, timezone
from discord.ext.commands import has_permissions, MissingPermissions

# Load environment variables
load_dotenv()

# Get environment variables
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')

# Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = discord.Client(intents=intents)
tree = app_commands.CommandTree(bot)

# Twitch API Configuration
TWITCH_CLIENT_ID = os.getenv('TWITCH_CLIENT_ID')
TWITCH_CLIENT_SECRET = os.getenv('TWITCH_CLIENT_SECRET')
CATEGORY_NAME = "BattleCore Arena"

# Bools / Ints & Floats / Lists / Strings
twitch_access_token = None
game_id = None
is_disconnected = False
disconnection_time = None

stream_messages_per_guild = {}
stream_quotes = {}
no_stream_message = {}
stream_messages = {}
max_viewers = {}

# Owner ID and authorized user ID's
OWNER_ID = 487588371443613698
authorized_users = [OWNER_ID]

# Data paths for JSON files
DATE_DIR = Path("data")
channel_settings_file = DATE_DIR / "channel_settings.json"
role_permissions_file = DATE_DIR / "role_permissions.json"
targets = DATE_DIR / "targets.json"
stats_file = DATE_DIR / "stats.json"

# Initialize stats dictionary
stats = {
    "streams_checked": 0,
    "messages_sent": 0,
    "active_streams": 0,
    "guilds_tracked": 0,
}

# List of developers
developers = {
    "syalen": {"url": "https://www.twitch.tv/syalen", "display_name": "Syalen"},                                # Syalen
    "voctolm": {"url": "https://www.twitch.tv/voctolm", "display_name": "Voctolm"},                             # Voctolm/Reop
    "dumbeldor": {"url": "https://www.twitch.tv/dumbeldor", "display_name": "Dumbeldor"},                       # Dumbeldor
    "enkeliix": {"url": "https://www.twitch.tv/enkeliix", "display_name": "Enkelix"},                           # Enkelix
    "lagger90": {"url": "https://www.twitch.tv/lagger90", "display_name": "Lagger90"},                          # Lagger90
    "krose_officiel": {"url": "https://www.twitch.tv/krose_officiel", "display_name": "Kross"},                 # Kross
    "hartsss": {"url": "https://www.twitch.tv/hartsss", "display_name": "Hartsss"},                             # HartRs
    "rapickt2": {"url": "https://www.twitch.tv/rapickt2", "display_name": "CptMug (Rapickt2)"},                 # CptMug/Rapickt2
    "ohmygodie": {"url": "https://www.twitch.tv/ohmygodie", "display_name": "OhMyGodie"},                       # OhMyGodie
    "dilystv": {"url": "https://www.twitch.tv/dilystv", "display_name": "Dilys (Maëlle)"},                      # Dilys/Mälle
    "UbisoftBordeaux": {"url": "https://www.twitch.tv/ubisoftbordeaux", "display_name": "Ubisoft Bordeaux"},    # Ubisoft Bordeaux
    "Ubisoft": {"url": "https://www.twitch.tv/ubisoft", "display_name": "Ubisoft"}                              # Ubisoft
}

# List of quotes for the dev reports
dev_quotes = [
    "Give them hell!", 
    "War. war never changes!",
    "They are rage, brutal, without mercy. But you. You will be worse. Rip and tear, until it is **done**.",
    "The only thing they fear is you!",
    "HOLD MY BEER, I GOT THIS!",
    "No retreat. No surrender!",
    "The right man in the wrong place can make all the difference in the world.",
    "The harder the battle, the sweeter the victory!",
    "This is where the fun begins!",
    "To be the best, you’ve got to beat the best.",
    "To be the best, you’ve got to beat the rest.",
    "I don't play games. I win them!",
    "Strike swiftly, and without hesitation!",
    "The enemy may be strong, but your will to win is stronger.",
    "Strike first, strike hard, no mercy."
]

# Function to load stats from stats.json
def load_stats():
    global stats
    if stats_file.exists():
        with open(stats_file, "r") as file:
            stats = json.load(file)
    else:
        save_stats()

# Function to save stats to stats.json
def save_stats():
    global stats
    if not stats:
        stats = {
            "streams_checked": 0,
            "messages_sent": 0,
            "active_streams": 0,
            "guilds_tracked": 0,
        }
    with open(stats_file, "w") as file:
        json.dump(stats, file, indent=4)

# Function to update a stat
def update_stat(key, value):
    stats[key] = value
    save_stats()

# Load channel settings from a file
try:
    with open(channel_settings_file, "r") as file:
        channel_settings = json.load(file)
except FileNotFoundError:
    channel_settings = {}

try:
    with open(role_permissions_file, "r") as file:
        role_permissions = json.load(file)
except FileNotFoundError:
    role_permissions = {}
    
# Load targets from a JSON file
def load_targets():
    try:
        with open(targets, "r") as file:
            data = json.load(file)
            return data.get(targets, []), data.get("past_targets", [])
    except FileNotFoundError:
        return [], []

# Save targets to a JSON file
def save_targets():
    with open(targets, "w") as file:
        json.dump({"active_targets": active_targets, "past_targets": past_targets}, file, indent=4)
        
# Load the initial target lists
active_targets, past_targets = load_targets()
    
# Function to save role permissions to a file
def save_role_permissions():
    with open(role_permissions_file, "w") as file:
        json.dump(role_permissions, file)

# Function to save channel settings to a file
def save_channel_settings():
    with open(channel_settings_file, "w") as file:
        json.dump(channel_settings, file)
        
# Helper function to check if a user is authorized to modify the list
def is_authorized(interaction: discord.Interaction) -> bool:
    return interaction.user.id in authorized_users
        
# Function to check if a user has administrator permissions
def is_admin(interaction: discord.Interaction) -> bool:
    return interaction.user.guild_permissions.administrator
        
# Function to check if a user has permission to use the bot
def has_permission(interaction: discord.Interaction) -> bool:
    # Check if the user is an admin
    if interaction.user.guild_permissions.administrator:
        return True

    # Check if the user has a role in the allowed roles list for the guild
    guild_id = str(interaction.guild.id)
    allowed_roles = role_permissions.get(guild_id, [])
    user_roles = [role.id for role in interaction.user.roles]
    return any(role_id in allowed_roles for role_id in user_roles)

# Function to get Twitch Access Token
async def get_twitch_access_token():
    async with aiohttp.ClientSession() as session:
        url = "https://id.twitch.tv/oauth2/token"
        data = {
            "client_id": TWITCH_CLIENT_ID,
            "client_secret": TWITCH_CLIENT_SECRET,
            "grant_type": "client_credentials"
        }
        async with session.post(url, data=data) as response:
            response_json = await response.json()
            return response_json.get("access_token")

# Function to get the Game ID for the Category Name
async def get_game_id():
    global twitch_access_token, game_id
    if twitch_access_token is None:
        twitch_access_token = await get_twitch_access_token()

    async with aiohttp.ClientSession() as session:
        url = f"https://api.twitch.tv/helix/games?name={CATEGORY_NAME}"
        headers = {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {twitch_access_token}"
        }
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                games = data.get("data", [])
                if games:
                    game_id = games[0]["id"]  # Get the ID of the first matching game
                    print(f"Game ID for '{CATEGORY_NAME}': {game_id}")
                else:
                    print(f"No game found for category name '{CATEGORY_NAME}'")
            else:
                print(f"Error fetching game ID: {response.status}")

# Function to get live streams from Twitch
async def get_twitch_streams():
    global twitch_access_token
    if twitch_access_token is None:
        twitch_access_token = await get_twitch_access_token()
    
    if game_id is None:
        await get_game_id()
        if game_id is None:
            return []  # Return an empty list if the game ID couldn't be fetched

    async with aiohttp.ClientSession() as session:
        url = f"https://api.twitch.tv/helix/streams?game_id={game_id}"
        headers = {
            "Client-ID": TWITCH_CLIENT_ID,
            "Authorization": f"Bearer {twitch_access_token}"
        }
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data.get("data", [])
            else:
                print(f"Error: {response.status}")
                return []

# Function to fetch user info from the Twitch API          
async def get_user_info(streamer_username: str):
    url = f"https://api.twitch.tv/helix/users?login={streamer_username.lower()}"
    headers = {
        "Client-ID": TWITCH_CLIENT_ID,
        "Authorization": f"Bearer {twitch_access_token}",
    }
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    users = data.get("data", [])
                    if users:
                        return users[0]  # Return first user object
                else:
                    print(f"Failed to fetch user info for {streamer_username}: {response.status}")
        except Exception as e:
            print(f"Error fetching user info for {streamer_username}: {e}")
    return None

# Function to delete old messages on bot startup
async def delete_old_messages():
    for guild_id, channel_id in channel_settings.items():
        channel = bot.get_channel(channel_id)
        if channel is None:
            continue

        try:
            # Fetch the last 100 messages from the channel
            messages = [message async for message in channel.history(limit=100)]
            
            # Use timezone-aware datetime for comparison
            current_time = datetime.now(timezone.utc)
            
            # Separate messages into those that can be bulk deleted and those that cannot
            messages_to_bulk_delete = [msg for msg in messages if (current_time - msg.created_at).days < 14]
            messages_to_delete_one_by_one = [msg for msg in messages if (current_time - msg.created_at).days >= 14]

            # Bulk delete messages that are less than 14 days old
            if messages_to_bulk_delete:
                await channel.delete_messages(messages_to_bulk_delete)
                print(f"Bulk deleted {len(messages_to_bulk_delete)} messages in channel {channel.id}")

            # Delete older messages one by one
            for message in messages_to_delete_one_by_one:
                await message.delete()
                await asyncio.sleep(1)  # Sleep to avoid hitting rate limits for individual deletions

        except discord.Forbidden:
            print(f"Missing permissions to delete messages in channel {channel.id}")
        except discord.HTTPException as e:
            print(f"Error deleting messages in channel {channel.id}: {e}")
            
# Function to reload channel settings dynamically
def reload_channel_settings():
    global channel_settings
    try:
        with open(channel_settings_file, "r") as file:
            channel_settings = json.load(file)
    except FileNotFoundError:
        channel_settings = {}

# Task to check Twitch API every minute
@tasks.loop(minutes=1)
async def check_twitch_streams():
    global no_stream_message, stream_messages, max_viewers, stream_quotes
    streams_data = await get_twitch_streams()
    current_streams = {stream["id"]: stream for stream in streams_data}

    # Reload channel settings dynamically
    reload_channel_settings()

    # Update stats
    update_stat("streams_checked", stats["streams_checked"] + 1)  # Increment streams checked
    update_stat("active_streams", len(current_streams))  # Current number of active streams
    update_stat("guilds_tracked", len(channel_settings))  # Guilds being tracked

    for guild_id, channel_id in channel_settings.items():
        channel = bot.get_channel(channel_id)
        if channel is None:
            continue

        # Ensure guild-specific message tracking exists
        if guild_id not in stream_messages:
            stream_messages[guild_id] = {}

        # Handle no live streams case
        if not current_streams:
            await bot.change_presence(activity=discord.CustomActivity(name="Scouting for streams..."))
            if guild_id not in no_stream_message:
                embed = discord.Embed(
                    title="No live streams found", 
                    description=f"There are no streams currently live in the {CATEGORY_NAME} category.",
                    color=discord.Color.purple()
                )
                embed.set_footer(text="Sinon - Made by Puppetino")
                no_stream_message[guild_id] = await channel.send(embed=embed)
            continue
        else:
            await bot.change_presence(activity=discord.CustomActivity(name="Stream Sniping on Twitch"))

        # If there was a previous "no streams" message, delete it
        if guild_id in no_stream_message:
            await no_stream_message[guild_id].delete()
            del no_stream_message[guild_id]

        # Update streams and send embeds
        for stream_id, stream in current_streams.items():
            user_name = stream["user_name"].lower()
            started_at = datetime.fromisoformat(stream["started_at"].replace("Z", "+00:00"))
            duration = datetime.now(timezone.utc) - started_at
            duration_str = f"{duration.seconds // 3600}h {duration.seconds % 3600 // 60}m"

            viewer_count = stream["viewer_count"]
            max_viewers[stream_id] = max(max_viewers.get(stream_id, 0), viewer_count)

            # Check if the streamer is a developer
            if user_name in developers:
                dev_info = developers[user_name]

                # Assign a random quote to the stream if it doesn't already have one
                if stream_id not in stream_quotes:
                    stream_quotes[stream_id] = random.choice(dev_quotes)
                quote = stream_quotes[stream_id]

                # Create a special embed for developer streams
                embed = discord.Embed(
                    title=f"{dev_info['display_name']} is live!",
                    url=dev_info["url"],
                    description=(
                        f"One of the developers of {CATEGORY_NAME} is live!\n\n"
                        f"**{quote}**\n\n"
                        f"**Title**: {stream['title']}"
                    ),
                    color=discord.Color.gold()
                )
                embed.add_field(name="Viewers", value=viewer_count, inline=True)
                embed.add_field(name="Max Viewers", value=max_viewers[stream_id], inline=True)
                embed.add_field(name="Duration", value=duration_str, inline=True)
                embed.set_thumbnail(url=stream["thumbnail_url"])
                embed.set_footer(text="Sinon - Made by Puppetino")
            else:
                # Regular embed for other streamers
                embed = discord.Embed(
                    title=stream["title"],
                    url=f"https://www.twitch.tv/{stream['user_name']}",
                    description=f"{stream['user_name']} is streaming {CATEGORY_NAME}",
                    color=discord.Color.purple()
                )
                embed.add_field(name="Viewers", value=viewer_count)
                embed.add_field(name="Max Viewers", value=max_viewers[stream_id])
                embed.add_field(name="Duration", value=duration_str)
                embed.set_thumbnail(url=stream["thumbnail_url"])
                embed.set_footer(text="Sinon - Made by Puppetino")

            # Send or update message
            if stream_id not in stream_messages[guild_id]:
                stream_messages[guild_id][stream_id] = await channel.send(embed=embed)
                update_stat("messages_sent", stats["messages_sent"] + 1)  # Increment messages sent
            else:
                await stream_messages[guild_id][stream_id].edit(embed=embed)

    # Remove ended streams from messages and quotes
    for guild_id, streams in list(stream_messages.items()):
        for stream_id in list(streams):
            if stream_id not in current_streams:
                # Delete the message if it exists
                if stream_id in stream_messages[guild_id]:
                    await stream_messages[guild_id][stream_id].delete()
                    del stream_messages[guild_id][stream_id]
                # Remove from max viewers and quotes
                if stream_id in max_viewers:
                    del max_viewers[stream_id]
                if stream_id in stream_quotes:
                    del stream_quotes[stream_id]

    # Save final stats at the end of the task
    save_stats()

# Command to reload channel settings
@tree.command(name="reload_settings", description="Reload channel settings, clear messages, and prepare for a fresh start.")
async def reload_settings(interaction: discord.Interaction):
    if not is_admin(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    # Reload channel settings
    reload_channel_settings()
    guild_id = str(interaction.guild.id)

    # Check if the guild has a configured channel
    if guild_id not in channel_settings:
        await interaction.response.send_message("No channel is set for updates in this server.", ephemeral=True)
        return

    channel_id = channel_settings[guild_id]
    channel = bot.get_channel(channel_id)

    if channel is None:
        await interaction.response.send_message("The configured channel no longer exists or cannot be accessed.", ephemeral=True)
        return

    try:
        # Delete all bot messages in the channel
        async for message in channel.history(limit=100):
            if message.author == bot.user:
                await message.delete()

        # Clear tracking for the guild
        if guild_id in stream_messages:
            del stream_messages[guild_id]
        if guild_id in no_stream_message:
            del no_stream_message[guild_id]

        # Send confirmation
        embed = discord.Embed(
            title="Settings Reloaded",
            description=(
                f"All messages in {channel.mention} have been cleared.\n"
                "The bot will resend stream messages on the next update."
            ),
            color=discord.Color.purple()
        )
        embed.set_footer(text="Sinon - Made by Puppetino")
        await interaction.response.send_message(embed=embed)

    except discord.Forbidden:
        await interaction.response.send_message(
            "I do not have permission to delete messages in the configured channel.",
            ephemeral=True,
        )
    except discord.HTTPException as e:
        await interaction.response.send_message(
            f"An error occurred while clearing messages: {e}",
            ephemeral=True,
        )

# Command to set the channel for updates
@tree.command(name="set_channel", description="Set the channel for Twitch updates")
async def set_channel(interaction: discord.Interaction):
    if not has_permission(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    old_channel_id = channel_settings.get(str(interaction.guild.id))
    
    # If there was a previously set channel, delete the old messages
    if old_channel_id:
        old_channel = bot.get_channel(old_channel_id)
        if old_channel:
            # Delete the old "no stream" message
            if str(interaction.guild.id) in no_stream_message:
                await no_stream_message[str(interaction.guild.id)].delete()
                del no_stream_message[str(interaction.guild.id)]
            
            # Delete all stream messages
            for stream_id in list(stream_messages):
                if stream_messages[stream_id].channel.id == old_channel_id:
                    await stream_messages[stream_id].delete()
                    del stream_messages[stream_id]
                    del max_viewers[stream_id]

    # Set the new channel ID
    channel_settings[str(interaction.guild.id)] = interaction.channel.id
    save_channel_settings()
    
    embed = discord.Embed(
        title="Channel set",
        description=f"{interaction.channel.mention} is now the channel for Twitch updates.",
        color=discord.Color.purple()
    )
    embed.set_footer(text="Sinon - Made by Puppetino")
    await interaction.response.send_message(embed=embed)
    
# Command to reset the channel for updates
@tree.command(name="reset_channel", description="Reset the channel for Twitch updates")
async def reset_channel(interaction: discord.Interaction):
    if not has_permission(interaction):
        await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
        return

    guild_id = str(interaction.guild.id)
    if guild_id in channel_settings:
        del channel_settings[guild_id]
        save_channel_settings()
        embed = discord.Embed(
            title="Channel reset",
            description="The channel for Twitch updates has been reset.",
            color=discord.Color.purple()
        )
        embed.set_footer(text="Sinon - Made by Puppetino")
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(
            title="No channel set",
            description="There is no channel set for Twitch updates.",
            color=discord.Color.purple()
        )
        embed.set_footer(text="Sinon - Made by Puppetino")
        await interaction.response.send_message(embed=embed)

# Command to add a role that can use the bot (admin only)
@tree.command(name="add_role", description="Add a role that can use the bot")
async def add_role(interaction: discord.Interaction, role: discord.Role):
    if not is_admin(interaction):
        await interaction.response.send_message(
            "You don't have permission to use this command.", ephemeral=True
        )
        return

    guild_id = str(interaction.guild.id)
    if guild_id not in role_permissions:
        role_permissions[guild_id] = []

    if role.id not in role_permissions[guild_id]:
        role_permissions[guild_id].append(role.id)
        save_role_permissions()
        embed = discord.Embed(
            title="Role added",
            description=f"Role @{role.name} has been given permission to use the bot.",
            color=discord.Color.purple()
        )
        embed.set_footer(text="Sinon - Made by Puppetino")
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(
            title="Role already has permission",
            description=f"Role @{role.name} already has permission to use the bot.",
            color=discord.Color.purple()
        )
        embed.set_footer(text="Sinon - Made by Puppetino")
        await interaction.response.send_message(embed=embed)

# Command to remove a role that can use the bot (admin only)
@tree.command(name="remove_role", description="Remove a role's permission to use the bot")
async def remove_role(interaction: discord.Interaction, role: discord.Role):
    if not is_admin(interaction):
        await interaction.response.send_message(
            "You don't have permission to use this command.", ephemeral=True
        )
        return

    guild_id = str(interaction.guild.id)
    if guild_id in role_permissions and role.id in role_permissions[guild_id]:
        role_permissions[guild_id].remove(role.id)
        save_role_permissions()
        embed = discord.Embed(
            title="Role removed",
            description=f"Role @{role.name} has been removed from the allowed roles.",
            color=discord.Color.purple()
        )
        embed.set_footer(text="Sinon - Made by Puppetino")
        await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(
            title="Role does not have permission",
            description=f"Role @{role.name} does not have permission to use the bot.",
            color=discord.Color.purple()
        )
        embed.set_footer(text="Sinon - Made by Puppetino")
        await interaction.response.send_message(embed=embed)
        
# Command to add a target (only authorized users can use this)
@tree.command(name="add_target", description="Add a priority target to the active list (authorized users only)")
async def add_target(interaction: discord.Interaction, name: str, reason: str):
    if not is_authorized(interaction):
        await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
        return

    target = {"name": name, "reason": reason}
    active_targets.append(target)
    save_targets()
    embed = discord.Embed(title="Target added to active targets", color=discord.Color.purple())
    embed.add_field(name="Name", value=name, inline=False)
    embed.add_field(name="Reason", value=reason, inline=False)
    embed.set_footer(text="Sinon - Made by Puppetino")
    await interaction.response.send_message(embed=embed)

# Simplified command to move a target to the past list (only authorized users can use this)
@tree.command(name="move_target", description="Move a target from active to past (authorized users only)")
async def move_target(interaction: discord.Interaction, name: str, status: str):
    if not is_authorized(interaction):
        await interaction.response.send_message("You are not authorized to use this command.", ephemeral=True)
        return

    # Find and remove the target from active_targets
    target = next((t for t in active_targets if t["name"] == name), None)
    if not target:
        embed = discord.Embed(title="Target not found", color=discord.Color.purple())
        embed.set_footer(text="Sinon - Made by Puppetino")
        await interaction.response.send_message(embed=embed)
        return

    active_targets.remove(target)
    target["status"] = status
    past_targets.append(target)
    save_targets()
    embed = discord.Embed(title="Target moved to past targets", color=discord.Color.purple())
    embed.set_footer(text="Sinon - Made by Puppetino")
    await interaction.response.send_message(embed=embed)

# Command to display active targets
@tree.command(name="active_targets", description="Display the active priority targets")
async def display_active_targets(interaction: discord.Interaction):
    if not active_targets:
        embed = discord.Embed(title="There are no active targets yet", color=discord.Color.purple())
        embed.set_footer(text="Sinon - Made by Puppetino")
        await interaction.response.send_message(embed=embed)
        return

    embed = discord.Embed(title="Active Priority Targets", color=discord.Color.purple())
    for target in active_targets:
        embed.add_field(name=target["name"], value=target["reason"], inline=False)
    
    embed.set_footer(text="Sinon - Made by Puppetino")
    await interaction.response.send_message(embed=embed)

# Command to display past targets
@tree.command(name="past_targets", description="Display the past priority targets")
async def display_past_targets(interaction: discord.Interaction):
    if not past_targets:
        embed = discord.Embed(title="There are no past targets yet", color=discord.Color.purple())
        embed.set_footer(text="Sinon - Made by Puppetino")
        await interaction.response.send_message(embed=embed)
        return

    embed = discord.Embed(title="Past Priority Targets", color=discord.Color.purple())
    for target in past_targets:
        # Combine reason and status into a single string
        embed.add_field(
            name=target["name"],
            value=f"Reason: {target['reason']}\nStatus: {target['status']}",
            inline=False
        )
    
    embed.set_footer(text="Sinon - Made by Puppetino")
    await interaction.response.send_message(embed=embed)

# About Command
@tree.command(name="about", description="About the bot")
async def about(interaction: discord.Interaction):
    embed = discord.Embed(
        title="About the bot",
        description=(
                "Welcome!\n\n"
                "If you're reading this, it likely means one of the following applies to you:\n"
                "- Are part of SSI\n"
                "- Are associated with SSI\n"
                "- You’re familiar with SSI and know about Sinon\n\n"
                "Regardless of how you got here, you’re probably interested in using Sinon or learning more about it.\n\n"
                "What is Sinon?\n"
                "Sinon is a dedicated Discord bot designed to monitor live streams on Twitch exclusively for the game BattleCore Arena. It keeps you informed by sending live updates directly to the designated channel of your choice. Additionally, it alerts you when a developer is watching the stream, ensuring you never miss any important activity.\n\n"
                "How does it work?\n"
                "Oh, you thought I’d explain all the juicy details here?\n"
                "No lmao. 💀\n\n"
                "If you really want to know how it works, you'll have to notify me directly.\n"
                "—@Puppetino.\n\n"
                "Thanks for using Sinon!\n"
        ),
        color=discord.Color.purple()
    )
    embed.add_field(name="Version", value="2.0.0")
    embed.set_footer(text="Sinon - Made by Puppetino")
    await interaction.response.send_message(embed=embed)

# Event that runs when the bot is ready (reconnected)
@bot.event
async def on_ready():
    global is_disconnected, disconnection_time

    load_stats()
    
    if is_disconnected:
        # Calculate downtime duration
        reconnect_time = datetime.now()
        reconnect_time_str = reconnect_time.strftime("%Y-%m-%d %H:%M:%S")
        downtime = reconnect_time - disconnection_time
        downtime_str = f"{downtime.seconds // 3600}h {downtime.seconds % 3600 // 60}m {downtime.seconds % 60}s"

        # Log the reconnect event
        print(f"[{reconnect_time_str}] Bot successfully reconnected to Discord.")

        # Send a summary to the bot owner
        try:
            owner = await bot.fetch_user(OWNER_ID)
            if owner:
                embed = discord.Embed(
                    title="Connection Timeout Report",
                    color=discord.Color.purple(),
                    description=(
                        "The bot experienced a connection timeout but has successfully reconnected."
                    ),
                )
                embed.add_field(name="Disconnection Time", value=disconnection_time.strftime("%Y-%m-%d %H:%M:%S"), inline=False)
                embed.add_field(name="Reconnection Time", value=reconnect_time_str, inline=False)
                embed.add_field(name="Downtime Duration", value=downtime_str, inline=False)
                embed.set_footer(text="Sinon - Made by Puppetino")
                await owner.send(embed=embed)
        except Exception:
            traceback.print_exc()
            print("Unable to notify the owner about the reconnection.")

        # Reset the disconnection flag and time
        is_disconnected = False
        disconnection_time = None

    # Regular startup tasks
    if not check_twitch_streams.is_running():
        await tree.sync()
        await delete_old_messages()
        print(f"Successfully logged in as {bot.user}")
        await get_game_id()
        check_twitch_streams.start()

# Event that runs when the bot is disconnected
@bot.event
async def on_disconnect():
    global is_disconnected, disconnection_time

    # Only set the disconnection time and flag on the first disconnect
    if not is_disconnected:
        is_disconnected = True
        disconnection_time = datetime.now()

        # Log the disconnect event
        disconnect_time_str = disconnection_time.strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{disconnect_time_str}] Bot disconnected from Discord.")

# Run the bot
bot.run(DISCORD_TOKEN)