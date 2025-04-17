import asyncio
import re
import json
import pandas as pd
import os

from logger import get_logger
from utils import CurseForgeSession, GithubSession, ModrinthSession, \
    edit_distance, truncate_with_ellipsis
from typing import Optional, Dict, Any, List, Tuple
from enumcls import VerifyIdStatus, CFModLoaderType, VersionCompareStatus
from mod_file import CurseForgeModFile, GithubModFile, ModrinthModFile
from game_version import check_valid_game_version, compare_game_versions, \
    compare_game_version, fuzzy_compare_game_version

logger = get_logger(__name__)

async def verify_id_consistency(session: CurseForgeSession, mod_id: int, url: str) -> Tuple[VerifyIdStatus, Optional[str]]:
    """
    Verify if the mod ID and file ID are consistent.
    """
    try:
        mod_details = await session.get_mod_details(mod_id)
    except Exception as e:
        logger.debug(f"Error fetching mod details for ID {mod_id}: {e}")
        return VerifyIdStatus.CONNECTIONFAILURE, f"Error fetching mod details for ID {mod_id}: {e}"
    
    try:
        url_from_web = mod_details['data']['links']['websiteUrl'].strip()
    except KeyError as e:
        logger.debug(f"KeyError: {e} for mod ID {mod_id}")
        return VerifyIdStatus.PARSEFAILURE, f"KeyError: {e} for mod ID {mod_id}"
    
    diff = edit_distance(url_from_web, url.strip())
    if diff > 2:
        logger.debug(f"ID consistency check failed for mod URL {mod_id}: {diff} > 2")
        return VerifyIdStatus.INVALID, f"URL consistency check failed for mod ID {mod_id}: {diff} > 2"
    
    return VerifyIdStatus.VERIFIED, None

