# © 2021-2022 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import os
import sys
from datetime import date, datetime
from unittest import mock

import pytest

from doblib.action import ALNUM, ActionEnvironment


@pytest.fixture
def env():
    cur = os.getcwd()
    os.chdir("tests/environment/")
    env = ActionEnvironment("odoo.local.yaml")
    os.chdir(cur)
    return env


@pytest.fixture
def module():
    m = mock.MagicMock()
    m.search.return_value = False
    return m


@pytest.fixture
def odoo_env(module):
    odoo_env = mock.MagicMock()
    odoo_env_dict = {"test": module}
    odoo_env.__getitem__.side_effect = odoo_env_dict.__getitem__
    odoo_env.__contains__.side_effect = odoo_env_dict.__contains__

    ref_mock = mock.MagicMock()
    ref_mock.id = 5
    references = {"reference": ref_mock}
    odoo_env.ref.side_effect = references.__getitem__

    return odoo_env


def test_boolean(env):
    assert env._boolean({"test": False}, field="test") is False
    assert env._boolean({"test": True}, field="test") is True

    with pytest.raises(KeyError):
        env._boolean({}, field="test")

    with mock.patch("random.choice", side_effect=[False, True]):
        assert env._boolean({"test": True}) is False
        assert env._boolean({"test": True}) is True


def test_integer(env):
    assert env._integer({"test": 42}, field="test") == 42

    with pytest.raises(KeyError):
        env._integer({}, field="test")

    with mock.patch("random.randint", side_effect=[42, 5]) as randint:
        assert env._integer({"test": 1}, lower=-42, upper=42) == 42
        randint.assert_called_once_with(-42, 42)
        assert env._integer({"test": 1}, lower=-42, upper=42) == 5

    with pytest.raises(TypeError):
        env._integer({"test": 1})


def test_float(env):
    assert env._float({"test": 42}, field="test") == 42

    with pytest.raises(KeyError):
        env._float({}, field="test")

    with mock.patch("random.random", side_effect=[0.25, 0.5]) as randint:
        assert env._float({"test": 1}) == 0.25
        randint.assert_called_once()
        assert env._float({"test": 1}, lower=0, upper=42) == 21


def test_selection(env):
    rec = mock.MagicMock()
    assert env._selection(rec, name="test", field="test") == rec["test"]

    with pytest.raises(KeyError):
        env._selection({}, name="test", field="test")

    with mock.patch("random.choice", side_effect=["on", "off"]) as choice:
        assert env._selection(rec, name="test") == "on"
        choice.assert_called_once()
        assert env._selection(rec, name="test") == "off"

    with mock.patch("random.choice", return_value="a-b") as choice:
        assert env._selection({}, name="test", choices=["a-b"]) == "a-b"
        choice.assert_called_once()


def test_text(env):
    assert (
        env._text({"test": "ll"}, name="test", field="test", prefix="he", suffix="o")
        == "hello"
    )
    assert env._text({"name": "yh"}, name="name", prefix="he", suffix="o") == "heyho"

    with pytest.raises(KeyError):
        env._text({}, name="name")

    with pytest.raises(KeyError):
        env._text({}, name="name", field="test")

    with mock.patch("random.choices", return_value="abc") as choices:
        assert (
            env._text({}, name="test", length=5, prefix="0", suffix="def") == "0abcdef"
        )
        choices.assert_called_once_with(ALNUM, k=5)

    with mock.patch("uuid.uuid1", return_value="a-b") as uuid:
        assert env._text({}, name="test", uuid=1) == "a-b"
        uuid.assert_called_once()

    with mock.patch("uuid.uuid4", return_value="a-b") as uuid:
        assert env._text({}, name="test", uuid=4) == "a-b"
        uuid.assert_called_once()

    with mock.patch("random.choice", return_value="a-b") as choice:
        assert env._text({}, name="test", choices=["a-b"]) == "a-b"
        choice.assert_called_once()


