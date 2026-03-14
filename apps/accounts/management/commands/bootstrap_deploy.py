import os

from django.core.management import call_command
from django.core.management.base import BaseCommand


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).lower() in ('true', '1', 'yes', 'on')


class Command(BaseCommand):
    help = (
        'Run deploy bootstrap steps for no-shell platforms '
        '(migrate, seed initial data, ensure superuser). '
        'Use --fresh or DJANGO_DEPLOY_FRESH=true to wipe all data first.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--skip-collectstatic',
            action='store_true',
            help='Skip collectstatic.',
        )
        parser.add_argument(
            '--skip-superuser',
            action='store_true',
            help='Skip ensure_superuser.',
        )
        parser.add_argument(
            '--fresh',
            action='store_true',
            help='Wipe all data and re-seed from scratch. '
                 'Also triggered by DJANGO_DEPLOY_FRESH=true env var.',
        )

    def handle(self, *args, **options):
        fresh = options['fresh'] or env_bool('DJANGO_DEPLOY_FRESH', False)

        self.stdout.write('Running database migrations...')
        call_command('migrate', interactive=False)

        if fresh:
            self.stdout.write(self.style.WARNING(
                'FRESH DEPLOY: Flushing all data from the database...'
            ))
            call_command('flush', interactive=False)

        if options['skip_collectstatic']:
            self.stdout.write('Skipping static collection.')
        else:
            self.stdout.write('Collecting static files...')
            call_command('collectstatic', interactive=False, verbosity=0)

        if options['skip_superuser']:
            self.stdout.write('Skipping superuser bootstrap.')
        else:
            self.stdout.write('Seeding initial data and superuser...')
            call_command('setup_initial_data', '--force-password-reset')

        self.stdout.write(self.style.SUCCESS('Deploy bootstrap complete.'))
