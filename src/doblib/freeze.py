# © 2021-2022 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import argparse
import os
import sys

import yaml

from . import base, env, utils


def load_freeze_arguments(args):
    parser = argparse.ArgumentParser(
        usage="%(prog)s freeze [options]",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-c",
        dest="cfg",
        default=utils.get_config_file(),
        help="Configuration file to use. Default: %(default)s",
    )
    parser.add_argument(
        "--mode",
        choices=("all", "ask", "skip"),
        default="ask",
        help="Mode of the freeze with\n"
        "`all` .. Freeze all and don't ask\n"
        "`skip` .. Skip existing files\n"
        "`ask` .. Ask if a file would be overwritten",
    )
    parser.add_argument(
        "--no-packages",
        dest="packages",
        action="store_false",
        default=True,
        help="Skip the packages",
    )
    parser.add_argument(
        "--no-repos",
        dest="repos",
        action="store_false",
        default=True,
        help="Skip the repositories",
    )
    return parser.parse_known_args(args)


class FreezeEnvironment(env.Environment):
    """Class to freeze the system"""

    def _freeze_mode(self, file, mode="ask"):
        """Return true if the file should be written/created"""
        if not os.path.isfile(file):
            return True

        if mode == "skip":
            return False

        if mode == "ask":
            answer = input(f"Do you want to overwrite the {file}? [y/N] ")
            if answer.lower() != "y":
                return False

        return True

    def _freeze_packages(self, file, mode="ask"):
        """Freeze the python packages in the versions.txt"""
        if self._freeze_mode(file, mode):
            utils.info("Freezing packages")
            versions = utils.call(sys.executable, "-m", "pip", "freeze")
            with open(file, "w+", encoding="utf-8") as fp:
                fp.write(versions)

    def _freeze_repositories(self, file, mode="ask"):
        """Freeze the repositories"""

        # Get the default merges dict from the configuration
        version = self.get(base.SECTION, "version", default="0.0")
        default_merges = self.get(
            base.SECTION,
            "repo",
            "merges",
            default=[f"origin {version}"],
        )

        # Get the used remotes and commits from the repositoriey
        commits = {}
        for path, repo in self.get("repos", default={}).items():
            # This will return all branches with "<remote> <commit>" syntax
            output = utils.call(
                "git",
                "branch",
                "-va",
                "--format=%(refname) %(objectname)",
                cwd=path,
            )
            remotes = dict(line.split() for line in output.splitlines())

            # Aggregate the used commits from each specified merge
            tmp = []
            for entry in repo.get("merges", default_merges):
                name = f"refs/remotes/{entry.replace(' ', '/')}"
                if name in remotes:
                    tmp.append(f"{entry.split()[0]} {remotes[name]}")
                else:
                    tmp.append(entry)

            if tmp:
                commits[path] = {"merges": tmp}

        if not commits:
            return

        # Output the suggestion in a proper format to allow copy & paste
        if self._freeze_mode(file, mode):
            utils.info("Freezing repositories")
            with open(file, "w+", encoding="utf-8") as fp:
                fp.write(yaml.dump({"repos": commits}))

    def freeze(self, args=None):
        """Freeze the python packages in the versions.txt"""
        args, _ = load_freeze_arguments(args or [])

        if args.packages:
            self._freeze_packages("versions.txt", args.mode)

        if args.repos:
            self._freeze_repositories("odoo.versions.yaml", args.mode)
