# © 2021-2022 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import os
import sys
from unittest import mock

import pytest

from doblib import base
from doblib.ci import CIEnvironment


@pytest.fixture
def env():
    os.environ["ODOO_VERSION"] = "1x.0"

    cur = os.getcwd()
    os.chdir("tests/environment/")
    env = CIEnvironment("odoo.local.yaml")
    os.chdir(cur)
    return env


@mock.patch("pytest.main", return_value=42)
def test_test(pytest_mock, env):
    odoo = sys.modules["odoo"] = mock.MagicMock()
    tools = sys.modules["odoo.tools"] = odoo.tools
    sys.modules["odoo.api"] = odoo.api
    sys.modules["odoo.cli"] = odoo.cli
    sys.modules["odoo.cli.server"] = odoo.cli.server
    sys.modules["odoo.modules"] = odoo.modules
    sys.modules["odoo.modules.registry"] = odoo.modules.registry
    sys.modules["odoo.release"] = odoo.release
    odoo.release.version_info = (14, 0)

    assert env.test() is False
    pytest_mock.assert_not_called()
    odoo.api.Environment.managed.assert_not_called()

    env._init_odoo = mock.MagicMock(return_value=True)
    assert env.test() == 42
    tools.config.parse_config.assert_called_once_with(["-c", base.ODOO_CONFIG])
    pytest_mock.assert_called_once()

    pytest_mock.return_value = pytest.ExitCode.NO_TESTS_COLLECTED
    assert env.test() == 0


def test_ci(env):
    env._ci_pylint = mock.MagicMock()
    assert env.ci("unknown") == 1

    env.ci("pylint")
    env._ci_pylint.assert_called_once()


@mock.patch("doblib.utils.call", return_value=42)
def test_ci_black(call, env):
    assert env.ci("black") == 42
    call.assert_called_once_with(
        sys.executable,
        "-m",
        "black",
        "--exclude",
        "(test1.*|test3|\\.git|\\.hg|\\.mypy_cache|"
        "\\.tox|\\.venv|_build|buck-out|build|dist)",
        "--check",
        "--diff",
        "addons",
        pipe=False,
    )


@mock.patch("doblib.utils.call", return_value=42)
@mock.patch("shutil.which", return_value=False)
def test_ci_eslint(which, call, env):
    assert env.ci("eslint") == 1
    call.assert_not_called()

    which.return_value = "/usr/bin/eslint"
    assert env.ci("eslint", ["--fix"]) == 42
    call.assert_called_once_with(
        "eslint",
        "--no-error-on-unmatched-pattern",
        "--fix",
        "--ignore-pattern",
        "test1*",
        "--ignore-pattern",
        "test3",
        "addons",
        pipe=False,
    )


@mock.patch("doblib.utils.call", return_value=42)
def test_ci_flake8(call, env):
    assert env.ci("flake8") == 42
    call.assert_called_once_with(
        sys.executable,
        "-m",
        "flake8",
        "--extend-exclude=test1*,test3",
        "addons",
        pipe=False,
    )


@mock.patch("doblib.utils.call", return_value=42)
def test_ci_isort(call, env):
    assert env.ci("isort") == 42
    call.assert_called_once_with(
        sys.executable,
        "-m",
        "isort",
        "--check",
        "--diff",
        "--skip-glob",
        "*/test1*",
        "--skip-glob",
        "*/test1*/*",
        "--skip-glob",
        "test1*/*",
        "--skip-glob",
        "*/test3",
        "--skip-glob",
        "*/test3/*",
        "--skip-glob",
        "test3/*",
        "--filter-files",
        "addons",
        pipe=False,
    )


@mock.patch("doblib.utils.call", return_value=42)
@mock.patch("shutil.which", return_value=False)
def test_ci_prettier(which, call, env):
    assert env.ci("prettier") == 1
    call.assert_not_called()

    # No files found
    call.reset_mock()
    which.return_value = "/usr/bin/prettier"
    assert env.ci("prettier", ["--fix"]) == 0
    call.assert_not_called()

    with mock.patch(
        "glob.glob",
        return_value=[
            "folder/path/test196.py",
            "folder/test123/file.py",
            "test15/path/file.py",
            "test2/path/file.py",
        ],
    ):
        assert env.ci("prettier", ["--fix"]) == 42
        call.assert_called_once_with(
            "prettier",
            "--check",
            "--write",
            "test2/path/file.py",
            pipe=False,
        )


@mock.patch(
    "glob.glob",
    return_value=[
        "test15/path/file.py",
        "folder/test123/file.py",
        "folder/path/test196.py",
        "test2/path/file.py",
    ],
)
@mock.patch("doblib.utils.call", return_value=42)
def test_ci_pylint(call, glob, env):
    assert env.ci("pylint") == 42
    call.assert_called_once_with(
        sys.executable,
        "-m",
        "pylint",
        "--rcfile=.pylintrc",
        "test2/path/file.py",
        pipe=False,
    )

    call.reset_mock()
    assert env.ci("pylint") == 42
    call.assert_called_once_with(
        sys.executable,
        "-m",
        "pylint",
        "--rcfile=.pylintrc",
        "test2/path/file.py",
        pipe=False,
    )

    glob.return_value = []
    call.reset_mock()
    assert env.ci("pylint") == 0
    call.assert_not_called()
