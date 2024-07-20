import discord
from utils import has_allowed_role, save_settings, load_settings, logger

# Setup for the commands
def setup_commands(bot, settings):
    tree = bot.tree

    # Command to set allowed role
    @tree.command(name="set_allowed_role", description="Set roles allowed to use bot commands")
    async def set_allowed_role(interaction: discord.Interaction, role: discord.Role):
        if has_allowed_role(interaction, settings):
            guild_id = str(interaction.guild_id)
            if guild_id not in settings['guilds']:
                settings['guilds'][guild_id] = {}
            settings['guilds'][guild_id]['allowed_role'] = role.id
            save_settings(settings)
            embed = discord.Embed(
                title="Allowed role set",
                description=f"The role {role.mention} is now allowed to use certain bot commands.",
                color=discord.Color(0x9900ff)
            )
            embed.set_footer(text="Sinon - Made by Puppetino")
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)

    # Command to set report channel
    @tree.command(name="set_report_channel", description="Set the channel for stream updates")
    async def set_report_channel(interaction: discord.Interaction, channel: discord.TextChannel):
        if has_allowed_role(interaction, settings):
            guild_id = str(interaction.guild_id)
            if guild_id not in settings['guilds']:
                settings['guilds'][guild_id] = {}
            settings['guilds'][guild_id]['channel_id'] = channel.id
            save_settings(settings)
            embed = discord.Embed(
                title="Stream updates will be posted in",
                description=channel.mention,
                color=discord.Color(0x9900ff)
            )
            embed.set_footer(text="Sinon - Made by Puppetino")
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)

    # Command to set Twitch category
    @tree.command(name="set_twitch_category", description="Set or change the Twitch category")
    async def set_twitch_category(interaction: discord.Interaction, category: str):
        if has_allowed_role(interaction, settings):
            guild_id = str(interaction.guild_id)
            if guild_id not in settings['guilds']:
                settings['guilds'][guild_id] = {}
            settings['guilds'][guild_id]['category_name'] = category
            save_settings(settings)
            embed = discord.Embed(
                title="Updated category",
                description=f"The category {category} is now being monitored on Twitch. Note that it can take up to 2.5 minutes for the category to update.",
                color=discord.Color(0x9900ff)
            )
            embed.set_footer(text="Sinon - Made by Puppetino")

            try:
                await interaction.response.send_message(embed=embed)
            except discord.errors.NotFound as e:
                logger.error(f"Ignoring NotFound error: {e}")
        else:
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)

    # Setup command
    @tree.command(name="setup", description="Initialize Setup")
    async def setup_command(interaction: discord.Interaction, channel: str, category: str):
        if has_allowed_role(interaction, settings):
            guild_id = str(interaction.guild_id)
            if guild_id not in settings['guilds']:
                settings['guilds'][guild_id] = {}

            channel_id = int(''.join(filter(str.isdigit, channel)))
            settings['guilds'][guild_id]['channel_id'] = channel_id
            settings['guilds'][guild_id]['category_name'] = category
            save_settings(settings)
            embed = discord.Embed(
                title="Setup Complete",
                description=f"Sinon will now report streams in {channel} and monitor any updates in the {category} category.\n"
                            f"Enjoy!",
                color=discord.Color(0x9900ff)
            )
            embed.set_footer(text="Sinon - Made by Puppetino")
            await interaction.response.send_message(embed=embed)
        else:
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)

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

    # Command to reset settings for a specific guild
    @tree.command(name="reset", description="Reset settings for this guild")
    async def reset_command(interaction: discord.Interaction):
        try:
            settings = load_settings()  # Load settings fresh at command execution
            guild_id = str(interaction.guild_id)  # Get the guild ID as a string

            if has_allowed_role(interaction, settings):
                # Reset settings only for the current guild
                if 'guilds' in settings and guild_id in settings['guilds']:
                    settings['guilds'][guild_id] = {}
                    save_settings(settings)
                    embed = discord.Embed(
                        title="Settings reset",
                        description=f"Settings have been reset for this guild ({interaction.guild.name}).",
                        color=discord.Color(0x9900ff)
                    )
                    embed.set_footer(text="Sinon - Made by Puppetino")
                    await interaction.response.send_message(embed=embed)
                    logger.info(f"Settings have been reset for guild: {interaction.guild.name} by user: {interaction.user.name}")
                else:
                    await interaction.response.send_message("No settings found to reset for this guild.", ephemeral=True)
                    logger.warning(f"No settings found for guild: {interaction.guild.name}")
            else:
                await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)
                logger.warning("User without permission attempted to reset settings.")
        except Exception as e:
            logger.error(f"Error in reset command: {e}")
            await interaction.response.send_message("An error occurred while resetting settings.", ephemeral=True)

    # Command to enable/disable developer mode 
    @tree.command(name="dev_mode", description="Enable or disable developer mode")
    async def dev_mode_command(interaction: discord.Interaction):
        if interaction.user.id == 487588371443613698:  # Check if the user ID matches
            settings = load_settings()

            # Toggle dev_mode globally
            dev_mode = not settings.get('dev_mode', False)
            settings['dev_mode'] = dev_mode
            save_settings(settings)

            # Respond to interaction with embed
            embed = discord.Embed(
                title="Developer Mode",
                description=f"Developer mode has been {'enabled' if dev_mode else 'disabled'}.",
                color=discord.Color(0x9900ff)
            )
            embed.set_footer(text="Sinon - Made by Puppetino")
            try:
                await interaction.response.send_message(embed=embed)
            except discord.errors.NotFound as e:
                logger.error(f"Ignoring NotFound error: {e}")

            # Update bot presence for all guilds
            activity_name = "In Developer Mode" if settings["dev_mode"] else "Stream Sniping on Twitch"
            await bot.change_presence(activity=discord.CustomActivity(name=activity_name))
        else:
            await interaction.response.send_message("You don't have permission to use this command.", ephemeral=True)