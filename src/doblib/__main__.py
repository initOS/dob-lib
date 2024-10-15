# © 2021 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import argparse
import logging
import sys

from . import utils
from .action import ActionEnvironment
from .aggregate import AggregateEnvironment
from .ci import CI, CIEnvironment
from .env import Environment
from .freeze import FreezeEnvironment
from .migrate import MigrateEnvironment, load_migrate_arguments
from .module import ModuleEnvironment
from .run import RunEnvironment
from .utils import config_logger

LOG_LEVELS = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARN,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
    "off": None,
}


def load_arguments(args):
    """Parse the command line options"""
    choices = (
        "a",
        "action",
        "c",
        "config",
        "f",
        "freeze",
        "g",
        "generate",
        "help",
        "i",
        "init",
        "m",
        "migrate",
        "populate",
        "r",
        "run",
        "s",
        "shell",
        "t",
        "test",
        "u",
        "update",
        "show-all-prs",
        "show-closed-prs",
    )

    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    base = parser.add_argument_group("Basic")
    base.add_argument(
        "command",
        metavar="command",
        nargs="?",
        help=f"Command to use. Possible choices: "
        f"a(ction): Execute pre-defined actions on the database\n"
        f"c(onfig): Output the aggregated configuration or parts of it\n"
        f"f(reeze): Freeze the packages and repositories\n"
        f"g(enerate): Generate the Odoo configuration. This is also part "
        f"of `init` and `update`\n"
        f"i(nit): Initialize the repositories\n"
        f"m(igrate): Run OpenUpgrade to migrate to a new Odoo version\n"
        f"populate: Run Odoo populate to fill the database with data\n"
        f"r(un): Run the Odoo server\n"
        f"s(hell): Enter the interactive python shell\n"
        f"t(est): Execute the unittests\n"
        f"u(pdate): Run the update and migration process\n"
        f"{', '.join(CI)}: Run the specific CI tool\n"
        f"show-all-prs: show GitHub pull requests in merge sections. Such "
        f"pull requests are identified as having a github.com remote and "
        f"a refs/pull/NNN/head ref in the merge section\n"
        f"show-closed-prs: show pull requests that are not open anymore",
        choices=sorted(choices + CI),
    )
    base.add_argument(
        "-c",
        dest="cfg",
        default=utils.get_config_file(),
        help="Configuration file to use. Default: %(default)s",
    )
    base.add_argument(
        "--logging",
        action="store",
        choices=list(LOG_LEVELS),
        default="info",
        help="Logging level. Default: %(default)s",
    )
    return parser.parse_known_args(args)


def main(args=None):
    args = args or sys.argv[1:]

    # Don't parse the `help` on the first level if a command is given
    show_help = "-h" in args or "--help" in args
    args = [x for x in args if x not in ("-h", "--help")]
    args, left = load_arguments(args)

    log_level = LOG_LEVELS.get(args.logging, logging.INFO)
    if args.command in ("c", "config"):
        # Show the configuration of the environment (skip all non-ERROR logging)
        config_logger(logging.ERROR)
        print(Environment(args.cfg).config(left))
        return

    if log_level:
        config_logger(log_level)

    if show_help:
        left.append("--help")

    if args.command in ("g", "generate"):
        # Regenerate the configuration file
        sys.exit(Environment(args.cfg).generate_config())
    elif args.command in ("f", "freeze"):
        # Freeze the environment
        sys.exit(FreezeEnvironment(args.cfg).freeze(left))
    elif args.command in ("i", "init"):
        # Bootstrap the environment
        sys.exit(AggregateEnvironment(args.cfg).init(left))
    elif args.command in ("s", "shell"):
        # Start a shell in the environment
        sys.exit(RunEnvironment(args.cfg).shell(left))
    elif args.command == "populate":
        # Populate the database
        sys.exit(RunEnvironment(args.cfg).populate(left))
    elif args.command in ("r", "run"):
        # Start the environment
        sys.exit(RunEnvironment(args.cfg).start(left))
    elif args.command in ("t", "test"):
        # Run unit tests in the environment
        sys.exit(CIEnvironment(args.cfg).test(left))
    elif args.command in CI:
        # Run tests on the environment
        sys.exit(CIEnvironment(args.cfg).ci(args.command, left))
    elif args.command in ("u", "update"):
        # Update the modules of the environment
        sys.exit(ModuleEnvironment(args.cfg).update(left))
    elif args.command in ("a", "action"):
        # Run actions in the environment
        sys.exit(ActionEnvironment(args.cfg).apply_action(left))
    elif args.command in ("m", "migrate"):
        # Run Odoo migration using OpenUpgrade
        migrate_args, left = load_migrate_arguments(left)
        migrate_cfg = f"odoo.migrate.{migrate_args.version[0]}.yaml"
        sys.exit(MigrateEnvironment(migrate_cfg).migrate(migrate_args))
    elif args.command in ("show-all-prs", "show-closed-prs"):
        sys.exit(AggregateEnvironment(args.cfg).aggregate(args.command, left))
    elif show_help:
        load_arguments(["--help"])
    else:
        utils.error("Unknown command")
        load_arguments(["--help"])


if __name__ == "__main__":
    main()
