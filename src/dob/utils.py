# © 2021 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import argparse
import os
from subprocess import PIPE, Popen


def get_config_file():
    """ Favor a odoo.local.yaml if exists """
    for file in ["odoo.local.yaml", "odoo.project.yaml"]:
        if os.path.isfile(file):
            return file
    error("No configuration file found.")
    return None


def call(*cmd, cwd=None, pipe=True):
    """ Call a subprocess and return the stdout """
    proc = Popen(
        cmd,
        cwd=cwd,
        stdout=PIPE if pipe else None,
        universal_newlines=True,
    )
    output = proc.communicate()[0]
    if pipe:
        return output.strip() if output else ""
    return proc.returncode


def info(msg, *args):
    """ Output a green colored info message """
    print(f"\x1b[32m{msg % args}\x1b[0m")


def warn(msg, *args):
    """ Output a yellow colored warning message """
    print(f"\x1b[33m{msg % args}\x1b[0m")


def error(msg, *args):
    """ Output a red colored error """
    print(f"\x1b[31m{msg % args}\x1b[0m")


def default_parser(command):
    """ Return the common parser options """
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
    """ Merges dicts and lists from the configuration structure """
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
