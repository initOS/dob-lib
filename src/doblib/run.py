# -*- coding: utf-8 -*-
# © 2021-2022 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import argparse
import os
import sys

from . import (
    base,
    env,
    utils,
)


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
    """Class to the environment"""

    def _shell(self, args):
        try:
            import odoo
            from odoo.cli import server
            from odoo.tools import config
        except ImportError:
            import openerp as odoo
            from openerp.cli import server
            from openerp.tools import config

        config.parse_config(["-c", base.ODOO_CONFIG, "--no-xmlrpc"])
        server.report_configuration()

        db_name = config["db_name"]
        with self._manage(), self.env(db_name, rollback=True) as env:
            local_vars = {
                "odoo": odoo,
                "openerp": odoo,
                "self": env.user,
                "env": env,
            }

            if args.file:
                local_vars["__name__"] = "__main__"
                with open(args.file, "r") as fp:
                    exec(fp.read(), local_vars)
            else:
                from IPython import start_ipython
                for name, value in sorted(local_vars.items()):
                    print("{}: {}".format(name, value))

                start_ipython(argv=[], user_ns=local_vars)

        return 0

    def shell(self, args=None):
        """Start an Odoo shell"""
        args, left = load_shell_arguments(args or [])
        if not self._init_odoo():
            return False

        # pylint: disable=C0415,E0401
        try:
            from odoo.cli.shell import Shell
        except ImportError:
            return self._shell(args)

        if args.file:
            sys.stdin = open(args.file, "r")
            sys.argv = [args.file] + left
        else:
            sys.argv = [""]

        shell = Shell()
        return shell.run(["-c", base.ODOO_CONFIG, "--no-xmlrpc"])

    def start(self, args=None):
        """Start Odoo without wrapper"""
        if not args:
            args = []

        path = self._init_odoo()
        if not path:
            return False

        debugger = self.get([base.SECTION, "debugger"])
        debug_cmd = ()
        if debugger == "debugpy":
            utils.info("Starting with debugger %s", debugger)
            debug_cmd = "-m", "debugpy", "--listen", "0.0.0.0:5678", "--wait-for-client"
        elif debugger == "dev":
            args += ("--dev=all",)

        print(path)
        if os.path.isfile(os.path.join(path, "odoo-bin")):
            cmd = ["odoo-bin", "-c", base.ODOO_CONFIG]
        else:
            cmd = ["openerp-server", "-c", base.ODOO_CONFIG]

        return utils.call(
            [sys.executable] + list(debug_cmd) + cmd + list(args),
            cwd=path,
        )
