# Simple Discord bot to access ChatGPT written in Python

## Features

- Check for guild_id and category_id to only work in a specific "directory" (security reasons - I'm paranoid)
- Each Channel below a category is a conversation
- Channel description allows configuration of bot
  - json style
  - set message history length
  - set GPT model version
- Messages encased in `{...}` are marked as System
- Messages starting with `!!` will be ignored
- Long messages will be split into 2000 characters
  - Code-Blocks will be split on linebreaks cleanly
  - Language-Code will be transferred if available
  - Normal messages will be split on last period or linebreak
- Delete all messages inbetween and including messges reacted with `:X:` (`\u274c`)

## How-To

Create a `config.json` file according to the `config.json.example` file and fill in at least these values:

```plain
    ...
    "openai_token": "",
    "elevenlabs_token": "",
    "discord_token": "",
    "model_list": [
        "gpt-4.1"
    ],
    "model_default": "gpt-4.1",
    ...
```

## Ressources

- [ChatGPT](https://chat.openai.com)
- [ChatGPT API](https://platform.openai.com/docs/api-reference)
- [Discord.py](https://discordpy.readthedocs.io/en/stable/)
