import discord
from discord.ext import commands
from discord import app_commands
import os
import time
import json
import asyncio
import traceback

TOKEN = os.getenv("TOKEN")
LOGIN_CHANNEL = 1473015218211651706

ADMIN_ROLE = 1473015044643094643

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

sessions = {}
points = {}
leave_timers = {}

# تحميل النقاط
if os.path.exists("points.json"):
    with open("points.json", "r") as f:
        points = json.load(f)

def save_points():
    with open("points.json", "w") as f:
        json.dump(points, f)

def format_time(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02}:{m:02}:{s:02}"

# صلاحيات
def is_admin(member):
    return any(role.id == ADMIN_ROLE for role in member.roles)

@bot.event
async def on_ready():
    print(f"Bot Online: {bot.user}")
    await bot.tree.sync()

# ======================
# Slash Commands
# ======================

@bot.tree.command(name="نقاط")
@app_commands.describe(member="العضو")
async def points_command(interaction: discord.Interaction, member: discord.Member):
    await interaction.response.send_message(
        f"📊 | نقاط {member.mention}: {points.get(str(member.id), 0)}"
    )

@bot.tree.command(name="اعطاء_نقاط")
@app_commands.describe(member="العضو", amount="عدد النقاط")
async def give_points(interaction: discord.Interaction, member: discord.Member, amount: int):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ | ليس لديك صلاحية", ephemeral=True)

    if amount <= 0:
        return await interaction.response.send_message("❌ | رقم غير صحيح", ephemeral=True)

    points[str(member.id)] = points.get(str(member.id), 0) + amount
    save_points()

    await interaction.response.send_message(f"🎁 تم إعطاء {amount} نقطة لـ {member.mention}")

@bot.tree.command(name="سحب_نقاط")
@app_commands.describe(member="العضو", amount="عدد النقاط")
async def remove_points(interaction: discord.Interaction, member: discord.Member, amount: int):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ | ليس لديك صلاحية", ephemeral=True)

    current = points.get(str(member.id), 0)

    if amount <= 0 or current < amount:
        return await interaction.response.send_message("❌ | رقم غير صحيح", ephemeral=True)

    points[str(member.id)] = current - amount
    save_points()

    await interaction.response.send_message(f"🗑️ تم سحب {amount} نقطة من {member.mention}")

@bot.tree.command(name="صفر")
@app_commands.describe(member="العضو")
async def reset_user(interaction: discord.Interaction, member: discord.Member):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ | ليس لديك صلاحية", ephemeral=True)

    points[str(member.id)] = 0
    save_points()

    await interaction.response.send_message(f"🧹 تم تصفير {member.mention}")

@bot.tree.command(name="تصفير")
async def reset_all(interaction: discord.Interaction):
    if not is_admin(interaction.user):
        return await interaction.response.send_message("❌ | ليس لديك صلاحية", ephemeral=True)

    points.clear()
    save_points()

    await interaction.response.send_message("🧹 تم تصفير الجميع")

# ======================
# نظام الحضور الصوتي
# ======================

@bot.event
async def on_message(message):
    try:
        if message.author.bot:
            return

        if message.channel.id != LOGIN_CHANNEL:
            return

        member = message.author

        # تسجيل دخول
        if message.content.strip() == "تسجيل دخول":

            if not member.voice or not member.voice.channel:
                return await message.reply("❌ لازم تكون داخل روم صوتي")

            if member.id in sessions:
                return await message.reply("⚠️ انت مسجل بالفعل")

            sessions[member.id] = time.time()

            await message.reply("🟢 تم تسجيل دخولك")

            try:
                await member.send(
                    "🟢 تم تسجيل دخولك\n🎧 يتم احتساب الوقت الآن\n⭐ 30 نقطة لكل ساعة"
                )
            except:
                pass

        # تسجيل خروج
        elif message.content.strip() == "تسجيل خروج":

            if member.id not in sessions:
                return await message.reply("❌ انت غير مسجل")

            start = sessions[member.id]
            duration = int(time.time() - start)
            earned = int((duration / 3600) * 30)

            del sessions[member.id]

            points[str(member.id)] = points.get(str(member.id), 0) + earned
            save_points()

            await message.reply(
                f"⏳ الوقت: {format_time(duration)}\n⭐ النقاط: {earned}\n🏆 مجموعك: {points[str(member.id)]}"
            )

        await bot.process_commands(message)

    except:
        print(traceback.format_exc())

@bot.event
async def on_voice_state_update(member, before, after):
    try:
        if before.channel == after.channel:
            return

        if member.id not in sessions:
            return

        # خروج
        if before.channel and not after.channel:

            if member.id in leave_timers:
                leave_timers[member.id].cancel()

            async def leave_timer():
                await asyncio.sleep(300)

                if member.id in sessions and (not member.voice or not member.voice.channel):

                    start = sessions[member.id]
                    duration = int(time.time() - start)
                    earned = int((duration / 3600) * 30)

                    del sessions[member.id]

                    points[str(member.id)] = points.get(str(member.id), 0) + earned
                    save_points()

                    try:
                        await member.send(
                            f"⏰ انتهت المهلة\n⏳ الوقت: {format_time(duration)}\n⭐ النقاط: {earned}"
                        )
                    except:
                        pass

            leave_timers[member.id] = asyncio.create_task(leave_timer())

            try:
                await member.send("🚪 خرجت من الصوتي، لديك 5 دقائق للعودة")
            except:
                pass

        # رجوع
        if after.channel:
            if member.id in leave_timers:
                leave_timers[member.id].cancel()
                del leave_timers[member.id]

                try:
                    await member.send("✅ تم إلغاء المهلة واستمرار تسجيلك")
                except:
                    pass

    except:
        print(traceback.format_exc())

bot.run(TOKEN)
