# © 2021 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import glob
import os
import shutil
import signal
import sys
from fnmatch import fnmatch

import pytest

from . import base, env, utils

CI = ("black", "eslint", "flake8", "isort", "prettier", "pylint", "ruff", "ruff-format")


def load_ci_arguments(args):
    parser = utils.default_parser("ci")
    parser.add_argument(
        "--fix",
        action="store_true",
        default=False,
        help="Write the fixes back if supported by the tool",
    )
    parser.add_argument(
        "--no-http",
        action="store_true",
        default=False,
        help="Don't start the HTTP server for pytest tests. Useful to speed up tests",
    )
    parser.add_argument(
        "--no-force-threaded",
    )
    return parser.parse_known_args(args)


class CIEnvironment(env.Environment):
    """Class to run tests on the environment"""

    def _ci_black(self, options, args, paths, ignores):
        """Run black"""
        try:
            # pylint: disable=C0415,W0611
            import black
        except ImportError:
            utils.error("black is not installed")
            return 1

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
        try:
            # pylint: disable=C0415,E0401,W0611
            import flake8
        except ImportError:
            utils.error("flake8 is not installed")
            return 1

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
        try:
            # pylint: disable=C0415,E0401,W0611
            import isort
        except ImportError:
            utils.error("isort is not installed")
            return 1

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
        """Run prettier on supported files"""
        executable = shutil.which("prettier")
        if not executable:
            utils.error("prettier is not installed")
            return 1

        files = set()

        extensions = self.get(
            base.SECTION, "prettier", "extension", default=["js", "xml"]
        )
        for path in paths:
            for ext in extensions:
                files.update(glob.glob(f"{path}/**/*.{ext}", recursive=True))

        files = sorted(
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

        cmd = ["prettier", "--check"]
        if options.fix:
            cmd.append("--write")

        config_path = self.get(
            base.SECTION, "prettier", "config", default=".prettierrc.yml"
        )
        if os.path.isfile(config_path):
            cmd.append(f"--config {config_path}")

        return utils.call(*cmd, *args, *files, pipe=False)

    def _ci_pylint(self, options, args, paths, ignores):
        """Run pylint tests for Odoo"""
        try:
            # pylint: disable=C0415,E0401,W0611
            import pylint
        except ImportError:
            utils.error("pylint is not installed")
            return 1

        files = set()

        extensions = self.get(
            base.SECTION, "pylint", "extension", default=["csv", "py", "xml"]
        )
        for path in paths:
            for ext in extensions:
                files.update(glob.glob(f"{path}/**/*.{ext}", recursive=True))

        files = sorted(
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
        config_path = self.get(base.SECTION, "pylint", "config", default=".pylintrc")
        if os.path.isfile(config_path):
            cmd.append(f"--rcfile={config_path}")

        return utils.call(*cmd, *args, *files, pipe=False)

    def _ci_ruff(self, options, args, paths, ignores):
        try:
            # pylint: disable=C0415,E0401,W0611
            import ruff
        except ImportError:
            utils.error("ruff is not installed")
            return 1

        cmd = [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--fix" if options.fix else "--no-fix",
            "--force-exclude",
        ]
        for pattern in ignores:
            cmd += ["--exclude", pattern]

        return utils.call(*cmd, *args, *paths, pipe=False)

    def _ci_ruff_format(self, options, args, paths, ignores):
        try:
            # pylint: disable=C0415,E0401,W0611
            import ruff
        except ImportError:
            utils.error("ruff is not installed")
            return 1

        cmd = [
            sys.executable,
            "-m",
            "ruff",
            "format",
            "--force-exclude",
        ]
        if not options.fix:
            cmd.append("--check")

        for pattern in ignores:
            cmd += ["--exclude", pattern]

        return utils.call(*cmd, *args, *paths, pipe=False)

    def _ci_paths(self):
        return self.get("odoo", "addons_path", default=[]) + self.get(
            base.SECTION, "ci_path", default=[]
        )

    def ci(self, ci, args=None):
        """Run CI tests"""
        args, left = load_ci_arguments(args or [])

        # Always include this script in the tests
        ignores = self.get(base.SECTION, "blacklist", default=[])
        func = getattr(self, f"_ci_{ci.replace('-', '_')}", None)
        if ci in CI and callable(func):
            # pylint: disable=E1102
            return func(args, left, self._ci_paths(), ignores)

        utils.error(f"Unknown CI {ci}")
        return 1

    def _install_patches_for_pytest(self):
        """Apply patches for pytest"""
        # pylint: disable=C0415
        from odoo.tests.common import BaseCase

        if hasattr(BaseCase, "run"):
            _original_run = BaseCase.run

            def base_case_run(self, result):
                if not hasattr(result, "wasSuccessful"):
                    result.wasSuccessful = lambda: not result.had_failure
                return _original_run(self, result)

            BaseCase.run = base_case_run

        import pytest_odoo

        if hasattr(pytest_odoo, "monkey_patch_resolve_pkg_root_and_module_name"):
            pytest_odoo.monkey_patch_resolve_pkg_root_and_module_name()

    def _pytest_start_server(self):
        # pylint: disable=C0415,E0401,W0611
        # ruff: noqa: F401
        from odoo.service import server

        server.start(preload=[], stop=True)
        signal.signal(signal.SIGINT, signal.default_int_handler)

        if hasattr(server.server, "http_spawn"):
            server.server.http_spawn()

    def test(self, args=None):
        """Run tests"""
        test_args, args = load_ci_arguments(args or [])

        if not self._init_odoo():
            return False

        # pylint: disable=C0415,E0401,W0611
        # ruff: noqa: F401
        import odoo
        from odoo.cli.server import report_configuration
        from odoo.tools import config

        self._install_patches_for_pytest()

        # Append needed parameter
        if self.get(base.SECTION, "coverage"):
            for path in self._ci_paths():
                args.extend([f"--cov={path}", path])

            args += ["--cov-report=html", "--cov-report=term"]

        for ignore_glob in self.get(base.SECTION, "pytest", "ignore", default=[]):
            args += [f"--ignore-glob={ignore_glob}"]

        # Load the odoo configuration
        with self._manage():
            config.parse_config(["-c", base.ODOO_CONFIG])
            report_configuration()

            if not test_args.no_http:
                config["workers"] = 0
                self._pytest_start_server()

            # Pass the arguments to pytest
            sys.argv = sys.argv[:1] + args
            result = pytest.main()
            if result and result != pytest.ExitCode.NO_TESTS_COLLECTED:
                return result

            return 0
