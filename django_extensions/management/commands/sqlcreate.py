# -*- coding: utf-8 -*-
import socket
import sys
import warnings

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import DEFAULT_DB_ALIAS

from django_extensions.management.utils import signalcommand
from django_extensions.utils.deprecation import RemovedInNextVersionWarning
from django_extensions.settings import SQLITE_ENGINES, POSTGRESQL_ENGINES, MYSQL_ENGINES


class Command(BaseCommand):
    help = """Generates the SQL to create your database for you, as specified in settings.py
The envisioned use case is something like this:

    ./manage.py sqlcreate [--database=<databasename>] | mysql -u <db_administrator> -p
    ./manage.py sqlcreate [--database=<databasname>] | psql -U <db_administrator> -W"""

    requires_system_checks = False
    can_import_settings = True

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            '-R', '--router', action='store', dest='router', default=DEFAULT_DB_ALIAS,
            help='Use this router-database other then defined in settings.py'
        )
        parser.add_argument(
            '--database',
            default=DEFAULT_DB_ALIAS,
            help=f'Nominates a database to run command for. Defaults to the "{DEFAULT_DB_ALIAS}" database.',
        )
        parser.add_argument(
            '-D', '--drop', action='store_true', dest='drop', default=False,
            help='If given, includes commands to drop any existing user and database.'
        )

    @signalcommand
    def handle(self, *args, **options):
        database = options['database']
        if options['router'] != DEFAULT_DB_ALIAS:
            warnings.warn("--router is deprecated. You should use --database.", RemovedInNextVersionWarning, stacklevel=2)
            database = options['router']

        dbinfo = settings.DATABASES.get(database)
        if dbinfo is None:
            raise CommandError(f"Unknown database {database}")

        engine = dbinfo.get('ENGINE')
        dbuser = dbinfo.get('USER')
        dbpass = dbinfo.get('PASSWORD')
        dbname = dbinfo.get('NAME')
        dbhost = dbinfo.get('HOST')
        dbclient = socket.gethostname()

        # django settings file tells you that localhost should be specified by leaving
        # the DATABASE_HOST blank
        if not dbhost:
            dbhost = 'localhost'

        if engine in SQLITE_ENGINES:
            sys.stderr.write("-- manage.py migrate will automatically create a sqlite3 database file.\n")
        elif engine in MYSQL_ENGINES:
            sys.stderr.write("""-- WARNING!: https://docs.djangoproject.com/en/dev/ref/databases/#collation-settings
-- Please read this carefully! Collation will be set to utf8_bin to have case-sensitive data.
""")
            print(f"CREATE DATABASE {dbname} CHARACTER SET utf8 COLLATE utf8_bin;")
            print(
                f"GRANT ALL PRIVILEGES ON {dbname}.* to '{dbuser}'@'{dbclient}' identified by '{dbpass}';"
            )
        elif engine in POSTGRESQL_ENGINES:
            if options['drop']:
                print(f"DROP DATABASE IF EXISTS {dbname};")
                if dbuser:
                    print(f"DROP USER IF EXISTS {dbuser};")

            if dbuser and dbpass:
                print(f"CREATE USER {dbuser} WITH ENCRYPTED PASSWORD '{dbpass}' CREATEDB;")
                print("CREATE DATABASE %s WITH ENCODING 'UTF-8' OWNER \"%s\";" % (dbname, dbuser))
                print(f"GRANT ALL PRIVILEGES ON DATABASE {dbname} TO {dbuser};")
            else:
                print(
                    "-- Assuming that unix domain socket connection mode is being used because\n"
                    "-- USER or PASSWORD are blank in Django DATABASES configuration."
                )
                print(f"CREATE DATABASE {dbname} WITH ENCODING 'UTF-8';")
        else:
            # CREATE DATABASE is not SQL standard, but seems to be supported by most.
            sys.stderr.write("-- Don't know how to handle '%s' falling back to SQL.\n" % engine)
            print(f"CREATE DATABASE {dbname};")
            print(f"GRANT ALL PRIVILEGES ON DATABASE {dbname} to {dbuser};")
