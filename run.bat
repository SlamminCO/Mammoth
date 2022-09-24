docker rm --force mammoth-bot
docker run -d --name=mammoth-bot --mount source=mammoth-bot-data,destination=/mammoth-bot-data mammoth-bot