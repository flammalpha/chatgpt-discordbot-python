import re
import discord

async def handle_test_message(message: discord.Message):
    print(message.content)
    if len(message.attachments) > 0:
        url = message.attachments[0].url.split("?")[0]
        print(message.content)
        await handle_image(message, url)
        return
    
    # check if message content has url http or https
    url_regex = r"https?://[^\s]+"
    match = re.search(url_regex, message.content)
    if match:
        print("URL found")
        url = match.group(0)
        await handle_image(message, url)
    else:
        await message.channel.send("No attachments found")


async def handle_image(message: discord.Message, url: str):
    print(message.content)
    await message.channel.send(url)