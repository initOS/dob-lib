# © 2021 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import glob
import os
import shutil
import sys
from fnmatch import fnmatch

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
    """Class to run tests on the environment"""

    def _ci_black(self, options, args, paths, ignores):
        """Run black"""
        cmd = [sys.executable, "-m", "black"]

        # Replace pattern matching with regex
        ignores = [pattern.replace("*", ".*").replace("?", ".") for pattern in ignores]

        # Append black default excludes
        ignores = ignores + [
            "\\.git",
            "\\.hg",
            "\\.mypy_cache",
            "\\.tox",
            "\\.venv",
            "_build",
            "buck-out",
            "build",
            "dist",
        ]

        exclude = "(" + "|".join(ignores) + ")"
        cmd += ["--exclude", exclude]

        if not options.fix:
            cmd += ["--check", "--diff"]

        return utils.call(*cmd, *args, *paths, pipe=False)

    def _ci_eslint(self, options, args, paths, ignores):
        """Run eslint if tool is available"""
        executable = shutil.which("eslint")
        if not executable:
            utils.error("eslint is not installed")
            return 1

        cmd = ["eslint", "--no-error-on-unmatched-pattern"]
        if options.fix:
            cmd.append("--fix")

        for pattern in ignores:
            cmd += ["--ignore-pattern", pattern]

        return utils.call(*cmd, *args, *paths, pipe=False)

    def _ci_flake8(self, options, left, paths, ignores):
        """Run flake8 tests"""
        cmd = [sys.executable, "-m", "flake8"]
        if ignores:
            cmd.append("--extend-exclude=" + ",".join(ignores))

        return utils.call(
            *cmd,
            *left,
            *paths,
            pipe=False,
        )

    def _ci_isort(self, options, args, paths, ignores):
        """Run isort"""

        cmd = [sys.executable, "-m", "isort"]
        if not options.fix:
            cmd.extend(("--check", "--diff"))

        if utils.Version(isort.__version__) < (5,):
            cmd.append("--recursive")

        for pattern in ignores:
            cmd += ["--skip-glob", f"*/{pattern}"]
            cmd += ["--skip-glob", f"*/{pattern}/*"]
            cmd += ["--skip-glob", f"{pattern}/*"]

        if ignores:
            cmd.append("--filter-files")

        return utils.call(*cmd, *args, *paths, pipe=False)

    def _ci_prettier(self, options, args, paths, ignores):
        """ """
        executable = shutil.which("prettier")
        if not executable:
            utils.error("prettier is not installed")
            return 1

        files = []
        for path in paths:
            files.extend(glob.glob(f"{path}/**/*.js", recursive=True))

        files = list(
            filter(
                lambda path: not any(
                    fnmatch(path, f"*/{pattern}")
                    or fnmatch(path, f"*/{pattern}/*")
                    or fnmatch(path, f"{pattern}/*")
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

        return utils.call(*cmd, *args, *files, pipe=False)

    def _ci_pylint(self, options, args, paths, ignores):
        """Run pylint tests for Odoo"""
        files = []
        for path in paths:
            files.extend(glob.glob(f"{path}/**/*.csv", recursive=True))
            files.extend(glob.glob(f"{path}/**/*.py", recursive=True))
            files.extend(glob.glob(f"{path}/**/*.xml", recursive=True))

        files = list(
            filter(
                lambda path: not any(
                    fnmatch(path, f"*/{pattern}")
                    or fnmatch(path, f"*/{pattern}/*")
                    or fnmatch(path, f"{pattern}/*")
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

        return utils.call(*cmd, *args, *files, pipe=False)

    def _ci_paths(self):
        return self.get("odoo", "addons_path", default=[]) + self.get(
            "bootstrap", "ci_path", default=[]
        )

    def ci(self, ci, args=None):
        """Run CI tests"""
        args, left = load_ci_arguments(args or [])

        # Always include this script in the tests
        ignores = self.get("bootstrap", "blacklist", default=[])
        func = getattr(self, f"_ci_{ci}", None)
        if ci in CI and callable(func):
            return func(args, left, self._ci_paths(), ignores)

        utils.error(f"Unknown CI {ci}")
        return 1

    def test(self, args=None):
        """Run tests"""
        if not args:
            args = []

        if not self._init_odoo():
            return False

        # pylint: disable=C0415,E0401
        import odoo
        from odoo.tools import config

        # Append needed parameter
        if self.get(base.SECTION, "coverage"):
            for path in self._ci_paths():
                args.extend([f"--cov={path}", path])

            args += ["--cov-report=html", "--cov-report=term"]

        # Load the odoo configuration
        with self._manage():
            config.parse_config(["-c", base.ODOO_CONFIG])
            odoo.cli.server.report_configuration()
            # Pass the arguments to pytest
            sys.argv = sys.argv[:1] + args
            result = pytest.main()
            if result and result != pytest.ExitCode.NO_TESTS_COLLECTED:
                return result

            return 0
