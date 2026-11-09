# © 2021-2022 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import os
import subprocess
from queue import Empty
from unittest import mock

import pytest

from doblib.aggregate import (
    COMMIT_FILE,
    AggregateEnvironment,
    aggregate,
    aggregate_repo,
    commit_file,
    merge_lines,
    repo_state,
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


SHA1 = "a" * 40
SHA2 = "b" * 40


def fake_repo(path, *merges):
    repo = mock.MagicMock()
    repo.cwd = str(path)
    repo.merges = [{"remote": r, "ref": ref} for r, ref in merges]
    return repo


def git_init(path):
    subprocess.run(["git", "init", "-q", str(path)], check=True)


def test_repo_state(tmp_path):
    repo = fake_repo(tmp_path, ("origin", SHA1), ("another", SHA2))
    assert repo_state(repo) == "new"

    git_init(tmp_path)
    assert repo_state(repo) == "incomplete"

    path = tmp_path / ".git" / COMMIT_FILE
    path.write_text(f"origin {SHA1}\nanother {SHA2}\n")
    assert commit_file(repo) == str(path)
    assert merge_lines(repo) == path.read_text()
    assert repo_state(repo) == "unchanged"

    (tmp_path / "file").write_text("local change")
    assert repo_state(repo) == "dirty"

    repo.merges[1]["ref"] = SHA1
    assert repo_state(repo) == "changed"

    repo.merges.pop()
    assert repo_state(repo) == "changed"

    repo.merges.append({"remote": "another", "ref": "18.0"})
    path.write_text(merge_lines(repo))
    assert repo_state(repo) == "unpinned"


def test_aggregate_commit_file(tmp_path):
    repo = fake_repo(tmp_path, ("origin", SHA1))
    path = tmp_path / ".git" / COMMIT_FILE

    def create_git():
        assert not path.exists()
        (tmp_path / ".git").mkdir(exist_ok=True)

    repo.aggregate.side_effect = create_git
    aggregate(repo)
    assert path.read_text() == f"origin {SHA1}\n"

    repo.merges[0]["ref"] = SHA2
    repo.aggregate.side_effect = RuntimeError()
    with pytest.raises(RuntimeError):
        aggregate(repo)
    assert not path.exists()


def test_filter_outdated(env, tmp_path):
    repos = {}
    for name in ("unchanged", "changed", "dirty", "incomplete", "new", "other"):
        repo = repos[name] = fake_repo(tmp_path / name, ("origin", SHA1))
        if name != "new":
            git_init(tmp_path / name)
        if name in ("unchanged", "changed", "dirty", "other"):
            (tmp_path / name / ".git" / COMMIT_FILE).write_text(merge_lines(repo))
    repos["changed"].merges[0]["ref"] = SHA2
    repos["other"].merges[0]["ref"] = SHA2
    (tmp_path / "dirty" / "file").write_text("local change")

    outdated = [repos["changed"], repos["incomplete"], repos["new"]]
    args = mock.MagicMock(dirmatch=f"{tmp_path}/[!o]*", force=False)
    assert env._filter_outdated(repos.values(), args) == outdated

    args.force = True
    outdated.insert(1, repos["dirty"])
    assert env._filter_outdated(repos.values(), args) == outdated

    hint = "Use --all to bootstrap the skipped repositories as well"
    with mock.patch("doblib.aggregate.utils.info") as info:
        env._filter_outdated(repos.values(), args)
        info.assert_any_call(hint)

        info.reset_mock()
        env._filter_outdated(outdated, args)
        assert mock.call(hint) not in info.call_args_list


@mock.patch("doblib.aggregate.match_dir", return_value=False)
def test_aggregate_repo(match_mock, tmp_path):
    m = mock.MagicMock(cwd=str(tmp_path), merges=[])
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
    repo.return_value.cwd = "unknown"

    assert not env.init()

    repos.assert_called_once()
    repo.assert_called()
    aggregate.assert_called()

    aggregate.reset_mock()
    env.init(["-j", "1"])
    aggregate.assert_called()

    aggregate.reset_mock()
    with mock.patch.object(env, "_filter_outdated", return_value=[]) as filter_mock:
        env.aggregate("show-all-prs", ["-j", "1"])
        filter_mock.assert_not_called()
        aggregate.assert_called_once()

        aggregate.reset_mock()
        assert not env.init(["-a", "-j", "1"])
        filter_mock.assert_not_called()
        aggregate.assert_called_once()

        aggregate.reset_mock()
        assert not env.init(["-j", "1"])
        filter_mock.assert_called_once()
        aggregate.assert_not_called()

    with mock.patch("doblib.aggregate.Queue") as m:
        queue = m.return_value
        queue.empty.return_value = False

        queue.get_nowait.side_effect = [(1, 42, 37), Empty()]
        assert env.init() == 1

        queue.empty.assert_called()
        queue.get_nowait.assert_called()
        traceback.print_exception.assert_called_once_with(1, 42, 37)
