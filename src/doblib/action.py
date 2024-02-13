# © 2021-2022 Florian Kantelberg (initOS GmbH)
# License Apache-2.0 (http://www.apache.org/licenses/).

import random
import string
import uuid
from datetime import date, datetime, timedelta

from dateutil.relativedelta import relativedelta

from . import base, env, utils

ALNUM = string.ascii_letters + string.digits


def load_action_arguments(args, actions=None):
    parser = utils.default_parser("action")
    parser.add_argument(
        "action",
        metavar="action",
        choices=actions or (),
        help=f"Action to run. Possible choices: {','.join(actions)}",
    )
    parser.add_argument(
        "steps",
        default=[],
        action="append",
        type=str,
        nargs="*",
        help="Specific steps to run",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Run the action as a dry-run and don't commit changes",
    )
    parser.add_argument_group(
        "Actions",
        "Database actions are defined under the `actions` section in the configuration "
        "with a name. Each database action is defined as dictionary with named steps. "
        "Each step allows the following keys:\n"
        "\n"
        "  `action`: .. Type of action. Either update, insert or delete with update "
        "as default\n"
        "  `enable` .. Option to enable/disable the step. Default is True.\n"
        "  `model`: .. The Odoo model to use. Required\n"
        "  `domain`: .. Search domain to specify specific records. Default is []\n"
        "  `context`: .. Dictionary to update the context of the environment for the action\n"
        "  `references`: .. Dictionary of unique identifiers to XML references of Odoo\n"
        "  `chunk`: .. Update or delete is done in chunks of given size. "
        "Default is 0 (no chunks)\n"
        "  `truncate`: .. The delete action uses TRUNCATE .. CASCADE on the table instead\n"
        "  `values`: .. Dictionary to define the new value of each field. Required\n\n"
        "`values` can be defined as a constant value or as dictionary which allows "
        "dynamic values. Following is possible:\n"
        "\n"
        "  `field`: .. A field name to copy the value from [n,d,t,s]\n"
        "  `lower`: .. The lower bounds for randomized values [n,d]\n"
        "  `upper`: .. The upper bounds for randomized values [n,d]\n"
        "  `prefix`: .. Prefix to add for the new value [t]\n"
        "  `suffix`: .. Suffix to add for the new value [t]\n"
        "  `length`: .. Generate a random alphanumeric value of this length [t]\n"
        "            .. Number of records to pick [m]\n"
        "  `uuid`: .. Generate a new uuid. Supported values are 1 or 4 [t]\n"
        "  `choices`: .. List of values to pick a random value [t,s]\n"
        "  `domain`: .. Domain to pick a random record from [o,m]\n"
        "\n"
        "  Additionally for Date or Datetime the specific parts of the value can be\n"
        "  replaced with a constant integer or a dict with `lower` and `upper` value.\n"
        "  Following attributes can be used as keys:\n"
        "    `year`, `month`, `day`, `hour`, `minute`, `second`"
        "\n"
        "Only available for:\n"
        "[n] Integer, Float, Monetary\n"
        "[d] Date, Datetime\n"
        "[t] Char, Html, Text\n"
        "[s] Selection\n"
        "[o] Many2one\n"
        "[m] Many2many\n",
    )
    return parser.parse_known_args(args)


