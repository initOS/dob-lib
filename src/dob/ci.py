# © 2021 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import glob
import os
import shutil
import sys

import isort
import pytest

from . import base, env, utils

CI = ("black", "eslint", "flake8", "isort", "prettier", "pylint")


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
    """ Class to run tests on the environment """

    def _ci_black(self, options, args, paths):
        """ Run black """
        cmd = [sys.executable, "-m", "black"]

        if not options.fix:
            cmd += ["--check"]

        return utils.call(*cmd, *args, *paths, pipe=False)

    def _ci_eslint(self, options, args, paths):
        """ Run eslint if tool is available """
        executable = shutil.which("eslint")
        if not executable:
            utils.error("eslint is not installed")
            return 1

        cmd = ["eslint", "--no-error-on-unmatched-pattern"]
        if options.fix:
            cmd.append("--fix")

        return utils.call(*cmd, *args, *paths, pipe=False)

    def _ci_flake8(self, options, left, paths):
        """ Run flake8 tests """
        return utils.call(sys.executable, "-m", "flake8", *left, *paths, pipe=False)

    def _ci_isort(self, options, args, paths):
        """ Run isort """

        cmd = [sys.executable, "-m", "isort"]
        if not options.fix:
            cmd.append("--check")

        if utils.Version(isort.__version__) < (5,):
            cmd.append("--recursive")

        return utils.call(*cmd, *args, *paths, pipe=False)

    def _ci_prettier(self, options, args, paths):
        """ """
        executable = shutil.which("prettier")
        if not executable:
            utils.error("prettier is not installed")
            return 1

        paths = [f"{path}/**/*.js" for path in paths]
        if not any(glob.glob(p, recursive=True) for p in paths):
            return 0

        cmd = ["prettier"]
        if options.fix:
            cmd.append("--write")

        return utils.call(*cmd, *args, *paths, pipe=False)

    def _ci_pylint(self, options, args, paths):
        """ Run pylint tests for Odoo """
        for path in paths:
            args.extend(glob.glob(f"{path}/**/*.py", recursive=True))

        cmd = [sys.executable, "-m", "pylint"]
        if os.path.isfile(".pylintrc"):
            cmd.append("--rcfile=.pylintrc")

        return utils.call(*cmd, *args, pipe=False)

    def ci(self, ci, args=None):
        """ Run CI tests """
        args, left = load_ci_arguments(args or [])

        # Always include this script in the tests
        paths = self.get("odoo", "addons_path", default=[])
        func = getattr(self, f"_ci_{ci}", None)
        if ci in CI and callable(func):
            return func(args, left, paths)

        utils.error(f"Unknown CI {ci}")
        return 1

    def test(self, args=None):
        """ Run tests """
        if not args:
            args = []

        if not self._init_odoo():
            return False

        # pylint: disable=C0415,E0401
        import odoo
        from odoo.tools import config

        # Append needed parameter
        if self.get(base.SECTION, "coverage"):
            for path in self.get("odoo", "addons_path", default=[]):
                args.extend([f"--cov={path}", path])

            args += ["--cov-report=html", "--cov-report=term"]

        # Load the odoo configuration
        with odoo.api.Environment.manage():
            config.parse_config(["-c", base.ODOO_CONFIG])
            odoo.cli.server.report_configuration()
            # Pass the arguments to pytest
            sys.argv = sys.argv[:1] + args
            result = pytest.main()
            if result and result != pytest.ExitCode.NO_TESTS_COLLECTED:
                return result

            return 0
