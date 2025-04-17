from typing import Optional, Dict
import os

from logger import get_logger

logger = get_logger(__name__)

class ModFile:
    def __init__(self, 
                 file_name: str,
                 file_website: str,
                 file_size: int,
                 download_url: str,
                 game_verion: str,
                 file_data: Dict):
        self.file_name = file_name
        self.file_website = file_website
        self.file_size = file_size
        self.download_url = download_url
        self.game_version = game_verion
        self.file_data = file_data
    
    def get_download_entry(self, config) -> Dict:
        raise NotImplementedError("This method should be implemented in subclasses")

class CurseForgeModFile(ModFile):
    def __init__(self, game_version: str, file_data: Dict):
        download_url = file_data.get('downloadUrl')
        if not download_url:
            logger.warning(f"File data does not contain downloadUrl: {file_data}, will deduct from fileId, may not work.")
            file_id = file_data.get('id', 0)
            seg_1, seg_2 = file_id // 1000, file_id % 1000
            download_url = f"https://edge.forgecdn.net/files/{seg_1}/{seg_2}/{file_data['fileName']}"
        
        super().__init__(
            file_name=file_data['fileName'],
            file_website='CurseForge',
            file_size=file_data['fileLength'],
            download_url=download_url,
            game_verion=game_version,
            file_data=file_data
        )
    
    def get_download_entry(self, config):
        return {
            'url' : self.download_url,
            'headers': {
                'Authorization': config['curseforge']['api_key'],
            },
            'save_path': os.path.join(config['output_dir'], self.file_name),
        }

class GithubModFile(ModFile):
    def __init__(self, game_version: str, file_data: Dict):
        super().__init__(
            file_name=file_data['name'],
            file_website='Github',
            file_size=file_data['size'],
            download_url=file_data['url'],
            game_verion=game_version,
            file_data=file_data
        )
    
    def get_download_entry(self, config):
        ret = {
            'url': self.download_url,
            'headers': {
                "Accept": "application/octet-stream",
                "Authorization": f"Bearer {config['github']['api_key']}",
                'X-GitHub-Api-Version': '2022-11-28'
            },
            'save_path': os.path.join(config['output_dir'], self.file_name),
        }
        # logger.debug(f"Github download url: {ret}")
        return ret

class ModrinthModFile(ModFile):
    def __init__(self, game_version: str, file_data: Dict):
        super().__init__(
            file_name=file_data['filename'],
            file_website='Modrinth',
            file_size=file_data['size'],
            download_url=file_data['url'],
            game_verion=game_version,
            file_data=file_data
        )
    
    def get_download_entry(self, config):
        return {
            'url': self.download_url,
            'headers': {
                'Authorization': config['modrinth']['api_key'],
            },
            'save_path': os.path.join(config['output_dir'], self.file_name),
        }
    