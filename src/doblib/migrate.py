# © 2021-2022 Ruben Ortlam (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

from contextlib import closing

from . import base, utils
from .aggregate import AggregateEnvironment
from .module import ModuleEnvironment
from .run import RunEnvironment


def load_migrate_arguments(args):
    parser = utils.default_parser("migrate")
    parser.add_argument(
        "version",
        default=None,
        type=utils.Version,
        help="Target Odoo version, e.g. 15 or 15.0",
    )
    parser.add_argument(
        "--skip-premigrate",
        help="Skip pre-migrate step",
        action="store_true",
    )
    parser.add_argument(
        "--skip-migrate",
        help="Skip migrate step",
        action="store_true",
    )
    parser.add_argument(
        "--skip-postmigrate",
        help="Skip post-migrate step",
        action="store_true",
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

            if not args.skip_premigrate:
                utils.info("Run pre-migration scripts")
                self._run_migration_sql(db_name, f"pre_migrate_{version[0]}.sql")
                self._run_migration(db_name, f"pre_migrate_{version[0]}")

            if not args.skip_migrate:
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

            if not args.skip_postmigrate:
                utils.info("Run post-migration scripts")
                self._run_migration_sql(db_name, f"post_migrate_{version[0]}.sql")
                self._run_migration(db_name, f"post_migrate_{version[0]}")
            return 0
