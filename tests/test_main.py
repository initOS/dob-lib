# © 2021 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import sys
from tempfile import NamedTemporaryFile
from unittest.mock import MagicMock, patch

from doblib.__main__ import main


@patch("sys.exit")
@patch("doblib.utils.get_config_file")
def test_config(config_mock, exit_mock):  # pylint: disable=R0915
    with NamedTemporaryFile() as fp:
        config_mock.return_value = fp.name

        with patch("doblib.__main__.Environment") as mock:
            main(["c", "additional"])
            mock.assert_called_once_with(fp.name)
            mock.return_value.config.assert_called_once_with(["additional"])

        with patch("doblib.__main__.FreezeEnvironment") as mock:
            main(["f", "additional"])
            mock.assert_called_once_with(fp.name)
            mock.return_value.freeze.assert_called_once_with(["additional"])

        with patch("doblib.__main__.AggregateEnvironment") as mock:
            main(["i", "additional"])
            mock.assert_called_once_with(fp.name)
            mock.return_value.init.assert_called_once_with(["additional"])

        with patch("doblib.__main__.RunEnvironment") as mock:
            main(["s", "additional"])
            mock.assert_called_once_with(fp.name)
            mock.return_value.shell.assert_called_once_with(["additional"])

            mock.reset_mock()
            main(["r", "additional"])
            mock.assert_called_once_with(fp.name)
            mock.return_value.start.assert_called_once_with(["additional"])

        with patch("doblib.__main__.CIEnvironment") as mock:
            main(["t", "additional"])
            mock.assert_called_once_with(fp.name)
            mock.return_value.test.assert_called_once_with(["additional"])

        with patch("doblib.__main__.CIEnvironment") as mock:
            main(["flake8", "additional"])
            mock.assert_called_once_with(fp.name)
            mock.return_value.ci.assert_called_once_with("flake8", ["additional"])

            mock.reset_mock()
            main(["eslint", "additional"])
            mock.assert_called_once_with(fp.name)
            mock.return_value.ci.assert_called_once_with("eslint", ["additional"])

            mock.reset_mock()
            main(["pylint", "additional"])
            mock.assert_called_once_with(fp.name)
            mock.return_value.ci.assert_called_with("pylint", ["additional"])

        with patch("doblib.__main__.ModuleEnvironment") as mock:
            main(["u", "additional"])
            mock.assert_called_once_with(fp.name)
            mock.return_value.update.assert_called_once_with(["additional"])

        with patch("doblib.__main__.ActionEnvironment") as mock:
            main(["a", "additional"])
            mock.assert_called_once_with(fp.name)
            mock.return_value.apply_action.assert_called_once_with(["additional"])

        with patch("doblib.__main__.AggregateEnvironment") as mock:
            main(["show-all-prs", "additional"])
            mock.assert_called_once_with(fp.name)
            mock.return_value.aggregate.assert_called_once_with(
                "show-all-prs", ["additional"]
            )

            mock.reset_mock()
            main(["show-closed-prs", "additional"])
            mock.assert_called_once_with(fp.name)
            mock.return_value.aggregate.assert_called_once_with(
                "show-closed-prs", ["additional"]
            )

        assert exit_mock.call_count == 12


@patch("doblib.__main__.load_arguments")
def test_help(arg_mock):
    arg = MagicMock()
    arg.command = "unknown"
    arg_mock.return_value = (arg, [])
    sys.argv = ["", "--help"]
    main()
    arg_mock.assert_called_with(["--help"])

    sys.argv = ["", "unknown"]
    arg_mock.reset_mock()
    main()
    arg_mock.assert_called_with(["--help"])
