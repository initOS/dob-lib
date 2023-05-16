# -*- coding: utf-8 -*-
# © 2021-2022 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import os
from Queue import Empty

import mock
import pytest
from doblib.aggregate import (
    AggregateEnvironment,
    aggregate_repo,
)


def aggregate_exception(repo, args, sem, err_queue):
    try:
        err_queue.put_nowait("ERROR")
    finally:
        sem.release()


@pytest.fixture
def env():
    cur = os.getcwd()
    os.chdir("tests/environment/")
    env = AggregateEnvironment("odoo.local.yaml")
    os.chdir(cur)
    return env


def test_init(env):
    env.generate_config = mock.MagicMock()
    env._aggregator = mock.MagicMock()

    env.init(["--no-config"])
    env.generate_config.assert_not_called()
    env._aggregator.assert_called_once()

    env._aggregator.reset_mock()
    env.init()
    env.generate_config.assert_called_once()
    env._aggregator.assert_called_once()


def test_aggregate(env):
    env._aggregator = mock.MagicMock()

    env.aggregate("show-all-prs", ["-f"])
    env._aggregator.assert_called_once()


@mock.patch("doblib.aggregate.match_dir", return_value=False)
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

    aggregate_repo(m, m, m, m, mode="show-all-prs")
    m.show_all_prs.assert_called_once()
    aggregate_repo(m, m, m, m, mode="show-closed-prs")
    m.show_closed_prs.assert_called_once()

    m.reset_mock()
    match_mock.side_effect = Exception()
    aggregate_repo(m, m, m, m)

    m.put_nowait.assert_called()
    m.release.assert_called_once()
    m.aggregate.assert_not_called()


@mock.patch("doblib.aggregate.traceback")
@mock.patch("doblib.aggregate.Repo")
@mock.patch("doblib.aggregate.aggregate_repo")
@mock.patch("doblib.aggregate.get_repos", return_value=[{"cwd": "unknown"}])
def test_bootstrap(repos, aggregate, repo, traceback, env):
    env.generate_config = mock.MagicMock()

    assert not env.init()

    repos.assert_called_once()
    repo.assert_called()
    aggregate.assert_called()

    aggregate.reset_mock()
    env.init(["-j", "1"])
    aggregate.assert_called()

    with mock.patch("doblib.aggregate.Queue") as m:
        queue = m.return_value
        queue.empty.return_value = False

        queue.get_nowait.side_effect = [(1, 42, 37), Empty()]
        assert env.init() == 1

        queue.empty.assert_called()
        queue.get_nowait.assert_called()
        traceback.print_exception.assert_called_once_with(1, 42, 37)
