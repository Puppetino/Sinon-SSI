import json
import discord
import asyncio

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
                    async for message in channel.history(limit=None):
                        if message.author == bot.user:
                            await message.delete()
                            await asyncio.sleep(0.5)
                    bot.reported_streams[guild_id] = {}
                except discord.Forbidden:
                    print(f"Missing permissions to purge messages in channel: {channel.name}")
                except discord.HTTPException as e:
                    if e.status == 429:
                        retry_after = e.retry_after
                        print(f"Rate limited when deleting messages in channel: {channel.name}. Retrying after {retry_after} seconds.")
                        await asyncio.sleep(retry_after)
                        await delete_all_messages(bot, settings)  # Retry deleting messages
                    else:
                        print(f"Failed to purge messages in channel: {channel.name} - {e}")
                except Exception as e:
                    print(f"An error occurred: {e}")
            else:
                print(f"Channel with ID {channel_id} does not exist")
        else:
            print(f"No channel_id found for guild ID {guild_id}")

# Delete guild data
def delete_guild_data(guild_id):
    settings = load_settings()
    
    if 'guilds' in settings and guild_id in settings['guilds']:
        del settings['guilds'][guild_id]
        print(f"Deleted data for guild ID: {guild_id}")
        save_settings(settings)
    else:
        print(f"No data found for guild ID: {guild_id}")