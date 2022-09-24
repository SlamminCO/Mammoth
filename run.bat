docker rm --force mammoth_bot
docker run -d --name=mammoth_bot --mount source=mammoth_bot_data,destination=/mammoth_bot_data mammoth_bot