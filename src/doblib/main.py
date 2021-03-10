# © 2021 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import argparse
import sys

from . import utils
from .action import ActionEnvironment
from .bootstrap import BootstrapEnvironment
from .ci import CI, CIEnvironment
from .env import Environment
from .freeze import FreezeEnvironment
from .module import ModuleEnvironment
from .run import RunEnvironment


def load_arguments(args):
    """ Parse the command line options """
    choices = (
        "a",
        "action",
        "c",
        "config",
        "f",
        "freeze",
        "i",
        "init",
        "r",
        "run",
        "s",
        "shell",
        "t",
        "test",
        "u",
        "update",
    )

    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    base = parser.add_argument_group("Basic")
    base.add_argument(
        "command",
        metavar="command",
        nargs="?",
        help=f"Command to use. Possible choices: "
        f"a(ction), c(onfig), f(reeze), i(nit), r(un), s(hell), t(est), u(pdate), "
        f"{', '.join(CI)}",
        choices=sorted(choices + CI),
    )
    base.add_argument(
        "-c",
        dest="cfg",
        default=utils.get_config_file(),
        help="Configuration file to use. Default: %(default)s",
    )
    return parser.parse_known_args(args)


def main(args=None):
    args = args or sys.argv[1:]

    # Don't parse the `help` on the first level if a command is given
    show_help = "-h" in args or "--help" in args
    args = [x for x in args if x not in ("-h", "--help")]
    args, left = load_arguments(args)

    if show_help:
        left.append("--help")

    if args.command in ("c", "config"):
        # Show the configuration of the environment
        print(Environment(args.cfg).config(left))
    elif args.command in ("f", "freeze"):
        # Freeze the environment
        sys.exit(FreezeEnvironment(args.cfg).freeze(left))
    elif args.command in ("i", "init"):
        # Bootstrap the environment
        sys.exit(BootstrapEnvironment(args.cfg).init(left))
    elif args.command in ("s", "shell"):
        # Start a shell in the environment
        sys.exit(RunEnvironment(args.cfg).shell(left))
    elif args.command in ("r", "run"):
        # Start the environment
        sys.exit(RunEnvironment(args.cfg).start(left))
    elif args.command in ("t", "test"):
        # Run unit tests in the environment
        sys.exit(CIEnvironment(args.cfg).test(left))
    elif args.command in ("flake8", "pylint", "eslint", "isort", "black", "prettier"):
        # Run tests on the environment
        sys.exit(CIEnvironment(args.cfg).ci(args.command, left))
    elif args.command in ("u", "update"):
        # Update the modules of the environment
        sys.exit(ModuleEnvironment(args.cfg).update(left))
    elif args.command in ("a", "action"):
        # Run actions in the environment
        sys.exit(ActionEnvironment(args.cfg).apply_action(left))
    elif show_help:
        load_arguments(["--help"])
    else:
        utils.error("Unknown command")
        load_arguments(["--help"])


if __name__ == "__main__":
    main()
