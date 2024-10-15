# © 2021-2022 Florian Kantelberg (initOS GmbH)
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
    parser.add_argument("file", default=None, nargs="?", help="File to execute")
    return parser.parse_known_args(args)


def wrapped_console(script_file):
    def console(local_vars):
        local_vars["__name__"] = "__main__"
        with open(script_file, "r", encoding="utf-8") as fp:
            exec(fp.read(), local_vars)

    return console


class RunEnvironment(env.Environment):
    """Class to the environment"""

    def shell(self, args=None):
        """Start an Odoo shell"""
        args, left = load_shell_arguments(args or [])
        if not self._init_odoo():
            return False

        # pylint: disable=C0415,E0401
        from odoo.cli.shell import Shell

        sys.argv = [args.file] + left if args.file else [""]
        shell = Shell()

        if args.file:
            shell.console = wrapped_console(args.file)

        return shell.run(["-c", base.ODOO_CONFIG, "--no-http"])

    def populate(self, args=None):
        if not args:
            args = []

        if not self._init_odoo():
            return False

        # pylint: disable=C0415,E0401
        from odoo.cli.populate import Populate

        return Populate().run(["-c", base.ODOO_CONFIG, *args])

    def start(self, args=None):
        """Start Odoo without wrapper"""
        if not args:
            args = []

        path = self._init_odoo()
        if not path:
            return False

        debugger = self.get(base.SECTION, "debugger")
        debug_cmd = ()
        if debugger == "debugpy":
            utils.info(f"Starting with debugger {debugger}")
            debug_cmd = "-m", "debugpy", "--listen", "0.0.0.0:5678", "--wait-for-client"
        elif debugger == "dev":
            args += ("--dev=all",)

        return utils.call(
            sys.executable,
            *debug_cmd,
            "odoo-bin",
            "-c",
            base.ODOO_CONFIG,
            *args,
            cwd=path,
        )
