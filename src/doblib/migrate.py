# © 2021-2022 Ruben Ortlam (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

from contextlib import closing

from . import base, utils
from .aggregate import AggregateEnvironment
from .module import ModuleEnvironment
from .run import RunEnvironment


def load_migrate_arguments(args):
    parser = utils.default_parser("init")
    parser.add_argument(
        "version",
        default=[],
        type=utils.Version,
        help="Target Odoo version, e.g. 15 or 15.0",
    )
    return parser.parse_known_args(args)


class MigrateEnvironment(AggregateEnvironment, ModuleEnvironment, RunEnvironment):
    def migrate(self, args):
        version = args.version
        self.generate_config()

        utils.info(f"Checkout Odoo {version} repos")
        retval = self.init()
        if retval:
            utils.error(f"Init step failed: {retval}")
            return retval

        if not self._init_odoo():
            return

        # pylint: disable=C0415,E0401
        import odoo
        from odoo.tools import config

        # Load the Odoo configuration
        config.parse_config(["-c", base.ODOO_CONFIG])
        odoo.cli.server.report_configuration()

        db_name = config["db_name"]
        with self._manage():
            # Ensure that the database is initialized
            db = odoo.sql_db.db_connect(db_name)
            with closing(db.cursor()) as cr:
                if not odoo.modules.db.is_initialized(cr):
                    utils.error("Odoo database not initialized")
                    return -1

            utils.info("Run pre-migration script")
            self._run_migration(db_name, f"pre_migrate_{version[0]}")
            utils.info(f"Running OpenUpgrade migration to Odoo {version}")
            open_upgrade_args = [
                "--update",
                "all",
                "--stop-after-init",
                "--load=base,web,openupgrade_framework",
            ]
            if version <= (13, 0):
                open_upgrade_args[-1] = "--load=base,web"
            retval = self.start(open_upgrade_args)
            if retval:
                utils.error(f"Upgrade step failed: {retval}")
                return retval
            utils.info("Run post-migration script")
            self._run_migration(db_name, f"post_migrate_{version[0]}")

            return 0
