# © 2021 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import os
import sys
from tempfile import NamedTemporaryFile
from unittest import mock

import pytest

from dob.run import RunEnvironment


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
        env.shell([fp.name])
        shell.Shell.assert_called_once()
        assert sys.argv == [fp.name]


@mock.patch("dob.utils.call", return_value=42)
def test_start(call_mock, env):
    assert env.start() is False

    env._init_odoo = mock.MagicMock(return_value=True)
    assert env.start() == 42
    call_mock.assert_called_once()
