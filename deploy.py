import json
import argparse
import os

parser = argparse.ArgumentParser()
parser.add_argument(
    "--deploy-id",
    dest="deployment_id",
    type=str,
    default="mammoth_bot",
    required=False,
    help="Give the instance a custom name. Useful for deploying multiple instances.",
)
parser.add_argument(
    "--no-auto-restart",
    dest="auto_restart",
    action="store_false",
    required=False,
    help="Disable auto-restarting when the bot crashes.",
)
parser.add_argument(
    "--no-asyncio-gather",
    dest="asyncio_gather",
    action="store_false",
    required=False,
    help="Disable using asyncio gather when generating hashes.",
)
parser.add_argument(
    "--no-caching",
    dest="caching",
    action="store_false",
    required=False,
    help="Disable caching hashes.",
)
parser.add_argument(
    "--owner-ids",
    dest="owner_ids",
    action="extend",
    nargs="+",
    type=int,
    required=True,
    help="List of discord IDs authorized to run the bot's owner commands.",
)
parser.add_argument(
    "--no-debug-printing",
    dest="debug_printing",
    action="store_false",
    required=False,
    help="Disable debug printers.",
)
parser.add_argument(
    "--debug-print-spam",
    dest="spammy_debug_printing",
    action="store_true",
    required=False,
    help="Enable more spammy debug printers.",
)
parser.add_argument(
    "--token", dest="bot_token", type=str, required=True, help="Discord bot token."
)
parser.add_argument(
    "--docker",
    dest="docker_mode",
    action="store_true",
    required=False,
    help="Configure the bot to be built and run in Docker.",
)
parser.add_argument(
    "--build",
    dest="build",
    action="store_true",
    required=False,
    help="Build the docker or host files necessary to run the bot.",
)
parser.add_argument(
    "--run", dest="run", action="store_true", required=False, help="Run the bot."
)


dockerfile = """
FROM python:3.10

WORKDIR /mammoth-bot-app

VOLUME [ "/$DEPLOYMENT_ID$_data" ]

ADD cogs/ ./cogs

ADD utils/ ./utils

ADD lib/ ./lib

ADD main.py .

ADD requirements.txt .

ADD settings.json .

ADD token.json .

RUN pip install -r requirements.txt

CMD [ "python", "-u", "./main.py" ]
"""

docker_build = """
docker volume create -d local --name $DEPLOYMENT_ID$_data
docker build -t $DEPLOYMENT_ID$ .
"""

docker_run = """
docker rm --force $DEPLOYMENT_ID$
docker run $AUTO_RESTART$ -d --name=$DEPLOYMENT_ID$ --mount source=$DEPLOYMENT_ID$_data,destination=/$DEPLOYMENT_ID$_data $DEPLOYMENT_ID$
"""

host_build = """
cmd /k "cd /d $CWDIR$\\venv\Scripts & activate.bat & cd /d $CWDIR$ & pip install -r requirements.txt"
"""
host_run = """
cmd /k "cd /d $CWDIR$\\venv\Scripts & activate.bat & cd /d $CWDIR$ & python main.py"
"""

settings = {
    "ownerIDs": [],
    "asyncio_gather": True,
    "caching": True,
    "debugPrinting": True,
    "spammyDebugPrinting": False,
    "dataPath": "",
}

token = {"token": ""}


def main(
    deployment_id,
    auto_restart,
    asyncio_gather,
    caching,
    owner_ids,
    debug_printing,
    spammy_debug_printing,
    bot_token,
    docker_mode,
    build,
    run,
):
    global dockerfile
    global docker_build
    global docker_run
    global host_build
    global host_run
    global settings
    global token

    settings["dataPath"] = f"{'' if docker_mode else '.'}/{deployment_id}_data"
    settings["asyncio_gather"] = asyncio_gather
    settings["caching"] = caching
    settings["ownerIDs"] = owner_ids
    settings["debugPrinting"] = debug_printing
    settings["spammyDebugPrinting"] = spammy_debug_printing

    token["token"] = bot_token

    with open("./settings.json", "w") as w:
        w.write(json.dumps(settings, indent=4))

    with open("./token.json", "w") as w:
        w.write(json.dumps(token, indent=4))

    print("Deployment files generated!")

    if docker_mode:
        dockerfile = dockerfile.replace("$DEPLOYMENT_ID$", deployment_id)

        docker_build = docker_build.replace("$DEPLOYMENT_ID$", deployment_id)

        docker_run = docker_run.replace("$DEPLOYMENT_ID$", deployment_id)
        docker_run = docker_run.replace(
            " $AUTO_RESTART$ ", " --restart=on-failure " if auto_restart else " "
        )

        with open("./dockerfile", "w") as w:
            w.write(dockerfile)

        with open("./build.bat", "w") as w:
            w.write(docker_build)

        with open("./run.bat", "w") as w:
            w.write(docker_run)

        if build:
            print("Building docker image...")

            os.system("build.bat")

            print("Docker image built!")

        if run:
            print("Running docker image...")

            os.system("run.bat")

            print("Docker image running!")
    else:
        host_build = host_build.replace("$CWDIR$", os.getcwd())
        host_run = host_run.replace("$CWDIR$", os.getcwd())

        with open("./build.bat", "w") as w:
            w.write(host_build)

        with open("./run.bat", "w") as w:
            w.write(host_run)

        if build:
            print("Building venv...")

            os.system("build.bat")

            print("Built venv!")
        if run:
            print("Running...")

            os.system("run.bat")

            print("Bot running!")


if __name__ == "__main__":
    args = parser.parse_args()
    main(**vars(args))
