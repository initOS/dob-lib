# © 2021 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import os
import sys
from tempfile import NamedTemporaryFile
from unittest import mock

import pytest

from doblib import base
from doblib.run import RunEnvironment

DEBUGGERS = ["debugpy"]


@pytest.fixture
def env():
    os.environ["ODOO_VERSION"] = "1x.0"

    cur = os.getcwd()
    os.chdir("tests/environment/")
    env = RunEnvironment("odoo.local.yaml")
    os.chdir(cur)
    return env


def test_shell(env):
    shell = sys.modules["odoo.cli.shell"] = mock.MagicMock()

    assert env.shell() is False
    shell.Shell.assert_not_called()

    shell.Shell.return_value.run.return_value = 42

    env._init_odoo = mock.MagicMock(return_value=True)
    assert env.shell() == 42
    shell.Shell.assert_called_once()
    assert sys.argv == [""]

    with NamedTemporaryFile() as fp:
        shell.Shell.reset_mock()
        console_mock = shell.Shell.return_value.console
        env.shell([fp.name])
        shell.Shell.assert_called_once()
        assert sys.argv == [fp.name]
        assert console_mock != shell.Shell.return_value.console


@mock.patch("doblib.utils.call", return_value=42)
def test_start(call_mock, env):
    assert env.start() is False

    env._init_odoo = mock.MagicMock(return_value=True)
    assert env.start() == 42
    call_mock.assert_called_once()


@mock.patch("doblib.utils.call")
def test_start_with_debugger(call_mock, env):
    def check_debugger(debugger, *args, **kwargs):
        if debugger == "dev" and "--dev=all" not in args:
            raise ValueError("Missing dev=all")
        elif debugger in DEBUGGERS and args[1:3] != ("-m", debugger):
            raise ValueError("Missing debugpy integration")
        return 128

    env._init_odoo = mock.MagicMock(return_value=True)

    call_mock.side_effect = lambda *a, **kw: check_debugger("debugpy", *a, **kw)
    env.set(base.SECTION, "debugger", value="debugpy")
    assert env.start() == 128
    call_mock.assert_called_once()

    call_mock.reset_mock()
    call_mock.side_effect = lambda *a, **kw: check_debugger("dev", *a, **kw)
    env.set(base.SECTION, "debugger", value="dev")
    assert env.start() == 128
    call_mock.assert_called_once()
