import aiohttp
import asyncio
import json
import os
import time
import aiohttp
from logger import get_logger
from typing import Any, Optional, Dict

logger = get_logger(__name__)

class BaseSession:
    def __init__(self, config: Dict):
        self.api_key = config['api_key']
        self.base_url = config['api_url']
        self.cache_dir = config.get('cache_dir', './.cache')
        self.cache_expire = config.get('cache_expire', 1) # default to 1 day
        self.session = None
        self.headers = {}
        
        assert self.api_key, "API key is required"
        assert self.base_url, "Base URL is required"
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession(
            base_url=self.base_url,
            headers=self.headers
        )
        return self
    
    async def __aexit__(self, exc_type, exc, tb):
        await self.session.close()
        self.session = None
    
    async def get(self, url: str, params: Optional[Dict] = None) -> Dict:
        async with self.session.get(url, params=params) as response:
            if response.status != 200:
                raise Exception(f"Error fetching data: {response.status}")
            ret = await response.json()
            return ret, response.headers.copy()
    
    async def get_with_cache(self, url: str, params: Optional[Dict] = None) -> Dict:
        # build cache filename using url and params
        url_param = ('?' + '&'.join([f'{k}={v}' for k, v in params.items()])) if params else ''
        
        cache_file = f"{self.base_url}{url}{url_param}.json"
        cache_file = cache_file.replace(":", "_").replace("/", "_").replace("?", "_")
        cache_file = os.path.join(self.cache_dir, cache_file)
        
        # check if cache file exists and is not expired
        if os.path.exists(cache_file):
            cache_time = os.path.getmtime(cache_file)
            if (time.time() - cache_time) < (self.cache_expire * 24 * 3600):
                logger.debug(f"Cache hit for {cache_file}")
                with open(cache_file, 'r', encoding='utf-8') as f:
                    # read the link header from the cache file (github specific)
                    link_header = f.readline().strip()
                    if link_header.startswith("Link: "):
                        link_header = link_header[6:]
                    else:
                        link_header = None
                        f.seek(0)
                    return json.load(f), {'Link': link_header}
        
        async with self.session.get(url, params=params) as response:
            if response.status != 200:
                raise Exception(f"Error fetching data: {response.status}")
            res = await response.json()
            # save response to cache file
            with open(cache_file, 'w', encoding='utf-8') as f:
                link_header = response.headers.get('Link', None)
                if link_header:
                    f.write("Link: " + link_header)
                    f.write('\n')
                json.dump(res, f, indent=4, ensure_ascii=False)
            return res, response.headers.copy()


class CurseForgeSession(BaseSession):
    def __init__(self, config: Dict):
        super().__init__(config)
        
        self.verify_id_consistency = config.get('verify_id_consistency', 'ignore')
        self.verify_file_hashes = config.get('verify_file_hashes', 'ignore')
        self.checks_after_latest = config.get('checks_after_latest', 5)
        self.headers = {
            "x-api-key": self.api_key,
            "Accept": "application/json"
        }
        
        os.makedirs(self.cache_dir, exist_ok=True)
        
        assert self.verify_id_consistency in ['ignore', 'warn', 'error'], "verify_id_consistency must be one of ['ignore', 'warn', 'error']"
        assert self.verify_file_hashes in ['ignore', 'warn', 'error'], "verify_file_hashes must be one of ['ignore', 'warn', 'error']"

    async def get_mod_details(self, mod_id: int) -> Dict:
        url = f"mods/{mod_id}"
        ret = await self.get_with_cache(url)
        return ret[0]

    async def get_mod_files(self, mod_id: int, params: Optional[Dict] = None) -> Dict:
        url = f"mods/{mod_id}/files"
        ret = await self.get_with_cache(url, params)
        return ret[0]
    
    async def get_mod_file_download_url(self, mod_id: int, file_id: int) -> Dict:
        url = f"mods/{mod_id}/files/{file_id}/download-url"
        ret = await self.get_with_cache(url)
        return ret[0]

class GithubSession(BaseSession):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.checks_after_latest = config.get('checks_after_latest', 5)
        self.headers = {
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Authorization: Bearer {self.api_key}',
            'X-GitHub-Api-Version': '2022-11-28'
        }
        os.makedirs(self.cache_dir, exist_ok=True)
    
    async def get_release_metadata(self, owner_repo: str, params: Optional[Dict] = None) -> Dict:
        url = f"repos/{owner_repo}/releases"
        ret = await self.get_with_cache(url, params)
        return ret[0], ret[1].get('Link', None)

class ModrinthSession(BaseSession):
    def __init__(self, config: Dict):
        super().__init__(config)
        self.checks_after_latest = config.get('checks_after_latest', 5)
        self.headers = {
            'Accept': 'application/json',
            'Authorization': self.api_key,
        }
        os.makedirs(self.cache_dir, exist_ok=True)
    
    async def get_metadata(self, project_name: str) -> Dict:
        url = f"project/{project_name}/version"
        ret = await self.get_with_cache(url)
        return ret[0]

# tool function: compute edit distance
def edit_distance(s1: str, s2: str) -> int:
    """Compute the edit distance between two strings."""
    if len(s1) < len(s2):
        return edit_distance(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]

def truncate_with_ellipsis(text: Any, max_length: int) -> str:
    str_text = str(text)
    if len(str_text) > max_length:
        return str_text[:max_length - 3] + "..."
    else:
        return str_text.ljust(max_length)

async def main():
    import yaml
    with open('./config.yaml', 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    async with CurseForgeSession(config['curseforge']) as session:
        mod_id = 433760
        file_id = 6356224
        mod_details = await session.get_mod_details(mod_id)
        print(mod_details)
        mod_details = await session.get_mod_file_download_url(mod_id, file_id)
        print(mod_details)

if __name__ == '__main__':
    # print(edit_distance("kitten", "sitting"))
    asyncio.run(main())
