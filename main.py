# bot.py
# Requires: discord.py v2.4+ (pip install -U discord.py)
import discord
from discord import app_commands
import asyncio
from datetime import datetime, timedelta
import os
import dotenv
from dotenv import load_dotenv
load_dotenv()

GUILD_ID = 1526024162768846988  # integer
LOG_CHANNEL_ID = 1526073282447544440
INVITE_URL = "https://discord.gg/egZtSDaEq6"

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

warnings = {}       # user_id -> int
tempban_tasks = {}  # user_id -> asyncio.Task

def make_embed(title, description="", color=0xFF0000, fields=None):
    e = discord.Embed(title=title, description=description, color=color)
    if fields:
        for name, value, inline in fields:
            e.add_field(name=name, value=value, inline=inline)
    return e

def join_button():
    return discord.ui.Button(label="Join Discord Server", url=INVITE_URL, style=discord.ButtonStyle.success)

async def log_send(embed: discord.Embed):
    ch = client.get_channel(LOG_CHANNEL_ID)
    if ch:
        await ch.send(embed=embed)

async def try_dm(user: discord.User, dm_embed: discord.Embed, components=None):
    try:
        if components:
            view = discord.ui.View()
            for c in components:
                view.add_item(c)
            await user.send(embed=dm_embed, view=view)
        else:
            await user.send(embed=dm_embed)
        return "Sent", None
    except discord.Forbidden as e:
        code = getattr(e, 'code', None)
        if code == 50278 or "50278" in str(e):
            return "Failed (no mutual guilds)", "403 Forbidden (50278): Cannot send messages to this user due to having no mutual guilds"
        return "Failed (forbidden)", f"403 Forbidden: {e}"
    except Exception as e:
        return "Failed", str(e)

async def dm_and_log(user: discord.User, dm_embed: discord.Embed, log_embed: discord.Embed, components=None):
    status, err = await try_dm(user, dm_embed, components)
    log_embed.add_field(name="DM status", value=status, inline=False)
    if err:
        log_embed.add_field(name="DM error", value=str(err)[:1024], inline=False)
    await log_send(log_embed)

@client.event
async def on_ready():
    await tree.sync(guild=discord.Object(id=GUILD_ID))
    print("Bot ready:", client.user)

async def dm_then_action_member(member: discord.Member, dm_embed, log_embed, components, action_coro):
    status, err = await try_dm(member, dm_embed, components)
    log_embed.add_field(name="DM status", value=status, inline=False)
    if err:
        log_embed.add_field(name="DM error", value=str(err)[:1024], inline=False)
    await log_send(log_embed)
    try:
        await action_coro()
    except Exception:
        pass

