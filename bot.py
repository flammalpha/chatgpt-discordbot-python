import os
from dotenv import load_dotenv
import discord

from text_generation import Chat
from speech_generation import Voice

load_dotenv()

discord_token = os.getenv("discord_token")
openai_token = os.getenv("openai_token")
elevenlabs_token = os.getenv("elevenlabs_token")
guild_id = int(os.getenv("guild_id"))
category_id = int(os.getenv("category_id"))

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
chatgpt = Chat(openai_token)
elevenlabs = Voice(elevenlabs_token)


@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')


@client.event
async def on_message(message: discord.Message):
    if ignoreMessage(message):
        print("Not my business")
        return

    print("Working...")
    async with message.channel.typing():
        # generate ChatGPT prompt
        message_history = await generate_messagehistory(message.channel)
        response = await chatgpt.get_response_async(message_history)

        # check if user is in voice -> generate TTS if funds available
        if message.author.voice and message.author.voice.channel:
            # message.author.voice.channel.connect()
            if elevenlabs.get_character_remaining() > response:
                # generate voice
                pass
            else:
                # say not enough funds
                pass
    await message.channel.send(response)


async def generate_messagehistory(channel: discord.TextChannel):
    print("Reading message history")
    messages = []
    async for message in channel.history(limit=None, oldest_first=True):
        # check user or bot
        if message.author.id == client.user.id:
            messages.append(
                {"role": "assistant", "content": message.content})
        else:
            # check system message
            if message.content.startswith('{') and message.content.endswith("}"):
                messages.append(
                    {"role": "system", "content": message.content[1:-1]})
            else:
                messages.append(
                    {"role": "user", "content": message.content})
    return messages


def ignoreMessage(message: discord.Message) -> bool:
    '''Checks for bot account,
    chat inside certain guild with category,
    aswell as system prompt'''
    if message.author.bot or message.author.id == client.user.id:
        print("Bot detected")
        return True
    if message.guild.id != guild_id:
        print(f"Wrong guild {message.guild.id} but expected {guild_id}")
        return True
    if message.channel.category is None or message.channel.category.id != category_id:
        print("Not in Category")
        return True
    if message.content.startswith('{') and message.content.endswith("}"):
        print("System message")
        return True
    return False


client.run(discord_token)