def test_datetime(env):
    assert env._datetime({"test": "abc", "k": "a"}, name="k", field="test") == "abc"

    with mock.patch("random.randint", return_value=0.0) as randint:
        assert env._datetime({}, name="test") == datetime(1970, 1, 1)
        randint.assert_called_once()

    attrs = {"hour": 12, "day": 32, "month": {"lower": 3, "upper": 9}}
    dt = datetime(2023, 1, 1, 0, 0, 0)
    res = env._datetime({"test": dt}, name="test", **attrs)
    assert res.day >= 28  # last day of the month must be bigger than 28
    assert res.hour == 12
    assert 3 <= res.month <= 9

    with mock.patch("random.randint", return_value=42) as randint:
        attrs = {"second": None}
        res = env._datetime({"test": dt}, name="test", second=None)
        assert res.second == 42
        randint.assert_called_once()

    attrs = {"hour": 12, "day": 32, "month": {"lower": 3, "upper": 9}}
    res = env._datetime({"test": datetime(2023, 1, 1, 0, 0, 0)}, name="test", **attrs)


def test_date(env):
    assert env._date({"test": "abc", "k": "a"}, name="k", field="test") == "abc"

    with mock.patch("random.randint", return_value=0.0) as randint:
        assert env._date({}, name="test") == date(1970, 1, 1)
        randint.assert_called_once()

    attrs = {"hour": 12, "day": 32, "month": {"lower": 3, "upper": 9}}
    res = env._date({"test": date(2023, 1, 1)}, name="test", **attrs)
    assert res.day >= 28  # last day of the month must be bigger than 28
    assert 3 <= res.month <= 9


def test_many2one(env):
    rec = mock.MagicMock()
    rec._name = "TEST"
    rec.__getitem__ = mock.MagicMock()
    rec.__getitem__.return_value.search.return_value = False

    assert env._many2one(rec, "test") is False

    recordset = mock.MagicMock()
    recordset.ids = [4, 2, 7, 9]
    search = mock.MagicMock(return_value=recordset)
    rec.__getitem__.return_value.search = search

    with mock.patch("random.choice", lambda x: x[0]):
        assert env._many2one(rec, "test", domain=[("test", "=", True)]) == 4
        assert rec.__getitem__.called_once_with("TEST")
        assert search.called_once_with([("test", "=", True)])


def test_many2many(env):
    rec = mock.MagicMock()
    rec._name = "TEST"
    rec.__getitem__ = mock.MagicMock()
    rec.__getitem__.return_value.__len__.return_value = 1
    rec.__getitem__.return_value.search.return_value = False

    assert env._many2many(rec, "test") == [(5,)]

    recordset = mock.MagicMock()
    recordset.ids = [4, 2, 7, 9]
    recordset.__len__.return_value = 4

    search = mock.MagicMock(return_value=recordset)
    rec.__getitem__.return_value.search = search

    with mock.patch("random.sample", lambda x, n: x[:n]):
        assert env._many2many(rec, "test", domain=[("test", "=", True)]) == [
            (6, 0, [4])
        ]
        assert rec.__getitem__.called_once_with("TEST")
        assert search.called_once_with([("test", "=", True)])

        assert env._many2many(rec, "test", length=2) == [(6, 0, [4, 2])]


