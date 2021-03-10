# © 2021 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import os
from queue import Empty
from unittest import mock

import pytest

from dob.bootstrap import BootstrapEnvironment, aggregate_repo


def aggregate_exception(repo, args, sem, err_queue):
    try:
        err_queue.put_nowait("ERROR")
    finally:
        sem.release()


@pytest.fixture
def env():
    cur = os.getcwd()
    os.chdir("tests/environment/")
    env = BootstrapEnvironment("odoo.local.yaml")
    os.chdir(cur)
    return env


def test_init(env):
    env.generate_config = mock.MagicMock()
    env._bootstrap = mock.MagicMock()

    env.init(["--no-config"])
    env.generate_config.assert_not_called()
    env._bootstrap.assert_called_once()

    env._bootstrap.reset_mock()
    env.init()
    env.generate_config.assert_called_once()
    env._bootstrap.assert_called_once()


@mock.patch("dob.bootstrap.match_dir", return_value=False)
def test_aggregate_repo(match_mock):
    m = mock.MagicMock()
    aggregate_repo(m, m, m, m)

    m.put_nowait.assert_not_called()
    m.release.assert_called_once()
    match_mock.assert_called_once_with(m.cwd, m.dirmatch)
    m.aggregate.assert_not_called()

    m.reset_mock()
    match_mock.return_value = True
    aggregate_repo(m, m, m, m)

    m.put_nowait.assert_not_called()
    m.release.assert_called_once()
    m.aggregate.assert_called()

    m.reset_mock()
    match_mock.side_effect = Exception()
    aggregate_repo(m, m, m, m)

    m.put_nowait.assert_called()
    m.release.assert_called_once()
    m.aggregate.assert_not_called()


@mock.patch("dob.bootstrap.traceback")
@mock.patch("dob.bootstrap.Repo")
@mock.patch("dob.bootstrap.aggregate_repo")
@mock.patch("dob.bootstrap.get_repos", return_value=[{"cwd": "unknown"}])
def test_bootstrap(repos, aggregate, repo, traceback, env):
    env.generate_config = mock.MagicMock()

    assert not env.init()

    repos.assert_called_once()
    repo.assert_called()
    aggregate.assert_called()

    aggregate.reset_mock()
    env.init(["-j", "1"])
    aggregate.assert_called()

    with mock.patch("dob.bootstrap.Queue") as m:
        queue = m.return_value
        queue.empty.return_value = False

        queue.get_nowait.side_effect = [(1, 42, 37), Empty()]
        assert env.init() == 1

        queue.empty.assert_called()
        queue.get_nowait.assert_called()
        traceback.print_exception.assert_called_once_with(1, 42, 37)
