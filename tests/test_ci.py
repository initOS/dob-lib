# -*- coding: utf-8 -*-
# © 2021-2022 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import os
import sys

import mock
import pytest
from doblib import (
    base,
    utils,
)
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
    utils.module_mock(odoo, ["odoo.cli", "odoo.release", "odoo.tools"])

    odoo.release.version_info = (14, 0)

    assert env.test() is False
    pytest_mock.assert_not_called()
    odoo.api.Environment.managed.assert_not_called()

    env._init_odoo = mock.MagicMock(return_value=True)
    assert env.test() == 42
    odoo.tools.config.parse_config.assert_called_once_with(["-c", base.ODOO_CONFIG])
    pytest_mock.assert_called_once()

    pytest_mock.return_value = 5
    assert env.test() == 0


def test_ci(env):
    env._ci_pylint = mock.MagicMock()
    assert env.ci("unknown") == 1

    env.ci("pylint")
    env._ci_pylint.assert_called_once()


@mock.patch("doblib.utils.call", return_value=42)
@mock.patch("doblib.utils.which", return_value=False)
def test_ci_eslint(which, call, env):
    assert env.ci("eslint") == 1
    call.assert_not_called()

    which.return_value = "/usr/bin/eslint"
    assert env.ci("eslint", ["--fix"]) == 42
    call.assert_called_once_with(
        [
            "eslint",
            "--no-error-on-unmatched-pattern",
            "--fix",
            "--ignore-pattern",
            "test1*",
            "--ignore-pattern",
            "test3",
            "addons",
        ],
        pipe=False,
    )


@mock.patch("doblib.utils.call", return_value=42)
def test_ci_flake8(call, env):
    assert env.ci("flake8") == 42
    call.assert_called_once_with(
        [
            sys.executable,
            "-m",
            "flake8",
            "--extend-exclude=test1*,test3",
            "addons",
        ],
        pipe=False,
    )


@mock.patch("doblib.utils.call", return_value=42)
def test_ci_isort(call, env):
    assert env.ci("isort") == 42
    call.assert_called_once_with(
        [
            "isort",
            "--check",
            "--diff",
            "--recursive",
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
        ],
        pipe=False,
    )


@mock.patch("doblib.utils.call", return_value=42)
@mock.patch("doblib.utils.which", return_value=False)
def test_ci_prettier(which, call, env):
    assert env.ci("prettier") == 1
    call.assert_not_called()

    # No files found
    call.reset_mock()
    which.return_value = "/usr/bin/prettier"
    assert env.ci("prettier", ["--fix"]) == 0
    call.assert_not_called()

    with mock.patch(
        "doblib.utils.recursive_glob",
        return_value=[
            "test15/path/file.js",
            "folder/test123/file.js",
            "folder/path/test196.js",
            "test2/path/file.js",
        ],
    ):
        assert env.ci("prettier", ["--fix"]) == 42
        call.assert_called_once_with(
            [
                "prettier",
                "--write",
                "test2/path/file.js",
            ],
            pipe=False,
        )


@mock.patch(
    "doblib.utils.recursive_glob",
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
        [
            sys.executable,
            "-m",
            "pylint",
            "--rcfile=.pylintrc",
            "test2/path/file.py",
            "test2/path/file.py",
            "test2/path/file.py",
        ],
        pipe=False,
    )

    call.reset_mock()
    assert env.ci("pylint") == 42
    call.assert_called_once_with(
        [
            sys.executable,
            "-m",
            "pylint",
            "--rcfile=.pylintrc",
            "test2/path/file.py",
            "test2/path/file.py",
            "test2/path/file.py",
        ],
        pipe=False,
    )

    glob.return_value = []
    call.reset_mock()
    assert env.ci("pylint") == 0
    call.assert_not_called()
