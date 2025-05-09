import sys
import os
import re
import string
import logging
from crccheck.crc import Crc15
from pathlib import Path
from TipiConfig import TipiConfig
from unidecode import unidecode
from ti_files import ti_files
from ti_files.BasicFile import basicSuffixes
from tinames.NativeFlags import *

# Transform a name supplied by the 4A into our storage path

logger = logging.getLogger(__name__)

tipi_config = TipiConfig.instance()

TIPI_DIR = "/home/tipi/tipi_disk"

WILDCARD = '#?'


def __driveMapping(key):
    path = tipi_config.get(key)

    if path == "" or path is None:
        return None

    if path == ".":
        return TIPI_DIR

    path = "/".join([x.replace("/", ".") for x in path.split(".")])
    path = TIPI_DIR + "/" + path
    return path


def __cs1Mapping():
    path = tipi_config.get("CS1_FILE")

    if path == "" or path is None:
        return None

    path = "/".join([x.replace("/", ".") for x in path.split(".")])
    path = TIPI_DIR + "/" + path
    return path


def __scanForVolume(volume):
    # If it is literally DSK.TIPI. act like it matches DSK0.
    if volume == 'TIPI':
        return TIPI_DIR

    # next check if one of the mapped drives has the name
    disks = ("DSK1_DIR", "DSK2_DIR", "DSK3_DIR", "DSK4_DIR", "DSK5_DIR", "DSK6_DIR", "DSK7_DIR", "DSK8_DIR", "DSK9_DIR",)
    for disk in disks:
        path = __driveMapping(disk)
        if path != None and path.endswith("/" + volume):
            return path

    # None of the Disks are mapped to this volume...
    # fall back to top level directories
    path = os.path.join(TIPI_DIR, volume)
    if os.path.exists(path):
        return path
    return None


def nativeFlags(devname):
    parts = str(devname).split(".")
    startpart = 1
    if parts[0] == "DSK":
        startpart = 2
    if parts[0] == "CS1":
        return ""
    flags = parts[startpart]
    if flags in NATIVE_FLAGS:
        return flags
    target_path = devnameToLocal(devname)
    if not target_path:
       return ""
    return nativeTextDir(target_path)


def nativeTextDir(target_path):
    if not os.path.isfile(target_path):
        target_path += '/'
    # check if any of text_dirs is a prefix of target_path
    native_text_dirs = [f"TIPI.{a.strip()}" for a in tipi_config.get("NATIVE_TEXT_DIRS").split(',') if a]
    if native_text_dirs and len(native_text_dirs):
        text_dirs = [devnameToLocal(dir) for dir in native_text_dirs]
        if True in [(f"{td}/" in target_path) for td in text_dirs]:
            return TEXT_WINDOWS
    return ""


def isDriveMapped(devname):
    return devnameToLocal(devname) is not None


def devnameToLocal(devname, prog=False):
    parts = str(devname).split(".")
    path = None
    startpart = 1
    if parts[0] == "TIPI":
        path = TIPI_DIR
    elif parts[0] == "DSK0":
        path = TIPI_DIR
    elif parts[0] in ("DSK1", "DSK2", "DSK3", "DSK4", "DSK5", "DSK6", "DSK7", "DSK8", "DSK9",):
        path = __driveMapping(f"{parts[0]}_DIR")
    elif parts[0] == "DSK":
        path = __scanForVolume(parts[1])
        startpart = 2
    elif parts[0] == "CS1":
        path = __cs1Mapping()

    if path == None or path == "":
        logger.debug("no path matched")
        return None

    # skip native file modes when finding linux path
    if len(parts) > startpart and parts[startpart] in NATIVE_FLAGS:
        startpart = startpart + 1

    for part in parts[startpart:]:
        if part != "":
            logger.debug("matching path part: %s", part)
            if part == parts[-1]:
                path += "/" + findpath(path, part, prog=prog)
            else:
                path += "/" + findpath(path, part, dir=True)
            logger.debug("building path: %s", path)

    path = str(path).strip()
    logger.debug("%s -> %s", devname, path)

    return path


# Transform long host filename to 10 character TI filename
def asTiShortName(name):
    parts = name.split("/")
    lastpart = parts[len(parts) - 1]
    name = lastpart.replace(".", "/")
    return encodeName(name)


def encodeName(name):
    bytes = bytearray(name, 'utf-8')
    if len(bytes) == len(name) and len(name) <= 10:
        return name
    else:
        crc = Crc15.calc(bytearray(name, 'utf-8'))
        prefix = unidecode(name)[:6]
        shortname = f'{prefix}`{baseN(crc, 36)}'
        return shortname


def baseN(num, b, numerals="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"):
    return ((num == 0) and numerals[0]) or (
        baseN(num // b, b, numerals).lstrip(numerals[0]) + numerals[num % b]
    )


# Use the context of actual files to transform TI file names to possibly
# long TI names


def findpath(path, part, prog=False, dir=False):
    part = part.replace("/", ".").replace("\\", ".")
    # if the file actually exists (or dir) then use literal name
    if os.path.exists(os.path.join(path, part)):
        return part
    else:
        # if it doesn't exist, and the part has a short name hash, then search
        # for a os match
        if re.match("^[^ ]{6}[`][0-9A-Z]{3}$", part):
            # Now we must find all the names in 'path' and see which one we
            # should load.
            candidates = list(
                filter(lambda x: asTiShortName(x) == part, os.listdir(path))
            )
            if candidates:
                return candidates[0]
        if WILDCARD in part:
            # return the first item that matches the wildcard expression
            globpart = part.replace(WILDCARD, "*")
            candidates = [p for p in Path(path).glob(globpart)]
            if candidates:
                candidates.sort()
                for item in candidates:
                    if dir:
                        # item must be a directory... 
                        if os.path.isdir(os.path.join(path, item.name)):
                            return item.name
                    elif prog:
                        # item must be a Program image, or convertable type
                        if isProgramLike(os.path.join(path, item.name)):
                            return item.name
                    else:
                        return candidates[0].name
    return part


def isProgramLike(path):
    if os.path.exists(path):
        type = ti_files.get_file_type(path)
        if type == "PRG" or (type == "native" and path.lower().endswith(basicSuffixes)):
            return True
    return False


def local2tipi(localpath):
    """ transform a unix local path to a ti path relative to TIPI. """
    if localpath.startswith(TIPI_DIR + "/"):
        idx = len(TIPI_DIR) + 1
        tipart = localpath[idx:]
        return tipart.replace("/", ".")
    else:
        return ""