async def fetch_metadata_for_cfmod(session: CurseForgeSession, mod_id: int, config: Any) -> Dict[str, Any]:
    """
    Fetch metadata for a single mod and return it as a dictionary.
    """
    
    params = {
        'pageSize': '50',
        'index': '0',
        'modLoaderType': CFModLoaderType[config['mod_loader'].upper()].value,
    }
    
    try:
        target_version = config['game_version']
    except KeyError as e:
        logger.debug(e, exc_info=True)
        return {'success': False, 'mod_id': mod_id, 'info': f"KeyError: {e} for mod ID {mod_id}"}
    
    total_count = 0
    try:
        temp_params = params.copy()
        temp_params['gameVersion'] = target_version
        mod_files = await session.get_mod_files(mod_id, params=temp_params)
        
        total_count = mod_files['pagination']['totalCount']
    except KeyError as e:
        logger.debug(e, exc_info=True)    
        return {'success': False, 'mod_id': mod_id, 'info': f"KeyError: {e} for mod ID {mod_id}"}
    except Exception as e:
        logger.debug(e, exc_info=True) 
        return {'success': False, 'mod_id': mod_id, 'info': f"Error fetching metadata for mod ID {mod_id}: {e}"}
    
    if total_count <= 0:
        # No files found for the specified game version, try without game version
        logger.info(f"No files found for mod ID {mod_id} with game version {target_version}, trying without game version.")
        try:
            mod_files = await session.get_mod_files(mod_id, params=params)
            total_count = mod_files['pagination']['totalCount']
        except Exception as e:
            logger.debug(e, exc_info=True)
            return {'success': False, 'mod_id': mod_id, 'info': f"Error fetching metadata for mod ID {mod_id}: {e}"}
        
        temp_params = params.copy()
        latest_found_version = None
        selected_file = None
        last_latest_counter = -1
        
        for start_idx in range(0, total_count, 50):
            idx = start_idx
            temp_params['index'] = str(idx)
            logger.debug(f"Fetching mod files for mod ID {mod_id} with all game versions, page {idx}.")
            
            if start_idx > 0:
                try:
                    mod_files = await session.get_mod_files(mod_id, params=temp_params)
                except Exception as e:
                    logger.debug(e, exc_info=True)
                    return {'success': False, 'mod_id': mod_id, 'info': f"Error fetching metadata for mod ID {mod_id}: {e}"}
            
            if 'data' not in mod_files or len(mod_files['data']) == 0:
                logger.debug(f"No files found for mod ID {mod_id} with game version {target_version}, trying without game version.")
                continue
            
            try:
                file_filtered = list(filter(lambda file: any(map(lambda x : True if check_valid_game_version(x) is not None else False, file['gameVersions'])), mod_files['data']))
                version_status = map(lambda file: compare_game_versions(target_version, file['gameVersions']), file_filtered)
                
                # choose the latest(first) Consistent or OlderMinor version
                for idx, (status, version) in enumerate(version_status):
                    if status == VersionCompareStatus.Consistent or status == VersionCompareStatus.OlderMinor:
                        # logger.debug(f"Found a file for mod ID {mod_id} with game version {version}, index {idx}.")
                        
                        if latest_found_version is None:
                            latest_found_version = version
                            selected_file = file_filtered[idx]
                            last_latest_counter = 0
                        else:
                            s = compare_game_version(version, latest_found_version)
                            if s == VersionCompareStatus.OlderMinor or s == VersionCompareStatus.OlderMajor:
                                latest_found_version = version
                                selected_file = file_filtered[idx]
                                last_latest_counter = 0
                            else:
                                last_latest_counter += 1
                        
                    else:
                        logger.debug(f"File {file_filtered[idx]['id']} for mod ID {mod_id} with game version {version} is not consistent, status: {status}.")
                        if selected_file is not None:
                            last_latest_counter += 1
                    
                    if last_latest_counter >= session.checks_after_latest:
                        logger.debug(f"Found a file for mod ID {mod_id} with game version {latest_found_version}, index {idx}.")
                        # if not selected_file['downloadUrl']:
                        #     return {'success': False, 'mod_id': mod_id, 'info': f"File {file_filtered[idx]['id']} for mod ID {mod_id} with game version {latest_found_version} has no download URL."}
                        return {'success': True, 'mod_id': mod_id, 'file': CurseForgeModFile(latest_found_version, selected_file)}
                
            except Exception as e:
                logger.debug(e, exc_info=True)
                return {'success': False, 'mod_id': mod_id, 'info': f"Error filtering files for mod ID {mod_id}: {e}"}
        
        
        if selected_file:
            logger.debug(f"Found a file for mod ID {mod_id} with game version {latest_found_version}.")
            # if not selected_file['downloadUrl']:
            #     return {'success': False, 'mod_id': mod_id, 'info': f"File {file_filtered[idx]['id']} for mod ID {mod_id} with game version {latest_found_version} has no download URL."}
            return {'success': True, 'mod_id': mod_id, 'file': CurseForgeModFile(latest_found_version, selected_file)}
        else:
            logger.debug(f"No files found for mod ID {mod_id} with game version {target_version}, even though tried with all game versions.")
            return {'success': False, 'mod_id': mod_id, 'info': f"No files found for mod ID {mod_id} with game version {target_version}, even though tried with all game versions."}
        
    else:
        # Files found for the specified game version, find the latest release(if exist) file
        logger.debug(f"Found {total_count} files for mod ID {mod_id} with game version {target_version}.")
        try:
            # Only find the first page of files
            for file in mod_files['data']:
                if file['releaseType'] == 1: # 1 Release, 2 Beta, 3 Alpha
                    logger.debug(f"Found a release file for mod ID {mod_id} with game version {target_version}.")
                    # if not file['downloadUrl']:
                    #     return {'success': False, 'mod_id': mod_id, 'info': f"File {file['id']} for mod ID {mod_id} with game version {target_version} has no download URL."}
                    return {'success': True, 'mod_id': mod_id, 'file': CurseForgeModFile(target_version, file)}
            
            logger.debug(f"No release file found for mod ID {mod_id} with game version {target_version}, return the latest.")
            # if not mod_files['data'][0]['downloadUrl']:
            #     return {'success': False, 'mod_id': mod_id, 'info': f"File {mod_files['data'][0]['id']} for mod ID {mod_id} with game version {target_version} has no download URL."}
            return {'success': True, 'mod_id': mod_id, 'file': CurseForgeModFile(target_version, mod_files['data'][0])}
        except Exception as e:
            logger.debug(e, exc_info=True)
            return {'success': False, 'mod_id': mod_id, 'info': f"Error filtering files for mod ID {mod_id}: {e}"}
            
    return {'success': False, 'mod_id': mod_id, 'info': "Something went wrong."}
    

