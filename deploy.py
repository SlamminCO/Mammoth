import json
import argparse
import os


DEFAULT_DEPLOYMENT_ID = "mammoth_bot"


parser = argparse.ArgumentParser()
parser.add_argument("--deploy-id", dest="deployment_id", type=str, required=False)
parser.add_argument(
    "--auto-restart", dest="auto_restart", action="store_true", required=False
)
parser.add_argument(
    "--owner-ids", dest="owner_ids", action="extend", nargs="+", type=int
)
parser.add_argument(
    "--print-debug", dest="debug_printing", action="store_true", required=False
)
parser.add_argument(
    "--print-debug-spam",
    dest="spammy_debug_printing",
    action="store_true",
    required=False,
)
parser.add_argument("--token", dest="bot_token", type=str, required=False)
parser.add_argument("--build", dest="build", action="store_true", required=False)
parser.add_argument("--run", dest="run", action="store_true", required=False)


dockerfile = """
FROM python:3.10

WORKDIR /mammoth-bot-app

VOLUME [ "/$DEPLOYMENT_ID$_data" ]

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
"""

docker_build = """
docker volume create -d local --name $DEPLOYMENT_ID$_data
docker build -t $DEPLOYMENT_ID$ .
"""

docker_run = """
docker rm --force $DEPLOYMENT_ID$
docker run $AUTO_RESTART$ -d --name=$DEPLOYMENT_ID$ --mount source=$DEPLOYMENT_ID$_data,destination=/$DEPLOYMENT_ID$_data $DEPLOYMENT_ID$
"""

settings = {
    "ownerIDs": [],
    "debugPrinting": True,
    "spammyDebugPrinting": False,
    "dataPath": "",
}

token = {"token": ""}


def get_deployment_id():
    deployment_id = input(f"Deployment ID? (Default: {DEFAULT_DEPLOYMENT_ID}): ")

    while deployment_id.find(" ") != -1:
        print("\nDeployment ID cannot contain spaces.\n")

        deployment_id = input(f"Deployment ID? (Default: {DEFAULT_DEPLOYMENT_ID}): ")

    deployment_id = deployment_id if deployment_id else DEFAULT_DEPLOYMENT_ID

    return deployment_id


def get_auto_restart():
    while (
        auto_restart := input(
            f"Should the container auto-restart on failure? (y/n): "
        ).lower()
    ) not in ["y", "n", "yes", "no"]:
        print("\nInvalid response.\n")

    return " --restart=on-failure " if auto_restart in ["y", "yes"] else " "


def get_owner_ids():
    owner_id_list = []

    while True:
        owner_id = input(
            f"Please provide a discord user ID to give access to owner commands: "
        )

        try:
            owner_id = int(owner_id)
        except:
            print("\nID must be an integer.\n")
            continue

        owner_id_list.append(owner_id)

        add_more_prompt = input(
            f"Would you like to add another ID to the owner list? (y/n): "
        ).lower()

        while add_more_prompt not in ["y", "n", "yes", "no"]:
            print("\nInvalid response.\n")

            add_more_prompt = input(
                f"Would you like to add another ID to the owner list? (y/n): "
            ).lower()

        if add_more_prompt in ["n", "no"]:
            break

    return owner_id_list


def get_debug_printing():
    while (
        debug_printing := input(
            f"Should debug info be printed to the logs? (y/n): "
        ).lower()
    ) not in ["y", "n", "yes", "no"]:
        print("\nInvalid response.\n")

    return True if debug_printing in ["y", "yes"] else False


def get_spammy_debug_printing():
    while (
        debug_printing := input(
            f"Should additional (spammy) debug info be printed to the logs? (y/n): "
        ).lower()
    ) not in ["y", "n", "yes", "no"]:
        print("\nInvalid response.\n")

    return True if debug_printing in ["y", "yes"] else False


def get_token():
    return input("Please provide your bot token: ")


def main(
    deployment_id,
    auto_restart,
    owner_ids,
    debug_printing,
    spammy_debug_printing,
    bot_token,
    build,
    run,
):
    print(
        deployment_id,
        auto_restart,
        owner_ids,
        debug_printing,
        spammy_debug_printing,
        bot_token,
    )

    global dockerfile
    global docker_build
    global docker_run
    global settings
    global token

    if deployment_id is None:
        deployment_id = get_deployment_id()

    dockerfile = dockerfile.replace("$DEPLOYMENT_ID$", deployment_id)
    docker_build = docker_build.replace("$DEPLOYMENT_ID$", deployment_id)
    docker_run = docker_run.replace("$DEPLOYMENT_ID$", deployment_id)

    settings["dataPath"] = f"/{deployment_id}_data"

    if auto_restart is None:
        auto_restart = get_auto_restart()
    else:
        auto_restart = " --restart=on-failure " if auto_restart else " "

    docker_run = docker_run.replace(" $AUTO_RESTART$ ", auto_restart)

    if owner_ids is None:
        owner_ids = get_owner_ids()

    settings["ownerIDs"] = owner_ids

    if debug_printing is None:
        debug_printing = get_debug_printing()

    settings["debugPrinting"] = debug_printing

    if spammy_debug_printing is None:
        spammy_debug_printing = get_spammy_debug_printing()

    settings["spammyDebugPrinting"] = spammy_debug_printing

    if bot_token is None:
        bot_token = get_token()

    token["token"] = bot_token

    with open("./dockerfile", "w") as w:
        w.write(dockerfile)

    with open("./build.bat", "w") as w:
        w.write(docker_build)

    with open("./run.bat", "w") as w:
        w.write(docker_run)

    with open("./settings.json", "w") as w:
        w.write(json.dumps(settings, indent=4))

    with open("./token.json", "w") as w:
        w.write(json.dumps(token, indent=4))

    print("Deployment files generated!")

    if build:
        print("Building docker image...")

        os.system("build.bat")

        print("Docker image built!")
    if run:
        print("Running docker image...")

        os.system("run.bat")

        print("Docker image running!")


if __name__ == "__main__":
    args = parser.parse_args()
    main(**vars(args))
