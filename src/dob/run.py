# © 2021 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import argparse
import sys

from . import base, env, utils


def load_shell_arguments(args):
    parser = argparse.ArgumentParser(
        usage="%(prog)s shell [options]",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "-c",
        dest="cfg",
        default=utils.get_config_file(),
        help="Configuration file to use. Default: %(default)s",
    )
    parser.add_argument("file", nargs="?", help="File to execute")
    return parser.parse_known_args(args)


class RunEnvironment(env.Environment):
    """ Class to the environment """

    def shell(self, args=None):
        """ Start an Odoo shell """
        args, left = load_shell_arguments(args or [])
        if not self._init_odoo():
            return False

        # pylint: disable=C0415,E0401
        from odoo.cli.shell import Shell

        if args.file:
            sys.stdin = open(args.file, "r")
            sys.argv = [args.file] + left
        else:
            sys.argv = [""]

        shell = Shell()
        return shell.run(["-c", base.ODOO_CONFIG, "--no-http"])

    def start(self, args=None):
        """ Start Odoo without wrapper """
        if not args:
            args = []

        path = self._init_odoo()
        if not path:
            return False

        cmd = sys.executable, "odoo-bin", "-c", base.ODOO_CONFIG
        return utils.call(*cmd, *args, cwd=path)