async def fetch_metadata_for_ghmod(session: GithubSession, repo: str, config: Any) -> Dict[str, Any]:
    """
    Fetch metadata for a single mod from GitHub and return it as a dictionary.
    """
    try:
        target_version = config['game_version']
    except KeyError as e:
        logger.debug(e, exc_info=True)
        return {'success': False, 'mod_id': repo, 'info': f"KeyError: {e} for repo {repo}"}
    
    latest_found_version = None
    selected_file = None
    last_latest_counter = -1
    
    # loop for paging
    page = 1
    while True:
        params = {
            'per_page': 100,
            'page': page,
        }
        
        try:
            releases, link_header = await session.get_release_metadata(repo, params=params)
        except Exception as e:
            logger.debug(e, exc_info=True)
            return {'success': False, 'mod_id': repo, 'info': f"Error fetching metadata for repo {repo}: {e}"}
        
        if not releases or len(releases) == 0:
            break
        
        for release in releases:
            if release['prerelease']:
                logger.debug(f"Skipping pre-release file {release['name']} for repo {repo}.")
                continue
            
            if 'assets' not in release or len(release['assets']) == 0:
                logger.debug(f"No assets found for release {release['name']} for repo {repo}.")
                continue
            
            s, version = fuzzy_compare_game_version(target_version, [release['tag_name'], release['name']])
            if s == VersionCompareStatus.Consistent or s == VersionCompareStatus.OlderMinor:
                # logger.debug(f"Found a file for repo {repo} with detected game version {version}.")
                
                if latest_found_version is None:
                    latest_found_version = version
                    selected_file = release
                    last_latest_counter = 0
                else:
                    s = compare_game_version(version, latest_found_version)
                    if s == VersionCompareStatus.OlderMinor or s == VersionCompareStatus.OlderMajor or \
                        (s == VersionCompareStatus.Consistent and selected_file['prerelease'] == False and release['prerelease']):
                        # if the version is older or the same, but the selected file is a pre-release and the current file is not
                        latest_found_version = version
                        selected_file = release
                        last_latest_counter = 0
                    else:
                        last_latest_counter += 1
            elif selected_file is not None:
                last_latest_counter += 1
                
            if last_latest_counter >= session.checks_after_latest:
                logger.debug(f"Found a file for repo {repo} with detected game version {latest_found_version}.")
                return {'success': True, 'mod_id': repo, 'file': GithubModFile(latest_found_version, selected_file['assets'][0])}
        
        # check if there are more pages
        if link_header is None or 'rel="next"' not in link_header:
            break
        
        page += 1
    
    if selected_file:
        return {'success': True, 'mod_id': repo, 'file': GithubModFile(latest_found_version, selected_file['assets'][0])}
    return {'success': False, 'mod_id': repo, 'info': f"No files found for repo {repo} even though retried with all pages."}

async def fetch_metadata_for_mrmod(session: ModrinthSession, project: str, config: Any) -> Dict[str, Any]:
    """
    Fetch metadata for a single mod from Modrinth and return it as a dictionary.
    """
    try:
        target_version = config['game_version']
    except KeyError as e:
        logger.debug(e, exc_info=True)
        return {'success': False, 'mod_id': project, 'info': f"KeyError: {e} for project {project}"}
    
    try:
        metadata = await session.get_metadata(project)
    except Exception as e:
        logger.debug(e, exc_info=True)
        return {'success': False, 'mod_id': project, 'info': f"Error fetching metadata for project {project}: {e}"}
    
    if metadata is None or len(metadata) == 0:
        return {'success': False, 'mod_id': project, 'info': f"No files found for project {project}."}
    
    
    latest_found_version = None
    selected_file = None
    last_latest_counter = -1
    
    for modrinth_version in metadata:
        if not config['mod_loader'] in modrinth_version['loaders']:
            continue
        if not 'files' in modrinth_version or len(modrinth_version['files']) == 0:
            continue
        if not 'game_versions' in modrinth_version or len(modrinth_version['game_versions']) == 0:
            continue
        if not 'version_type' in modrinth_version or modrinth_version['version_type'] == 'alpha':
            continue
        
        s, version = compare_game_versions(target_version, modrinth_version['game_versions'])
        if s == VersionCompareStatus.Consistent or s == VersionCompareStatus.OlderMinor:
            logger.debug(f"Found a file for project {project} with detected game version {version}.")
            
            if latest_found_version is None:
                latest_found_version = version
                selected_file = modrinth_version
                last_latest_counter = 0
            else:
                s = compare_game_version(version, latest_found_version)
                if s == VersionCompareStatus.OlderMinor or s == VersionCompareStatus.OlderMajor or \
                    (s == VersionCompareStatus.Consistent and selected_file['version_type'] == 'beta' and modrinth_version['version_type'] == 'release'):
                    # if the version is older or the same, but the selected file is a pre-release and the current file is not
                    latest_found_version = version
                    selected_file = modrinth_version
                    last_latest_counter = 0
                else:
                    last_latest_counter += 1
        elif selected_file is not None:
            last_latest_counter += 1
        
        if last_latest_counter >= session.checks_after_latest:
            logger.debug(f"Found a file for project {project} with detected game version {latest_found_version}.")
            return {'success': True, 'mod_id': project, 'file': ModrinthModFile(latest_found_version, selected_file['files'][0])}
    
    if selected_file:
        logger.debug(f"Found a file for project {project} with detected game version {latest_found_version}.")
        return {'success': True, 'mod_id': project, 'file': ModrinthModFile(latest_found_version, selected_file['files'][0])}
    return {'success': False, 'mod_id': project, 'info': f"No files found for project {project} even though retried with versions."}

