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
        help="Target Odoo version",
    )
    return parser.parse_known_args(args)


class MigrateEnvironment(AggregateEnvironment, ModuleEnvironment, RunEnvironment):
    def migrate(self, version, args):
        version = utils.Version(version)
        self.generate_config()

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
                    utils.info("Initializing the database")
                    odoo.modules.db.initialize(cr)
                    cr.commit()

            migrate_pre_script = f"pre_migrate_{version[0]}"
            migrate_post_script = f"post_migrate_{version[0]}"
            utils.info(f"Checkout Odoo {version} repos")
            retval = self.init(args)
            if retval:
                return retval
            utils.info("Run pre-migration script")
            self._run_migration(db_name, migrate_pre_script)
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
                return retval
            utils.info("Run post-migration script")
            self._run_migration(db_name, migrate_post_script)

            return 0
