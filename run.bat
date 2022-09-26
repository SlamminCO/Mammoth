
docker rm --force swaggy_boi
docker run --restart=on-failure -d --name=swaggy_boi --mount source=swaggy_boi_data,destination=/swaggy_boi_data swaggy_boi
