# Minecraft Mod Updater
Automatically Update Mods from CurseForge, Github and Modrinth.

Users only need to prepare a excel file (e.g. `mod整合包.xlsx`) containing all links of each mod, and specify target Minecraft version in `config.yaml`. The program will intellectually search the mod files that match (or close to) the specified game version and download them.

We hope this simple program will help users to conveniently update mods once their game version has been upgraded.

## Usage
First, copy the `config.yaml.sample` file, and edit for your own. The API-KEY of CurseForge, Github and Modrinth are required (as long as your mods need download from these websites).

```sh
cp config.yaml.sample config.sample
# Then, edit config.sample
```

Then, you can run the program. By default, the program will collect file metadata for each mod, and ask user to confirm. After that, the download will be launched.
```sh
python main.py
```

```
usage: main.py [-h] [-c CONFIG] [-y]

Process some integers.

options:
  -h, --help            show this help message and exit
  -c CONFIG, --config CONFIG
                        Path to the configuration file, default is './config.yaml'
  -y, --yes             Download without asking for confirmation
```