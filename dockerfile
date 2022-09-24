FROM python:3.10

WORKDIR /mammoth-bot-app

VOLUME [ "/mammoth_bot_data" ]

ADD cogs/ ./cogs

ADD main.py .

ADD helper.py .

ADD storage.py .

ADD shared_classes.py .

ADD requirements.txt .

ADD settings.json .

ADD token.json .

RUN pip install -r requirements.txt

CMD [ "python", "-u", "./main.py" ]