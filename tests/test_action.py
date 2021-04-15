# © 2021 Florian Kantelberg (initOS GmbH)
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


def test_text(env):
    assert env._text({"test": "ll"}, field="test", prefix="he", suffix="o") == "hello"
    assert env._text({"name": "yh"}, name="name", prefix="he", suffix="o") == "heyho"

    with pytest.raises(KeyError):
        env._text({})

    with pytest.raises(KeyError):
        env._text({}, field="test")

    with mock.patch("random.choices", return_value="abc") as choices:
        assert env._text({}, length=5, prefix="0", suffix="def") == "0abcdef"
        choices.assert_called_once_with(ALNUM, k=5)

    with mock.patch("uuid.uuid1", return_value="a-b") as uuid:
        assert env._text({}, uuid=1) == "a-b"
        uuid.assert_called_once()

    with mock.patch("uuid.uuid4", return_value="a-b") as uuid:
        assert env._text({}, uuid=4) == "a-b"
        uuid.assert_called_once()


def test_datetime(env):
    assert env._datetime({"test": "abc"}, field="test") == "abc"

    with mock.patch("random.randint", return_value=0.0) as randint:
        assert env._datetime({}) == datetime(1970, 1, 1)
        randint.assert_called_once()


def test_date(env):
    assert env._date({"test": "abc"}, field="test") == "abc"

    with mock.patch("random.randint", return_value=0.0) as randint:
        assert env._date({}) == date(1970, 1, 1)
        randint.assert_called_once()


def test_action_delete(env):
    domain = [("abc", "=", 42)]
    m = mock.MagicMock()
    search = m.with_context.return_value.search

    env._action_delete({"test": m}, "unknown", domain)
    m.with_context.assert_not_called()
    search.assert_not_called()

    env._action_delete({"test": m}, "test", domain)
    m.with_context.assert_called_once_with(active_test=False)
    search.assert_called_once_with(domain)
    search.return_value.unlink.assert_called_once()


def test_action_update(env):
    env._apply = mock.MagicMock()
    m = mock.MagicMock()
    search = m.with_context.return_value.search
    odoo_env = {"test": m}

    env._action_update(odoo_env, "test", [], {})
    m.with_context.assert_not_called()
    search.assert_not_called()

    records = search.return_value
    records._fields = {"test": "integer"}
    env._action_update(odoo_env, "test", [], {"test": 42, "unknown": 42})
    records.write.assert_called_once_with({"test": 42})

    records.__iter__.return_value = [records]
    records.write.reset_mock()
    env._action_update(odoo_env, "test", [], {"test": {}})
    records.write.assert_called_once_with({"test": env._apply.return_value})


def test_action_insert(env):
    m = mock.MagicMock()
    create = m.with_context.return_value.create
    m.search.return_value = False

    odoo_env = mock.MagicMock()
    odoo_env_dict = {"model": m}
    odoo_env.__getitem__.side_effect = odoo_env_dict.__getitem__
    odoo_env.__contains__.side_effect = odoo_env_dict.__contains__

    ref_mock = mock.MagicMock()
    ref_mock.id = 5
    references = {"reference": ref_mock}
    odoo_env.ref.side_effect = references.__getitem__

    env._action_insert(odoo_env, "model", [], {}, {})
    create.assert_not_called()
    odoo_env.ref.assert_not_called()

    env._action_insert(
        odoo_env,
        "wrong.model",
        [["name", "=", "test"]],
        {"$value": "reference"},
        {"name": "test", "test": "$value", "list": [{"other_test": "$value"}]},
    )
    create.assert_not_called()
    odoo_env.ref.assert_not_called()

    env._action_insert(
        odoo_env,
        "model",
        [["name", "=", "test"]],
        {"$value": "reference"},
        {"name": "test", "test": "$value", "list": [{"other_test": "$value"}]},
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

    sys.modules["odoo"] = mock.MagicMock()
    sys.modules["odoo.tools"] = mock.MagicMock()
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
