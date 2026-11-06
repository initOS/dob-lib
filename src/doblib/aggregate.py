# © 2021-2022 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import os
import re
import sys
import threading
import traceback
from multiprocessing import cpu_count
from queue import Empty, Queue

from git_aggregator.config import get_repos
from git_aggregator.main import match_dir
from git_aggregator.repo import Repo
from git_aggregator.utils import ThreadNameKeeper

from . import env, utils

COMMIT_FILE = "dob-commit"
CommitRegex = re.compile(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}")


def commit_file(repo):
    """Path of the file storing the merges of the last successful aggregation"""
    return os.path.join(repo.cwd, ".git", COMMIT_FILE)


def merge_lines(repo):
    """Merges of the repository in the format of the odoo.versions.yaml"""
    return "".join(f"{merge['remote']} {merge['ref']}\n" for merge in repo.merges)


def repo_state(repo):
    """Return why the repository needs an aggregation or None if it's up to date"""
    if not os.path.isdir(os.path.join(repo.cwd, ".git")):
        return "new"

    if not all(CommitRegex.fullmatch(merge["ref"]) for merge in repo.merges):
        return "unpinned"

    try:
        with open(commit_file(repo), encoding="utf-8") as fp:
            content = fp.read()
    except FileNotFoundError:
        return "incomplete"

    return None if content == merge_lines(repo) else "changed"


def aggregate(repo):
    """Aggregate the repository and remember the merges after success"""
    path = commit_file(repo)
    if os.path.isfile(path):
        os.remove(path)

    repo.aggregate()

    if os.path.isdir(os.path.dirname(path)):
        with open(path, "w", encoding="utf-8") as fp:
            fp.write(merge_lines(repo))


def aggregate_repo(repo, args, sem, err_queue, mode=None):
    """Aggregate one repo according to the args"""
    try:
        if not match_dir(repo.cwd, args.dirmatch):
            return

        if mode == "show-all-prs":
            repo.show_all_prs()
        elif mode == "show-closed-prs":
            repo.show_closed_prs()
        else:
            aggregate(repo)
    except Exception:
        err_queue.put_nowait(sys.exc_info())
    finally:
        sem.release()


def load_init_arguments(args):
    parser = utils.default_parser("init")
    parser.add_argument(
        "--no-config",
        dest="config",
        action="store_false",
        default=True,
        help="Skip the bootstrapping of the configuration",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        default=False,
        help="Force the bootstrapping of repositories with local changes. "
        "The local changes are discarded",
    )
    parser.add_argument(
        "-u",
        "--update",
        action="store_true",
        default=False,
        help="Only bootstrap repositories which are new, unpinned, changed in "
        "the odoo.versions.yaml or weren't bootstrapped successfully last time",
    )
    parser.add_argument(
        "-d",
        "--dirmatch",
        dest="dirmatch",
        type=str,
        nargs="?",
        help="Only bootstrap repositories with a matching glob",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        dest="jobs",
        default=cpu_count(),
        type=int,
        help="Number of jobs used for the bootstrapping. Default %(default)s",
    )
    return parser.parse_known_args(args)


def load_aggregate_arguments(args):
    parser = utils.default_parser("aggregate")
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        default=False,
        help="Force the bootstrapping of repositories with local changes. "
        "The local changes are discarded",
    )
    parser.add_argument(
        "-d",
        "--dirmatch",
        dest="dirmatch",
        type=str,
        nargs="?",
        help="Only bootstrap repositories with a matching glob",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        dest="jobs",
        default=cpu_count(),
        type=int,
        help="Number of jobs used for the bootstrapping. Default %(default)s",
    )
    return parser.parse_known_args(args)


class AggregateEnvironment(env.Environment):
    """Class to bootstrap the environment"""

    def _filter_outdated(self, repos, args):
        """Return only the repositories which need an aggregation"""
        result, skipped, reasons = [], 0, {}
        for repo in repos:
            if not match_dir(repo.cwd, args.dirmatch):
                continue

            reason = repo_state(repo)
            if reason is None:
                skipped += 1
            else:
                result.append(repo)
                reasons.setdefault(reason, []).append(os.path.relpath(repo.cwd))

        utils.info("Skipping %s unchanged repositories", skipped)
        for reason, paths in sorted(reasons.items()):
            utils.info("Bootstrapping %s repositories: %s", reason, ", ".join(paths))
        return result

    def _aggregator(self, args, mode=None):
        """Bootstrap the git repositories using git aggregator"""

        # Mostly adapted from the git aggregator main module with integration
        # into the dob structure
        jobs = max(args.jobs, 1)
        threads = []
        sem = threading.Semaphore(jobs)
        err_queue = Queue()

        repos = [
            Repo(**repo_dict)
            for repo_dict in get_repos(self.get("repos", default={}), args.force)
        ]
        if mode is None and getattr(args, "update", False):
            repos = self._filter_outdated(repos, args)

        for r in repos:
            if not err_queue.empty():
                break

            with sem:
                tname = os.path.basename(r.cwd)

                if jobs > 1:
                    t = threading.Thread(
                        target=aggregate_repo,
                        args=(r, args, sem, err_queue, mode),
                    )
                    t.daemon = True
                    t.name = tname
                    threads.append(t)
                    t.start()
                else:
                    with ThreadNameKeeper():
                        threading.current_thread().name = tname
                        aggregate_repo(r, args, sem, err_queue, mode)

        for t in threads:
            t.join()

        if not err_queue.empty():
            while True:
                try:
                    exc_type, exc_obj, exc_trace = err_queue.get_nowait()
                except Empty:
                    break
                traceback.print_exception(exc_type, exc_obj, exc_trace)
            return 1

        return 0

    def init(self, args=None):
        """Initialize the environment using the git-aggregator"""
        args, _ = load_init_arguments(args or [])

        if args.config:
            self.generate_config()

        utils.info("Bootstrapping repositories")
        return self._aggregator(args)

    def aggregate(self, mode=None, args=None):
        """Run additional features of the git-aggregator"""
        args, _ = load_aggregate_arguments(args or [])
        return self._aggregator(args, mode=mode)
