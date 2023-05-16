# -*- coding: utf-8 -*-
# © 2021 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import glob
import os
import sys
from fnmatch import fnmatch

import isort
import pytest

from . import (
    base,
    env,
    utils,
)

CI = ("eslint", "flake8", "isort", "prettier", "pylint")


def load_ci_arguments(args):
    parser = utils.default_parser("ci")
    parser.add_argument(
        "--fix",
        action="store_true",
        default=False,
        help="Write the fixes back if supported by the tool",
    )
    return parser.parse_known_args(args)


class CIEnvironment(env.Environment):
    """Class to run tests on the environment"""

    def _ci_eslint(self, options, args, paths, ignores):
        """Run eslint if tool is available"""
        executable = utils.which("eslint")
        if not executable:
            utils.error("eslint is not installed")
            return 1

        cmd = ["eslint", "--no-error-on-unmatched-pattern"]
        if options.fix:
            cmd.append("--fix")

        for pattern in ignores:
            cmd += ["--ignore-pattern", pattern]

        cmd.extend(args)
        cmd.extend(paths)
        return utils.call(cmd, pipe=False)

    def _ci_flake8(self, options, args, paths, ignores):
        """Run flake8 tests"""
        cmd = [sys.executable, "-m", "flake8"]
        if ignores:
            cmd.append("--extend-exclude=" + ",".join(ignores))

        cmd.extend(args)
        cmd.extend(paths)
        return utils.call(
            cmd,
            pipe=False,
        )

    def _ci_isort(self, options, args, paths, ignores):
        """Run isort"""

        cmd = ["isort"]
        if not options.fix:
            cmd.extend(("--check", "--diff"))

        if utils.Version(isort.__version__) < (5,):
            cmd.append("--recursive")

        for pattern in ignores:
            cmd += ["--skip-glob", "*/{}".format(pattern)]
            cmd += ["--skip-glob", "*/{}/*".format(pattern)]
            cmd += ["--skip-glob", "{}/*".format(pattern)]

        if ignores:
            cmd.append("--filter-files")

        cmd.extend(args)
        cmd.extend(paths)
        return utils.call(cmd, pipe=False)

    def _ci_prettier(self, options, args, paths, ignores):
        """ """
        executable = utils.which("prettier")
        if not executable:
            utils.error("prettier is not installed")
            return 1

        files = []
        for path in paths:
            files.extend(utils.recursive_glob(path, "*.js"))

        files = list(
            filter(
                lambda path: not any(
                    fnmatch(path, "*/{}".format(pattern))
                    or fnmatch(path, "*/{}/*".format(pattern))
                    or fnmatch(path, "{}/*".format(pattern))
                    for pattern in ignores
                ),
                files,
            )
        )

        if not files:
            return 0

        cmd = ["prettier"]
        if options.fix:
            cmd.append("--write")

        cmd.extend(args)
        cmd.extend(files)
        return utils.call(cmd, pipe=False)

    def _ci_pylint(self, options, args, paths, ignores):
        """Run pylint tests for Odoo"""
        files = []
        for path in paths:
            files.extend(utils.recursive_glob(path, "*.csv"))
            files.extend(utils.recursive_glob(path, "*.py"))
            files.extend(utils.recursive_glob(path, "*.xml"))

        files = list(
            filter(
                lambda path: not any(
                    fnmatch(path, "*/{}".format(pattern))
                    or fnmatch(path, "*/{}/*".format(pattern))
                    or fnmatch(path, "{}/*".format(pattern))
                    for pattern in ignores
                ),
                files,
            )
        )

        if not files:
            return 0

        cmd = [sys.executable, "-m", "pylint"]
        if os.path.isfile(".pylintrc"):
            cmd.append("--rcfile=.pylintrc")

        cmd.extend(args)
        cmd.extend(files)
        return utils.call(cmd, pipe=False)

    def ci(self, ci, args=None):
        """Run CI tests"""
        args, left = load_ci_arguments(args or [])

        # Always include this script in the tests
        paths = self.get(["odoo", "addons_path"], default=[])
        ignores = self.get(["bootstrap", "blacklist"], default=[])
        func = getattr(self, "_ci_{}".format(ci), None)
        if ci in CI and callable(func):
            return func(args, left, paths, ignores)

        utils.error("Unknown CI {}".format(ci))
        return 1

    def test(self, args=None):
        """Run tests"""
        if not args:
            args = []

        if not self._init_odoo():
            return False

        # pylint: disable=C0415,E0401
        try:
            from odoo.cli import server
            from odoo.tools import config
        except ImportError:
            from openerp.cli import server
            from openerp.tools import config

        # Append needed parameter
        if self.get(base.SECTION, "coverage"):
            for path in self.get(["odoo", "addons_path"], default=[]):
                args.extend(["--cov={}".format(path), path])

            args += ["--cov-report=html", "--cov-report=term"]

        # Load the odoo configuration
        with self._manage():
            config.parse_config(["-c", base.ODOO_CONFIG])
            server.report_configuration()
            # Pass the arguments to pytest
            sys.argv = sys.argv[:1] + args
            result = pytest.main()
            if result and result != 5:
                return result

            return 0
