# © 2021 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import os
import sys
import threading
import traceback
from multiprocessing import cpu_count
from queue import Empty, Queue

from git_aggregator.config import get_repos
from git_aggregator.main import match_dir
from git_aggregator.repo import Repo
from git_aggregator.utils import ThreadNameKeeper

from . import base, env, utils


def aggregate_repo(repo, args, sem, err_queue):
    """ Aggregate one repo according to the args """
    try:
        if not match_dir(repo.cwd, args.dirmatch):
            return
        repo.aggregate()
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
        help="Force the bootstrapping of repositories by stashing",
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


class BootstrapEnvironment(env.Environment):
    """ Class to bootstrap the environment """

    def _bootstrap(self, args):
        """ Bootstrap the git repositories using git aggregator """

        # Mostly adapted from the git aggregator main module with integration
        # into the dob structure
        jobs = max(args.jobs, 1)
        threads = []
        sem = threading.Semaphore(jobs)
        err_queue = Queue()

        default = self.get(base.SECTION, "repo", default={})
        repos = {
            key: utils.merge(default, value, replace=["merges"])
            for key, value in self.get("repos", default={}).items()
        }
        for repo_dict in get_repos(repos, args.force):
            if not err_queue.empty():
                break

            sem.acquire()
            r = Repo(**repo_dict)
            tname = os.path.basename(repo_dict["cwd"])

            if jobs > 1:
                t = threading.Thread(
                    target=aggregate_repo,
                    args=(r, args, sem, err_queue),
                )
                t.daemon = True
                t.name = tname
                threads.append(t)
                t.start()
            else:
                with ThreadNameKeeper():
                    threading.current_thread().name = tname
                    aggregate_repo(r, args, sem, err_queue)

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

    def init(self, args=None):
        """ Initialize the environment """
        args, _ = load_init_arguments(args or [])

        if args.config:
            self.generate_config()

        utils.info("Bootstrapping repositories")
        return self._bootstrap(args)
