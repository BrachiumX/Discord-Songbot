# Discord-Songbot

Self-hosted Discord Music Player Bot.

Uses yt-dlp to fetch stream urls from youtube and ffmpeg to stream the audio to discord.

Since it is stream based, you can play live streams, huge playlists from the bot because it does not download the content that it is playing.

## To set it up:

### Set up the code

<pre>
git clone https://github.com/BrachiumX/Discord-Songbot.git
cd Discord-Songbot
python -m venv .venv
source ./.venv/bin/activate
pip install -r requirement.txt`
</pre>

### Set up the bot

You also have to create an app in the Discord Developer Page and set the api key as an enviroment variable.

<pre>
  export DISCORD_KEY="YOUR_API_KEY"
</pre>

You also have to add the bot to your server manually.

You can find how to do these steps in Discord's own website.

## To run it:

<pre>
  cd Discord-Songbot
  source ./.venv/bin/activate
  python bot.py
</pre>

## Commands

You can write -h to see the commands in your server.

## Disclaimer

Youtube doesn't really enjoy people using their website for purposes like these. So use it at your own risk.
