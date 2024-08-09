# © 2021-2022 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import argparse
import logging
import os
from fnmatch import fnmatch
from subprocess import PIPE, Popen

_logger = logging.getLogger(__name__)


def get_config_file():
    """Favor a odoo.local.yaml if exists"""
    for file in ["odoo.local.yaml", "odoo.project.yaml"]:
        if os.path.isfile(file):
            return file
    error("No configuration file found.")
    return None


def call(*cmd, cwd=None, pipe=True):
    """Call a subprocess and return the stdout"""
    with Popen(
        cmd,
        cwd=cwd,
        stdout=PIPE if pipe else None,
        universal_newlines=True,
    ) as proc:
        output = proc.communicate()[0]
        if pipe:
            return output.strip() if output else ""
        return proc.returncode


def info(msg, *args):
    """Output a green colored info message"""
    _logger.info(f"\x1b[32m{msg % args}\x1b[0m")


def warn(msg, *args):
    """Output a yellow colored warning message"""
    _logger.warning(f"\x1b[33m{msg % args}\x1b[0m")


def error(msg, *args):
    """Output a red colored error"""
    _logger.error(f"\x1b[31m{msg % args}\x1b[0m")


def check_filters(name, whitelist=None, blacklist=None):
    """Check the name against the whitelist and blacklist"""

    def matches(patterns):
        return [len(pat.replace("*", "")) for pat in patterns if fnmatch(name, pat)]

    # Per default everything is allowed
    if not whitelist and not blacklist:
        return True

    whitelist_matches = matches(whitelist or [])
    blacklist_matches = matches(blacklist or [])

    if whitelist_matches and blacklist_matches:
        # The most specific pattern wins
        return max(whitelist_matches) > max(blacklist_matches)

    return not blacklist_matches


def default_parser(command):
    """Return the common parser options"""
    parser = argparse.ArgumentParser(
        usage=f"%(prog)s {command} [options]",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-c",
        dest="cfg",
        default=get_config_file(),
        help="Configuration file to use. Default: %(default)s",
    )
    return parser


def merge(a, b, *, replace=None):
    """Merges dicts and lists from the configuration structure"""
    if isinstance(a, dict) and isinstance(b, dict):
        if not replace:
            replace = set()

        res = {}
        for key in set(a).union(b):
            if key not in a:
                res[key] = b[key]
            elif key not in b:
                res[key] = a[key]
            elif key in replace:
                res[key] = b[key]
            else:
                res[key] = merge(a[key], b[key], replace=replace)
        return res

    if isinstance(a, list) and isinstance(b, list):
        return a + b

    if isinstance(a, set) and isinstance(b, set):
        return a.union(b)

    return b


def raise_keyboard_interrupt(*a):
    raise KeyboardInterrupt()


def config_logger(log_level=logging.INFO):
    """Configure the loggers for doblib and git_aggregator fully embedding the logs
    of the wrapper into the normal log stream"""
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler = logging.StreamHandler()
    handler.setFormatter(formatter)

    for name, logger in logging.root.manager.loggerDict.items():
        if any(name.startswith(x) for x in ("doblib.", "git_aggregator.")):
            logger.propagate = False
            logger.addHandler(handler)
            logger.setLevel(log_level)


def tobool(x):
    if isinstance(x, str):
        return x.lower() in ("t", "true", "1", "on", "yes", "y")
    return bool(x)


class Version:
    """Class to read and and compare versions. Instances are getting
    passed to the migration scripts"""

    def __init__(self, ver=None):
        if isinstance(ver, Version):
            self.version = ver.version
        elif isinstance(ver, str):
            self.version = tuple(int(x) if x.isdigit() else x for x in ver.split("."))
        elif isinstance(ver, int) and not isinstance(ver, bool):
            self.version = (ver,)
        elif isinstance(ver, (list, tuple)):
            self.version = tuple(ver)
        else:
            self.version = tuple()

    def __str__(self):
        return ".".join(map(str, self.version))

    def __eq__(self, other):
        return self.version == Version(other).version

    def __lt__(self, other):
        return self.version < Version(other).version

    def __le__(self, other):
        return self.version <= Version(other).version

    def __gt__(self, other):
        return self.version > Version(other).version

    def __ge__(self, other):
        return self.version >= Version(other).version

    def __getitem__(self, item):
        return self.version[item]
