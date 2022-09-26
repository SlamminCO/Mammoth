import os

FILES_TO_REMOVE = ["./dockerfile", "./build.bat", "./run,bat", "settings.json", "token.json"]

if __name__ == "__main__":
    for file in FILES_TO_REMOVE:
        if os.path.exists(file):
            os.remove(file)

    print("Deployment files cleaned!")