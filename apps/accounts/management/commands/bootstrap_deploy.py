from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        'Run deploy bootstrap steps for no-shell platforms '
        '(migrate, collectstatic, ensure_superuser).'
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

    def handle(self, *args, **options):
        self.stdout.write('Running database migrations...')
        call_command('migrate', interactive=False)

        if options['skip_collectstatic']:
            self.stdout.write('Skipping static collection.')
        else:
            self.stdout.write('Collecting static files...')
            call_command('collectstatic', interactive=False, verbosity=0)

        if options['skip_superuser']:
            self.stdout.write('Skipping superuser bootstrap.')
        else:
            self.stdout.write('Ensuring deploy superuser exists...')
            call_command('ensure_superuser', '--force-password-reset')

        self.stdout.write(self.style.SUCCESS('Deploy bootstrap complete.'))
