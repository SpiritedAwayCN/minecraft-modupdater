import yaml
import argparse
import os
import pandas as pd
import asyncio
from workflow import fetch_metadata
from utils import truncate_with_ellipsis
from downloader import AsyncDownloader
from logger import get_logger

logger = get_logger(__name__)


def load_yaml(file_path):
    """Load a YAML file and return its content as a dictionary."""
    with open(file_path, 'r', encoding='utf-8') as file:
        config = yaml.safe_load(file)
    return config

def get_parser():
    """Set up the argument parser."""
    parser = argparse.ArgumentParser(description="Process some integers.")
    parser.add_argument('-c', '--config', type=str, default='./config.yaml', help='Path to the configuration file')
    parser.add_argument('-y', '--yes', action='store_true', help='Download without asking for confirmation')
    return parser

def print_metadata_results(results, df, target_version, no_comfirm):
    COLUMNS = {
        "modName": 30,
        "success": 8,
        "site": 12,
        "version": 10,
        "fileSize": 10,
        "fileName": 22,
    }
    separator = "-" * (sum(COLUMNS.values()) + len(COLUMNS) - 1)
    header = ["{:<{width}}".format(k, width=v) for k, v in COLUMNS.items()]
    print(separator)
    print(" ".join(header))
    print(separator)
    
    version_consist_n, version_mismatch_n = 0, 0
    for idx, status in enumerate(results):
        if status is None:
            row = [
                truncate_with_ellipsis(df['名称'][idx], COLUMNS["modName"]),
                truncate_with_ellipsis('False', COLUMNS["success"]),
                'Entry has been ignored due to not being a CurseForge/Github/Modrinth mod',
            ]
        elif status['success']:
            row = [
                truncate_with_ellipsis(df['名称'][idx], COLUMNS["modName"]),
                truncate_with_ellipsis(status['success'], COLUMNS["success"]),
                truncate_with_ellipsis(status['file'].file_website, COLUMNS["site"]),
                truncate_with_ellipsis(status['file'].game_version, COLUMNS["version"]),
                truncate_with_ellipsis(status['file'].file_size, COLUMNS["fileSize"]),
                status['file'].file_name
            ]
            if status['file'].game_version == target_version:
                version_consist_n += 1
            else:
                version_mismatch_n += 1
        else:
            row = [
                truncate_with_ellipsis(df['名称'][idx], COLUMNS["modName"]),
                truncate_with_ellipsis(status['success'], COLUMNS["success"]),
                status['info']
            ]
        print(" ".join(row))
        
    failed_n = len(results) - version_consist_n - version_mismatch_n
    print(separator)
    
    print(f"Total mods: {len(results)}, attempt to match game version: {target_version}.")
    print(f"{version_consist_n} mod(s) are successfully matched with the game version.")
    print(f"{version_mismatch_n} mod(s) are not perfectly matched, but find alternative files (see above).")
    print(f"{failed_n} mod(s) failed to find any files (see above), will be ignored.")
    print()
    
    while not no_comfirm:
        choice = input(f"{version_consist_n + version_mismatch_n} mod(s) to download, continue? (y/n)")
        if choice.lower() == 'y':
            break
        elif choice.lower() == 'n':
            print("Exiting...")
            exit(0)


def print_download_results(entries, results):
    succ_count, fail_count = 0, 0
    for entry, result in zip(entries, results):
        if isinstance(result, Exception):
            logger.warning(f"Download failed for {entry['save_path']}: {str(result)}")
            fail_count += 1
        else:
            succ_count += 1
    logger.info(f"Successfully downloaded {succ_count} file(s), failed to download {fail_count} file(s).")

async def main():
    parser = get_parser()
    args = parser.parse_args()

    # Check if the config file exists
    if not os.path.exists(args.config):
        print(f"Configuration file {args.config} does not exist.")
        return

    # Load the configuration file
    config = load_yaml(args.config)

    # Print the loaded configuration
    print("Loaded configuration:")
    print(config)
    
    # Read the xlsx file
    xlsx_file = config.get('modlist_file')
    if not xlsx_file or not os.path.exists(xlsx_file):
        print(f"Excel file {xlsx_file} does not exist.")
        return
    df = pd.read_excel(xlsx_file)
    
    # Step 1: Get file metadata for each mod
    results = await fetch_metadata(df, config)
    print_metadata_results(results, df, config['game_version'], args.yes)
    
    # Step 2: Download the files
    os.makedirs(config['output_dir'], exist_ok=True)
    
    downloader = AsyncDownloader(max_concurrent=config['max_downloads'])
    download_entries = [entry['file'].get_download_entry(config) for entry in results if entry['success']]
    download_results = await downloader.download(download_entries)
    print_download_results(download_entries, download_results)
    logger.info("Mods saved to " + config['output_dir'])

if __name__ == "__main__":
    asyncio.run(main())