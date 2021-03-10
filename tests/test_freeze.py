# © 2021 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import os
from tempfile import NamedTemporaryFile
from unittest import mock

import pytest

from doblib.freeze import FreezeEnvironment


@pytest.fixture
def env():
    cur = os.getcwd()
    os.chdir("tests/environment/")
    env = FreezeEnvironment("odoo.local.yaml")
    os.chdir(cur)
    return env


def test_freeze(env):
    pack_mock = env._freeze_packages = mock.MagicMock()
    repo_mock = env._freeze_repositories = mock.MagicMock()

    env.freeze(["--no-packages", "--no-repos"])
    pack_mock.assert_not_called()
    repo_mock.assert_not_called()

    env.freeze(["--no-packages"])
    pack_mock.assert_not_called()
    repo_mock.assert_called()

    repo_mock.reset_mock()
    env.freeze(["--no-repos"])
    pack_mock.assert_called()
    repo_mock.assert_not_called()

    pack_mock.reset_mock()
    env.freeze()
    pack_mock.assert_called()
    repo_mock.assert_called()


@mock.patch("builtins.input")
def test_mode(input_mock, env):
    input_mock.return_value = "n"

    assert env._freeze_mode("unknown") is True
    input_mock.assert_not_called()

    with NamedTemporaryFile() as fp:
        assert env._freeze_mode(fp.name, mode="skip") is False
        input_mock.assert_not_called()

        assert env._freeze_mode(fp.name, "all") is True
        input_mock.assert_not_called()

        assert env._freeze_mode(fp.name, "ask") is False
        input_mock.assert_called()

        input_mock.reset_mock()
        input_mock.return_value = "Y"
        assert env._freeze_mode(fp.name, "ask") is True
        input_mock.assert_called()


def test_freeze_packages(env):
    env._freeze_mode = mock.MagicMock(return_value=True)
    with NamedTemporaryFile() as fp:
        env._freeze_packages(fp.name)
        fp.seek(0)
        assert fp.read()


@mock.patch("doblib.utils.call", return_value="")
def test_freeze_repositories(call_mock, env):
    env._freeze_mode = mock.MagicMock(return_value=True)
    with NamedTemporaryFile() as fp:
        call_mock.return_value = "\n".join(
            ["refs/remotes/origin/master 0123abcd", "origin/develop abcd0123"]
        )
        env._freeze_repositories(fp.name)
        fp.seek(0)
        assert fp.read()

    with NamedTemporaryFile() as fp:
        env.set("repos", value={})
        env._freeze_repositories(fp.name)
        fp.seek(0)
        assert not fp.read()