@mock.patch("doblib.utils.warn")
def test_action_delete(call_mock, env, odoo_env, module):
    domain = [["abc", "=", 42], ["def", "=", "$value"]]
    refs = {"$value": "reference"}
    domain_resolved = [["abc", "=", 42], ["def", "=", 5]]

    search = module.with_context.return_value.search
    records = search.return_value
    records.__len__.return_value = 2
    records.__getitem__.return_value = records

    env._action_delete(odoo_env, "unknown", domain, {})
    module.with_context.assert_not_called()
    search.assert_not_called()

    env._action_delete(odoo_env, "test", domain, {"chunk": 1000})
    module.with_context.assert_called_once_with(active_test=False)
    search.assert_called_once_with(domain)
    records.unlink.assert_called_once()
    odoo_env.cr.commit.assert_called_once()

    search.reset_mock()
    odoo_env.reset_mock()
    module.with_context.reset_mock()
    env._action_delete(odoo_env, "test", domain, {"chunk": 1000}, dry_run=True)
    module.with_context.assert_called_once_with(active_test=False)
    search.assert_called_once_with(domain)
    records.unlink.assert_called_once()
    odoo_env.cr.commit.assert_not_called()

    search.reset_mock()
    odoo_env.reset_mock()
    module.with_context.reset_mock()
    env._action_delete(odoo_env, "test", domain, {"references": refs})
    module.with_context.assert_called_once_with(active_test=False)
    search.assert_called_once_with(domain_resolved)
    records.unlink.assert_called_once()
    odoo_env.cr.commit.assert_not_called()

    search.reset_mock()
    odoo_env.reset_mock()
    module.with_context.reset_mock()
    env._action_delete(odoo_env, "test", domain, {"references": refs, "chunk": 1})
    module.with_context.assert_called_once_with(active_test=False)
    search.assert_called_once_with(domain_resolved)
    assert records.unlink.call_count == 2
    assert odoo_env.cr.commit.call_count == 2
    call_mock.assert_not_called()

    search.reset_mock()
    odoo_env.reset_mock()
    module.with_context.reset_mock()
    env._action_delete(odoo_env, "test", domain, {"references": refs, "truncate": True})
    module.with_context.assert_called_once_with(active_test=False)
    search.assert_called_once_with(domain_resolved)
    records.unlink.assert_called_once()
    odoo_env.cr.commit.assert_not_called()
    call_mock.assert_called_once_with(
        "Setting a domain is not possible with truncate. Falling back"
    )

    search.reset_mock()
    odoo_env.reset_mock()
    module._table.__str__.return_value = "test_model"
    module.with_context.reset_mock()
    env._action_delete(odoo_env, "test", [], {"references": refs, "truncate": True})
    module.with_context.assert_not_called()
    search.assert_not_called()
    records.unlink.assert_not_called()
    odoo_env.cr.commit.assert_not_called()
    odoo_env.cr.execute.assert_called_once_with("TRUNCATE test_model CASCADE")


def test_action_update(env, odoo_env, module):
    env._apply = mock.MagicMock()
    search = module.with_context.return_value.search

    env._action_update(odoo_env, "test", [], {})
    module.with_context.assert_not_called()
    search.assert_not_called()

    records = search.return_value
    test_model = mock.MagicMock()
    test_model.type = "integer"
    const_model = mock.MagicMock()
    const_model.type = "integer"
    records._fields = {"test": test_model, "const": const_model}
    records.__len__.return_value = 2
    records.__bool__.return_value = False
    records.__getitem__.return_value = records

    env._action_update(
        odoo_env, "test", [], {"values": {"test": 42, "unknown": 42}, "chunk": 1000}
    )
    records.write.assert_not_called()

    records.__bool__.return_value = True
    env._action_update(
        odoo_env, "test", [], {"values": {"test": 42, "unknown": 42}, "chunk": 1000}
    )
    records.write.assert_called_once_with({"test": 42})
    odoo_env.cr.commit.assert_called_once()

    records.__iter__.return_value = [records]
    records.write.reset_mock()
    odoo_env.reset_mock()
    env._action_update(odoo_env, "test", [], {"values": {"test": {}}, "chunk": 1000})
    records.write.assert_called_once_with({"test": env._apply.return_value})
    odoo_env.cr.commit.assert_not_called()

    records.__iter__.return_value = [records]
    records.write.reset_mock()
    odoo_env.reset_mock()
    refs = {"$value": "reference"}
    env._action_update(
        odoo_env, "test", [], {"references": refs, "values": {"test": "$value"}}
    )
    records.write.assert_called_once_with({"test": 5})
    odoo_env.cr.commit.assert_not_called()

    records.__iter__.return_value = [records, records]
    records.write.reset_mock()
    odoo_env.reset_mock()
    env._action_update(
        odoo_env,
        "test",
        [],
        {"values": {"test": {"lower": 5, "upper": 5}, "const": 2}, "chunk": 1},
    )
    # For each record (2) const and dynamic commit
    assert records.write.call_count == 4
    assert odoo_env.cr.commit.call_count == 4

    records.write.reset_mock()
    odoo_env.reset_mock()
    env._action_update(
        odoo_env,
        "test",
        [],
        {"values": {"test": {"lower": 5, "upper": 5}, "const": 2}, "chunk": 1},
        dry_run=True,
    )
    # For each record (2) const and dynamic commit
    odoo_env.cr.commit.assert_not_called()


