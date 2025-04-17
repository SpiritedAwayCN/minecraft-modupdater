import re
from typing import Optional, Tuple, Dict, List
from enumcls import VersionCompareStatus

def check_valid_game_version(game_version: str) -> Optional[List[int]]:
    """
    Check if the game version is valid.
    """
    
    ids = game_version.split('.')
    if len(ids) < 2 or len(ids) > 3:
        return None
    
    try:
        ids = [int(i) for i in ids]
    except ValueError:
        return None
    
    if ids[0] != 1:
        return None
    
    return ids

def compare_game_version(version1: List[int] | str, version2: List[int] | str) -> VersionCompareStatus:
    """
    Compare two game versions.
    """
    
    if isinstance(version1, str):
        version1 = check_valid_game_version(version1)
        if version1 is None:
            return VersionCompareStatus.InvalidVersion
    if isinstance(version2, str):
        version2 = check_valid_game_version(version2)
        if version2 is None:
            return VersionCompareStatus.InvalidVersion
    
    if version1 == version2:
        return VersionCompareStatus.Consistent
    
    if version1[1] == version2[1]:
        if len(version1) == 2:
            version1.append(0)
        if len(version2) == 2:
            version2.append(0)
        return VersionCompareStatus.OlderMinor if version1[2] > version2[2] else VersionCompareStatus.NewerMinor
    
    return VersionCompareStatus.OlderMajor if version1[1] > version2[1] else VersionCompareStatus.NewerMajor

def compare_game_versions(version1: List[int] | str, version2_list: List[str]) -> Tuple[VersionCompareStatus, Optional[str]]:
    """
    Compare a game version with a list of game versions.
    """
    
    if isinstance(version1, str):
        version1 = check_valid_game_version(version1)
        if version1 is None:
            return VersionCompareStatus.InvalidVersion
    
    final_res = VersionCompareStatus.InvalidVersion
    version_res = None
    
    for version2 in version2_list:
        result = compare_game_version(version1, version2)
        if int(result) < int(final_res):
            final_res = result
            version_res = version2
        elif int(result) == int(final_res) and result != VersionCompareStatus.InvalidVersion:
            if version_res is None or int(compare_game_version(version_res, version2)) >= VersionCompareStatus.NewerMinor:
                final_res = result
                version_res = version2
        if final_res == VersionCompareStatus.Consistent:
            break
    
    return final_res, version_res

def fuzzy_compare_game_version(version: str, names: str | List[str]) -> Tuple[VersionCompareStatus, Optional[str]]:
    """
    Fuzzy find the game version in a string.
    """
    
    if isinstance(names, str):
        names = [names]
    
    pattern = re.compile(r'(?<![.\d])1\.(\d+)(?:\.(\d+)(?!\.))?(?:-pre)?')
    
    final_res = VersionCompareStatus.InvalidVersion
    version_res = None

    version = check_valid_game_version(version)
    if version is None:
        return final_res, version_res
    
    for name in names:
        for match in re.finditer(pattern, name):
            res = compare_game_version(version, match.group())
            if int(res) < int(final_res):
                final_res = res
                version_res = match.group()
            elif int(res) == int(final_res) and res != VersionCompareStatus.InvalidVersion:
                if version_res is None or int(compare_game_version(version_res, match.group())) >= VersionCompareStatus.NewerMinor:
                    final_res = res
                    version_res = match.group()
            if final_res == VersionCompareStatus.Consistent:
                break
        if final_res == VersionCompareStatus.Consistent:
            break

    return final_res, version_res

if __name__ == '__main__':
    print(compare_game_version('1.21', '1.21.1'))