async def fetch_metadata(df: pd.DataFrame, config: Any) -> Dict[str, Any]:
    """
    Fetch metadata for each mod in the DataFrame and save it to a JSON file.
    """
    # Create output directory if it doesn't exist
    results = [None] * len(df)
    
    # ==========================================
    # Fetch metadata for CurseForge mods
    # ===========================================
    async with CurseForgeSession(config['curseforge']) as session:
        tasks = []
        ignore_set = set()
        
        if session.verify_id_consistency != 'ignore':
            for index, row in df.iterrows():
                if not 'curseforge' in row['地址']:
                    ignore_set.add(index) # Mark as ignore if not a CurseForge mod
                    continue
                
                mod_id = int(row['modId'])
                task = asyncio.create_task(verify_id_consistency(session, mod_id, row['地址']))
                tasks.append(task)
            
            _results = await asyncio.gather(*tasks)
            for index, (status, msg) in enumerate(_results):
                if status != VerifyIdStatus.VERIFIED:
                    logger.warning(f"Row {index} ({df.iloc[index]['名称']}) verification failed: {msg}")
                    if session.verify_id_consistency == 'error':
                        ignore_set.add(index) # Mark as ignore if treat inconsistent IDs as error
                    elif status != VerifyIdStatus.INVALID:
                        ignore_set.add(index) # Mark as ignore if other errors occur

        tasks = []
        index_map = []
        for index, row in df.iterrows():
            if not 'curseforge' in row['地址']:
                continue
            
            if index in ignore_set:
                continue
            
            mod_id = int(row['modId'])
            index_map.append(index)
            task = asyncio.create_task(fetch_metadata_for_cfmod(session, mod_id, config))
            tasks.append(task)
        
        cf_results = await asyncio.gather(*tasks)
    
    for idx, result in zip(index_map, cf_results):
        # print(idx, len(results))
        results[idx] = result
    
    # ============================================
    # Fetch metadata for GitHub mods
    # ============================================
    
    async with GithubSession(config['github']) as session:
        tasks = []
        index_map = []
        pattern = re.compile(r'https?://github\.com/([^/]+)/([^/]+)')
        
        for index, row in df.iterrows():
            if not 'github' in row['地址']:
                continue
            
            mch = pattern.search(row['地址'])
            if not mch:
                logger.debug(f"Invalid GitHub URL: {row['地址']} at row {index}.")
                results[index] = {'success': False, 'mod_id': row['地址'], 'info': f"Invalid GitHub URL."}
                continue
            
            index_map.append(index)
            repo = f"{mch.group(1)}/{mch.group(2)}"
            task = asyncio.create_task(fetch_metadata_for_ghmod(session, repo, config))
            tasks.append(task)
        
        gh_results = await asyncio.gather(*tasks)
    
    for idx, result in zip(index_map, gh_results):
        results[idx] = result
    
    # ============================================
    # Fetch metadata for Modrinth mods
    # ============================================
    
    async with ModrinthSession(config['modrinth']) as session:
        tasks = []
        index_map = []
        
        pattern = re.compile(r'https?://modrinth\.com/mod/([^/]+)')
        
        for index, row in df.iterrows():
            if not 'modrinth' in row['地址']:
                continue
            
            mch = pattern.search(row['地址'])
            if not mch:
                logger.debug(f"Invalid Modrinth URL: {row['地址']} at row {index}.")
                results[index] = {'success': False, 'mod_id': row['地址'], 'info': f"Invalid Modrinth URL."}
                continue
            project = mch.group(1)
            
            index_map.append(index)
            task = asyncio.create_task(fetch_metadata_for_mrmod(session, project, config))
            tasks.append(task)
        
        mr_results = await asyncio.gather(*tasks)
    
    for idx, result in zip(index_map, mr_results):
        results[idx] = result
        
    return results