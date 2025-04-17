import aiohttp
import asyncio
import os
from tqdm.asyncio import tqdm_asyncio

from utils import truncate_with_ellipsis
from typing import Dict, Any, Optional, List
from logger import get_logger

logger = get_logger(__name__)

class AsyncDownloader:
    def __init__(self, max_concurrent: int = 5):
        """
        Initialize the downloader with concurrent control
        
        :param max_concurrent: Maximum simultaneous downloads
        """
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.progress_bars = {}  # Tracking progress bars for each task

    async def _download_single(
        self,
        url: str,
        headers: dict,
        save_path: str,
        max_retries: int = 3
    ):
        """Single file download implementation with resume support"""
        temp_path = f"{save_path}.tmp"
        downloaded_size = 0
        progress_bar = None
        
        if os.path.exists(save_path):
            return RuntimeError(f"File already exists: {save_path}")
        
        async with self.semaphore:
            try:
                
                # Check for existing temp file
                if os.path.exists(temp_path):
                    downloaded_size = os.path.getsize(temp_path)
                    headers["Range"] = f"bytes={downloaded_size}-"
                
                # logger.debug(f"Downloading {url} {headers} to {temp_path}...")
            
                for attempt in range(max_retries):
                    try:
                        async with aiohttp.ClientSession(headers=headers) as session:
                            async with session.get(url) as response:
                                # Handle response status
                                if response.status == 416:  # Range not satisfiable
                                    os.remove(temp_path)
                                    continue

                                response.raise_for_status()

                                # Get total file size
                                content_range = response.headers.get("Content-Range")
                                if content_range:
                                    total_size = int(content_range.split("/")[1])
                                else:
                                    total_size = int(response.headers.get("Content-Length", 0)) + downloaded_size

                                # Initialize/resume progress bar
                                progress_bar = self.progress_bars.get(save_path)
                                if not progress_bar:
                                    progress_bar = tqdm_asyncio(
                                        total=total_size,
                                        initial=downloaded_size,
                                        unit='B',
                                        unit_scale=True,
                                        desc=truncate_with_ellipsis(os.path.basename(save_path), 30),
                                        leave=False
                                    )
                                    self.progress_bars[save_path] = progress_bar

                                # Open file in append mode if resuming
                                mode = "ab" if downloaded_size > 0 else "wb"
                                with open(temp_path, mode) as f:
                                    async for chunk in response.content.iter_any():
                                        f.write(chunk)
                                        progress_bar.update(len(chunk))

                                # Rename temp file when complete
                                os.rename(temp_path, save_path)
                                progress_bar.close()
                                del self.progress_bars[save_path]
                                return True

                    except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                        # Cleanup on final attempt failure
                        if attempt == max_retries - 1:
                            if os.path.exists(temp_path):
                                os.remove(temp_path)
                            progress_bar.close()
                            del self.progress_bars[save_path]
                            raise
                        await asyncio.sleep(2 ** attempt)

            except Exception as e:
                logger.debug(e, exc_info=True)
                # Ensure cleanup on unexpected errors
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                if save_path in self.progress_bars:
                    self.progress_bars[save_path].close()
                    del self.progress_bars[save_path]
                return e

    async def download(
        self,
        download_tasks: List[Dict | None],
        overall_progress: bool = True
    ):
        """
        Batch download entry point
        
        :param download_tasks: List of download tasks (dictionaries with url/headers/save_path)
        :param overall_progress: Show master progress bar
        """
        # Create download tasks
        tasks = [self._download_single(**task) for task in download_tasks if task]

        # Add master progress bar
        if overall_progress:
            return await tqdm_asyncio.gather(
                *tasks,
                desc="Overall Progress",
                unit="files",
                unit_scale=True,
                leave=True
            )

        # Execute and gather results
        return await asyncio.gather(*tasks)

# Usage Example
async def main():
    downloader = AsyncDownloader(max_concurrent=5)
    
    tasks = [
        {
            "url": "https://api.github.com/repos/gnembon/fabric-carpet/releases/assets/244607575",
            "headers": {
                "Accept": "application/octet-stream",
                "Authorization": "Bearer x",
                'X-GitHub-Api-Version': '2022-11-28'
            },
            "save_path": "./.debug_output/fabric-carpet-25w15a-1.4.170+v250408.jar"
        },
        {
            "url": "https://api.github.com/repos/sakura-ryoko/malilib/releases/assets/245860210",
            "headers": {
                "Accept": "application/octet-stream",
                "Authorization": "Bearer x",
                'X-GitHub-Api-Version': '2022-11-28'
            },
            "save_path": "./.debug_output/malilib-fabric-1.21.5-0.24.0-sakura.8.jar"
        },
        {
            "url": "https://edge.forgecdn.net/files/6382/47/fabric-api-0.119.8%2b25w14craftmine.jar",
            "headers": {},
            "save_path": "./.debug_output/fabric-api-0.119.8+25w14craftmine.jar"
        }
    ]

    results = await downloader.download(tasks)

    # Process results
    for result, task in zip(results, tasks):
        if isinstance(result, Exception):
            print(f"Download failed for {task['save_path']}: {str(result)}")

if __name__ == "__main__":
    asyncio.run(main())