class ActionEnvironment(env.Environment):
    """Class to apply actions in the environment"""

    def _apply(self, rec, name, **kw):
        """Apply an action on a field of a record"""
        field_type = rec._fields[name].type
        if field_type == "boolean":
            return self._boolean(rec, name=name, **kw)
        if field_type == "integer":
            return self._integer(rec, name=name, **kw)
        if field_type in ("float", "monetary"):
            return self._float(rec, name=name, **kw)
        if field_type == "date":
            return self._date(rec, name=name, **kw)
        if field_type == "datetime":
            return self._datetime(rec, name=name, **kw)
        if field_type in ("char", "html", "text"):
            return self._text(rec, name=name, **kw)
        if field_type == "selection":
            return self._selection(rec, name=name, **kw)
        if field_type == "many2one":
            return self._many2one(rec, name=name, **kw)
        if field_type == "many2many":
            return self._many2many(rec, name=name, **kw)
        raise TypeError("Field type is not supported by action handler")

    def _boolean(self, rec, **kw):
        """Return a value for boolean fields depending on the arguments

        * Take the value from a field of the record and interpret as boolean
        * Randomly True or False
        """
        field = kw.get("field")

        # Use the value of a different field
        if field:
            return bool(rec[field])

        return random.choice((False, True))

    def _integer(self, rec, **kw):
        """Return a value for integer fields depending on the arguments

        * Take the value from a `field` of the record
        * Random value between `lower` and `upper`
        """

        field = kw.get("field", None)

        # Use the value of a different field
        if field:
            return rec[field]

        # Randomize the value
        lower = kw.get("lower", None)
        upper = kw.get("upper", None)
        if isinstance(lower, int) and isinstance(upper, int):
            return random.randint(lower, upper)

        raise TypeError("Lower and upper bounds must be integer")

    def _float(self, rec, **kw):
        """Return a value for float fields depending on the arguments

        * Take the value from a `field` of the record
        * Random value between `lower` and `upper`
        """
        field = kw.get("field", None)

        # Use the value of a different field
        if field:
            return rec[field]

        # Randomize the value
        lower = kw.get("lower", 0.0)
        upper = kw.get("upper", 1.0)
        return random.random() * (upper - lower) + lower

    def _selection(self, rec, name, **kw):
        """Return a value for selection fields depending on the arguments

        * Take the value from a `field` of the record
        * Random value of the `choices` key
        * Random value
        """
        field = kw.get("field", None)
        # Use the value of a different field
        if field:
            return rec[field]

        choices = kw.get("choices", None)
        if choices and len(choices) > 0:
            return str(random.choice(choices))

        # Randomize the value
        return random.choice(rec._fields[name].get_values(rec.env))

    def _text(self, rec, name, **kw):
        """Return a value for text fields depending on the arguments

        * Generate a UUID if `uuid` is set. Support UUID1 and UUID4
        * Take the value from a `field` of the record. Add `prefix` and `suffix`
        * Random alphanumeric string with specific `length`. Add `prefix` and `suffix`
        * Random value of the `choices` key. Add `prefix` and `suffix`
        * Current value of the field with `prefix` and `suffix` added
        """

        # Support for uuid1 and uuid4
        vuuid = kw.get("uuid", None)
        if vuuid == 1:
            return str(uuid.uuid1())
        if vuuid == 4:
            return str(uuid.uuid4())

        # Use the value of a different field
        prefix = kw.get("prefix", "")
        suffix = kw.get("suffix", "")
        field = kw.get("field", None)
        if isinstance(field, str):
            return f"{prefix}{rec[field]}{suffix}"

        # Randomize the value
        length = kw.get("length", None)
        if isinstance(length, int) and length > 0:
            return prefix + "".join(random.choices(ALNUM, k=length)) + suffix

        # Take a random value from the choices
        choices = kw.get("choices", None)
        if choices and len(choices) > 0:
            return prefix + str(random.choice(choices)) + suffix

        return prefix + rec[name] + suffix

    def _datetime_parts(self, value, attrs):
        """Replace specific parts of a date or datetime value"""

        bounds = {
            "year": (1900, 2100),
            "month": (1, 12),
            "day": (1, 31),  # dateutil will handle the rest
            "hour": (0, 23),
            "minute": (0, 59),
            "second": (0, 59),
        }

        replacement = {}
        for name, attr in attrs.items():
            if attr is None:
                attr = {}

            if isinstance(attr, dict):
                lower, upper = bounds.get(name, (0, 0))
                lower = attr.get("lower", lower)
                upper = attr.get("upper", upper)
                replacement[name] = random.randint(lower, upper)
            else:
                replacement[name] = attr

        return value + relativedelta(**replacement)

    def _datetime(self, rec, name, **kw):
        """Return a value for datetime fields depending on the arguments

        * Take the value from a `field` of the record
        * Replacement of specific parts
        * Random value between `lower` and `upper`
        """
        field = kw.get("field", None)
        if field:
            return rec[field]

        attrs = ["year", "month", "day", "hour", "minute", "second"]
        attrs = {k: kw[k] for k in attrs if k in kw}
        if attrs:
            return self._datetime_parts(rec[name] or datetime.now(), attrs)

        lower = kw.get("lower", datetime(1970, 1, 1))
        upper = kw.get("upper", datetime.now())
        diff = upper - lower
        return lower + timedelta(seconds=random.randint(0, diff.seconds))

    def _date(self, rec, name, **kw):
        """Return a value for date fields depending on the arguments

        * Take the value from a `field` of the record
        * Replacement of specific parts
        * Random value between `lower` and `upper`
        """
        field = kw.get("field", None)
        if field:
            return rec[field]

        attrs = ["year", "month", "day"]
        attrs = {k: kw[k] for k in attrs if k in kw}
        if attrs:
            return self._datetime_parts(rec[name] or date.today(), attrs)

        lower = kw.get("lower", date(1970, 1, 1))
        upper = kw.get("upper", date.today())
        return lower + timedelta(days=random.randint(0, (upper - lower).days))

    def _many2one(self, rec, name, **kw):
        """Return a value for Many2one fields depending on the arguments

        * Replacement of the reference with a random record from a search with
          a `domain` filter
        """
        domain = kw.get("domain", [])
        records = rec[name].search(domain)
        if not records:
            return False
        return random.choice(records.ids)

    def _many2many(self, rec, name, **kw):
        """Return a value for Many2many fields depending on the arguments

        * Replacement of the references with random records from a search with
          a `domain` filter. If `length` is specified, return `length` random records.
        """
        domain = kw.get("domain", [])
        records = rec[name].search(domain)

        if not records:
            return [(5,)]

        length = kw.get("length", len(rec[name]))

        selected_records = random.sample(records.ids, min(length, len(records)))
        return [(6, 0, selected_records)]

    def _replace_references(self, env, references, values):
        resolved_refs = {}
        for key, val in references.items():
            resolved_refs[key] = env.ref(val).id

        self._replace_recursively(values, resolved_refs)

    def _replace_recursively(self, value, replace_dict):
        if isinstance(value, dict):
            iterator = value
        elif isinstance(value, list):
            iterator = range(0, len(value))
        else:
            return

        for index in iterator:
            if isinstance(value[index], str):
                if value[index] in replace_dict:
                    value[index] = replace_dict[value[index]]
            else:
                self._replace_recursively(value[index], replace_dict)

    def _action_delete(self, env, model, domain, item, *, dry_run=False):
        """Runs the delete action"""
        if model in env:
            references = item.get("references", {})
            chunk = item.get("chunk", None)
            truncate = item.get("truncate", False)

            if domain and truncate:
                utils.warn(
                    "Setting a domain is not possible with truncate. Falling back"
                )

            elif not domain and truncate:
                table = env[model]._table

                env.cr.execute(f"TRUNCATE {table} CASCADE")
                return

            self._replace_references(env, references, domain)
            records = env[model].with_context(active_test=False).search(domain)

            if records:
                if chunk:
                    for i in range(0, len(records), chunk):
                        records[i : i + chunk].unlink()
                        if not dry_run:
                            env.cr.commit()
                else:
                    records.unlink()

    def _action_update(self, env, model, domain, item, *, dry_run=False):
        """Runs the update action"""
        values = item.get("values", {})
        if not values or model not in env:
            return

        references = item.get("references", {})
        chunk = item.get("chunk", None)

        self._replace_references(env, references, domain)
        self._replace_references(env, references, values)

        records = env[model].with_context(active_test=False).search(domain)
        if not records:
            return

        # Split the values in constant and dynamic
        const, dynamic = {}, {}
        for name, apply_act in values.items():
            if name not in records._fields:
                continue

            if isinstance(apply_act, dict):
                dynamic[name] = apply_act
            else:
                const[name] = apply_act

        # Handle the constant values
        if const:
            if chunk:
                for i in range(0, len(records), chunk):
                    records[i : i + chunk].write(const)
                    if not dry_run:
                        env.cr.commit()
            else:
                records.write(const)

        # Handle the dynamic values
        if dynamic:
            counter = 0
            for rec in records:
                vals = {}
                for name, apply_act in dynamic.items():
                    vals[name] = self._apply(rec, name, **apply_act)
                rec.write(vals)

                counter += 1

                if chunk and counter >= chunk:
                    counter = 0
                    if not dry_run:
                        env.cr.commit()

    def _action_insert(self, env, model, domain, item, *, dry_run=False):
        values = item.get("values", {})
        if not domain or not values or model not in env or env[model].search(domain):
            return

        references = item.get("references", {})

        self._replace_references(env, references, domain)
        self._replace_references(env, references, values)

        env[model].with_context(active_test=False).create(values)

    def apply_action(self, args=None):
        """Apply in the configuration defined actions on the database"""
        actions = self.get("actions", default={})
        args, _ = load_action_arguments(args or [], list(actions))

        if not self._init_odoo():
            return

        # pylint: disable=C0415,E0401
        import odoo
        from odoo.tools import config

        # Load the Odoo configuration
        config.parse_config(["-c", base.ODOO_CONFIG])
        odoo.cli.server.report_configuration()

        db_name = config["db_name"]

        utils.info(f"Running {args.action}")
        with self._manage():
            with self.env(db_name, rollback=args.dry_run) as env:
                for name, item in sorted(actions[args.action].items()):
                    if not item.get("enable", True):
                        continue

                    steps = sum(args.steps, [])

                    if steps and name not in steps:
                        continue

                    utils.info(f"{args.action.capitalize()} {name}")
                    model = item.get("model")
                    if not isinstance(model, str):
                        utils.error("Model must be string")
                        continue

                    domain = item.get("domain", [])
                    if not isinstance(domain, list):
                        utils.error("Domain must be list")
                        continue

                    ctx = env.context.copy()
                    ctx.update(item.get("context") or {})
                    action_env = odoo.api.Environment(env.cr, env.uid, ctx)

                    act = item.get("action", "update")
                    if act == "update":
                        self._action_update(
                            action_env, model, domain, item, dry_run=args.dry_run
                        )
                    elif act == "delete":
                        self._action_delete(
                            action_env, model, domain, item, dry_run=args.dry_run
                        )
                    elif act == "insert":
                        self._action_insert(
                            action_env, model, domain, item, dry_run=args.dry_run
                        )
                    else:
                        utils.error(f"Undefined action {act}")