# /ban
@tree.command(name="ban", description="Ban a member", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Member to ban", reason="Reason")
async def ban(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    dm = make_embed("Banned", f"You have been banned from 𝑩𝒂𝒔𝒕𝒂𝒓𝒅 𝑴ü𝒏𝒄𝒉𝒆𝒏 | 𝑷𝒖𝒃𝒍𝒊𝒄 𝑺𝒆𝒓𝒗𝒆𝒓\n\nReason:\n{reason}", color=0xFF0000)
    log = make_embed("Member Banned", color=0xFF0000, fields=[
        ("Sent By", f"{interaction.user}", True),
        ("Sent To", f"{member} ({member.id})", True),
        ("Action", "Permanent Ban", True),
        ("Reason", reason, False)
    ])
    async def do_ban():
        await interaction.guild.ban(member, reason=reason)
    await dm_then_action_member(member, dm, log, None, do_ban)
    await interaction.followup.send(f"Banned {member}.", ephemeral=True)

# /timeout
@tree.command(name="timeout", description="Timeout a member", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Member to timeout", minutes="Minutes", reason="Reason")
async def timeout(interaction: discord.Interaction, member: discord.Member, minutes: int, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    dur = minutes * 60
    dm = make_embed("TimeOut", f"You have been timed out from 𝑩𝒂𝒔𝒕𝒂𝒓𝒅 𝑴ü𝒏𝒄𝒉𝒆𝒏 | 𝑷𝒖𝒃𝒍𝒊𝒄 𝑺𝒆𝒓𝒗𝒆𝒓\n\nReason:\n{reason}\nDuration: {minutes} minute(s)", color=0xFFFF00)
    log = make_embed("Timeout Issued", color=0xFFFF00, fields=[
        ("sent By", f"{interaction.user}", True),
        ("Sent To", f"{member}", True),
        ("Duration", f"{minutes} minute(s)", True),
        ("Reason", reason, False)
    ])
    async def do_timeout():
        await member.timeout_for(timedelta(seconds=dur), reason=reason)
    await dm_then_action_member(member, dm, log, None, do_timeout)
    await interaction.followup.send(f"Timed out {member} for {minutes} minute(s).", ephemeral=True)

# /warn
@tree.command(name="warn", description="Warn a member", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Member to warn", reason="Reason")
async def warn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    prev = warnings.get(member.id, 0)
    warnings[member.id] = prev + 1
    dm = make_embed("WARNED", f"You have been warned from 𝑩𝒂𝒔𝒕𝒂𝒓𝒅 𝑴ü𝒏𝒄𝒉𝒆𝒏 | 𝑷𝒖𝒃𝒍𝒊𝒄 𝑺𝒆𝒓𝒗𝒆𝒓\n\nReason:\n{reason}", color=0xFFA500)
    log = make_embed("Member Warned", color=0xFFA500, fields=[
        ("Staff", f"{interaction.user}", True),
        ("User", f"{member} ({member.id})", True),
        ("New Warnings", str(prev+1), True),
        ("Reason", reason, False)
    ])
    await dm_and_log(member, dm, log)
    await interaction.followup.send(f"Warned {member}.", ephemeral=True)

async def schedule_unban(guild: discord.Guild, user_id: int, unban_at: datetime):
    await asyncio.sleep((unban_at - datetime.utcnow()).total_seconds())
    try:
        await guild.unban(discord.Object(id=user_id))
    except:
        pass
    embed = make_embed("Member Unbanned (Temp-Ban Expiry)", color=0x00FF00, fields=[
        ("User", f"{user_id}", False),
        ("Reason", "Temp-ban expired", False)
    ])
    await log_send(embed)
    tempban_tasks.pop(user_id, None)

# /temp-ban
@tree.command(name="temp-ban", description="Temporary ban", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Member to temp-ban", days="Days", reason="Reason")
async def temp_ban(interaction: discord.Interaction, member: discord.Member, days: int, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    dm = make_embed("Temporary Ban", f"You have been temp banned for {days} day(s)\n\nReason:\n{reason}\n\nExpires on:\n{(datetime.utcnow()+timedelta(days=days)).strftime('%A, %B %d, %Y %I:%M %p')}", color=0xFF0000)
    log = make_embed("Temp-Ban Issued", color=0xFF0000, fields=[
        ("User", f"{member}", True),
        ("Staff", f"{interaction.user}", True),
        ("Duration", f"{days} day(s)", True),
        ("Unban Date", (datetime.utcnow()+timedelta(days=days)).strftime('%A, %B %d, %Y %I:%M %p'), False),
        ("Reason", reason, False)
    ])
    async def do_tempban():
        await interaction.guild.ban(member, reason=reason)
    await dm_then_action_member(member, dm, log, None, do_tempban)
    unban_at = datetime.utcnow() + timedelta(days=days)
    if member.id in tempban_tasks:
        tempban_tasks[member.id].cancel()
    tempban_tasks[member.id] = asyncio.create_task(schedule_unban(interaction.guild, member.id, unban_at))
    await interaction.followup.send(f"Temp-banned {member} for {days} day(s).", ephemeral=True)

# /unban
@tree.command(name="unban", description="Unban by ID", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(userid="User ID to unban", reason="Reason")
async def unban(interaction: discord.Interaction, userid: str, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    guild = interaction.guild
    user = None
    try:
        user = await client.fetch_user(int(userid))
    except:
        user = None
    dm = make_embed("UNBANNED", f"You have been unbanned from 𝑩𝒂𝒔𝒕𝒂𝒓𝒅 𝑴ü𝒏𝒄𝒉𝒆𝒏 | 𝑷𝒖𝒃𝒍𝒊𝒄 𝑺𝒆𝒓𝒗𝒆𝒓\n\nReason:\n{reason}", color=0x00FF00)
    # FIX: use str(user) instead of user.tag (some User objects lack .tag in your version)
    log = make_embed("Member Unbanned", color=0x00FF00, fields=[
        ("Action By", f"{interaction.user}", True),
        ("User", f"{user} ({userid})" if user else userid, True),
        ("Reason", reason, False)
    ])
    try:
        await guild.unban(discord.Object(id=int(userid)))
    except:
        pass
    if user:
        status, err = await try_dm(user, dm, [join_button()])
        log.add_field(name="DM status", value=status, inline=False)
        if err:
            log.add_field(name="DM error", value=str(err)[:1024], inline=False)
    else:
        log.add_field(name="DM status", value="No user object", inline=False)
    await log_send(log)
    await interaction.followup.send(f"Unbanned {userid}.", ephemeral=True)

# /unwarn
@tree.command(name="unwarn", description="Remove a warn", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Member", reason="Reason")
async def unwarn(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    old = warnings.get(member.id, 0)
    new = max(0, old - 1)
    warnings[member.id] = new
    dm = make_embed("UNWARNED", f"UNWARNED\nYou have been unwarned and you have {new}", color=0x00FF00)
    log = make_embed("Warning Remoted", color=0x00FF00, fields=[
        ("Action By", f"{interaction.user}", True),
        ("User", f"{member}", True),
        ("Old Warning Count", str(old), True),
        ("New Warning Count", str(new), True)
    ])
    await dm_and_log(member, dm, log)
    await interaction.followup.send(f"Removed a warning from {member}.", ephemeral=True)

# /untimeout
@tree.command(name="untimeout", description="Remove timeout", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Member", reason="Reason")
async def untimeout(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    try:
        await member.timeout_for(None, reason=reason)
    except:
        pass
    dm = make_embed("UNTIMEDOUT", f"You have been untimed out from 𝑩𝒂𝒔𝒕𝒂𝒓𝒅 𝑴ü𝒏𝒄𝒉𝒆𝒏 | 𝑷𝒖𝒃𝒍𝒊𝒄 𝑺𝒆𝒓𝒗𝒆𝒓\n\nReason:\n{reason}\n\nYou can now talk in the server now", color=0x00FF00)
    log = make_embed("Untimed Out", color=0x00FF00, fields=[
        ("Action By", f"{interaction.user}", True),
        ("User", f"{member}", True),
        ("Reason", reason, False)
    ])
    await dm_and_log(member, dm, log)
    await interaction.followup.send(f"Removed timeout for {member}.", ephemeral=True)

# /kick
@tree.command(name="kick", description="Kick a member", guild=discord.Object(id=GUILD_ID))
@app_commands.describe(member="Member to kick", reason="Reason")
async def kick(interaction: discord.Interaction, member: discord.Member, reason: str = "No reason provided"):
    await interaction.response.defer(ephemeral=True)
    dm = make_embed("KICKED", f"You have been kicked from 𝑩𝒂𝒔𝒕𝒂𝒓𝒅 𝑴ü𝒏𝒄𝒉𝒆𝒏 | 𝑷𝒖𝒃𝒍𝒊𝒄 𝑺𝒆𝒓𝒗𝒆𝒓\n\nReason:\n{reason}", color=0xFF0000)
    row = [join_button()]
    log = make_embed("User Kicked", color=0xFF0000, fields=[
        ("Action By", f"{interaction.user}", True),
        ("Target", f"{member} ({member.id})", True),
        ("Status", "Kicked", True),
        ("Reason", reason, False)
    ])
    async def do_kick():
        await member.kick(reason=reason)
    await dm_then_action_member(member, dm, log, row, do_kick)
    await interaction.followup.send(f"Kicked {member}.", ephemeral=True)

client.run(os.getenv("TOKEN"))
