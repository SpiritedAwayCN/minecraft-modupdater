from enum import IntEnum

class VerifyIdStatus(IntEnum):
    """Enum for VerifyModid status."""
    VERIFIED = 0
    UNVERIFIED = 1
    INVALID = 2
    CONNECTIONFAILURE = 3
    PARSEFAILURE = 4

class MetadataFetchStatus(IntEnum):
    """Enum for MetadataFetch status."""
    SUCCESS = 0
    FAILURE = 1
    CONNECTIONFAILURE = 2
    PARSEFAILURE = 3

class VersionCompareStatus(IntEnum):
    """Enum for VersionCompare status."""
    Consistent = 0
    OlderMinor = 1
    OlderMajor = 2
    NewerMinor = 3
    NewerMajor = 4
    InvalidVersion = 5
    
class CFModLoaderType(IntEnum):
    """Enum for CurseForge Mod Loader Type."""
    ANY = 0
    FORGE = 1
    CAULDRON = 2
    LITE_LOADER = 3
    FABRIC = 4

class CFFileHashType(IntEnum):
    """Enum for CurseForge File Hash Type."""
    SHA1 = 1
    MD5 = 2