def test_action_insert(env, odoo_env, module):
    create = module.with_context.return_value.create

    env._action_insert(odoo_env, "test", [], {})
    create.assert_not_called()
    odoo_env.ref.assert_not_called()

    env._action_insert(
        odoo_env,
        "wrong.model",
        [["name", "=", "test"]],
        {
            "references": {"$value": "reference"},
            "values": {
                "name": "test",
                "test": "$value",
                "list": [{"other_test": "$value"}],
            },
        },
    )
    create.assert_not_called()
    odoo_env.ref.assert_not_called()

    env._action_insert(
        odoo_env,
        "test",
        [["name", "=", "test"]],
        {
            "references": {"$value": "reference"},
            "values": {
                "name": "test",
                "test": "$value",
                "list": [{"other_test": "$value"}],
            },
        },
    )
    create.assert_called_once_with(
        {"name": "test", "test": 5, "list": [{"other_test": 5}]},
    )

    module.search.return_value = True
    env._action_insert(
        odoo_env,
        "test",
        [["name", "=", "test"]],
        {
            "references": {"$value": "reference"},
            "values": {
                "name": "test",
                "test": "$value",
                "list": [{"other_test": "$value"}],
            },
        },
    )
    create.assert_called_once_with(
        {"name": "test", "test": 5, "list": [{"other_test": 5}]},
    )


def test_apply_action(env):
    env._action_update = mock.MagicMock()
    env._action_delete = mock.MagicMock()
    env._action_insert = mock.MagicMock()
    env._init_odoo = mock.MagicMock(return_value=False)
    env.apply_action(["action"])

    odoo = sys.modules["odoo"] = mock.MagicMock()
    sys.modules["odoo.tools"] = mock.MagicMock()
    sys.modules["odoo.release"] = odoo.release
    odoo.release.version_info = (14, 0)
    env._init_odoo.return_value = True

    env.apply_action(["action"])

    env._action_update.assert_called_once()
    env._action_delete.assert_called_once()
    env._action_insert.assert_called_once()


def test_apply(env):
    env._boolean = mock.MagicMock()
    env._date = mock.MagicMock()
    env._datetime = mock.MagicMock()
    env._float = mock.MagicMock()
    env._integer = mock.MagicMock()
    env._text = mock.MagicMock()
    env._selection = mock.MagicMock()

    mtype = mock.MagicMock()
    rec = mock.MagicMock(_fields={"test": mtype})
    rec._fields = {"test": mtype}

    with pytest.raises(TypeError):
        env._apply(rec, "test")

    mtype.type = "boolean"
    assert env._apply(rec, "test") == env._boolean.return_value
    mtype.type = "integer"
    assert env._apply(rec, "test") == env._integer.return_value
    mtype.type = "float"
    assert env._apply(rec, "test") == env._float.return_value
    mtype.type = "monetary"
    assert env._apply(rec, "test") == env._float.return_value
    mtype.type = "date"
    assert env._apply(rec, "test") == env._date.return_value
    mtype.type = "datetime"
    assert env._apply(rec, "test") == env._datetime.return_value
    mtype.type = "char"
    assert env._apply(rec, "test") == env._text.return_value
    mtype.type = "html"
    assert env._apply(rec, "test") == env._text.return_value
    mtype.type = "text"
    assert env._apply(rec, "test") == env._text.return_value
    mtype.type = "selection"
    assert env._apply(rec, "test") == env._selection.return_value
