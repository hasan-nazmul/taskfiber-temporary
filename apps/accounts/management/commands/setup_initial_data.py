from django.core.management.base import BaseCommand
from django.core.management import call_command
from apps.accounts.models import Role
from apps.customers.models import Area, Package
from apps.stock.models import StockCategory


class Command(BaseCommand):
    help = 'Setup initial data for the ISP Manager system'

    def handle(self, *args, **kwargs):
        self.stdout.write('Setting up initial data...\n')

        # --- Roles ---
        roles_data = [
            ('Owner', 'owner', 'System owner with full access'),
            ('Manager', 'manager', 'Office manager'),
            ('Marketing', 'marketing', 'Marketing team member'),
            ('Support Agent', 'support_agent', 'Customer support agent'),
            ('Cable Technician', 'cable_technician', 'Cable/fiber technician'),
            ('Field Technician', 'field_technician', 'Field technician'),
            ('Accountant', 'accountant', 'Accounts/billing staff'),
        ]

        for name, slug, desc in roles_data:
            role, created = Role.objects.get_or_create(
                slug=slug,
                defaults={'name': name, 'description': desc}
            )
            status = 'Created' if created else 'Exists'
            self.stdout.write(f'  Role: {name} [{status}]')

        # --- Areas ---
        areas_data = [
            ('Amin Colony', 'AC01'),
            ('Belghoria', 'BG01'),
            ('Town Center', 'TC01'),
            ('Station Road', 'SR01'),
            ('College Para', 'CP01'),
            ('Hospital Road', 'HR01'),
            ('Market Area', 'MA01'),
            ('New Town', 'NT01'),
        ]

        for name, code in areas_data:
            area, created = Area.objects.get_or_create(
                zone_code=code,
                defaults={'name': name}
            )
            status = 'Created' if created else 'Exists'
            self.stdout.write(f'  Area: {name} [{status}]')

        # --- Packages ---
        packages_data = [
            ('Basic 5', 5, 500, 'home'),
            ('Standard 10', 10, 700, 'home'),
            ('Premium 20', 20, 1000, 'home'),
            ('Ultra 30', 30, 1500, 'home'),
            ('Business 50', 50, 3000, 'business'),
            ('Corporate 100', 100, 5000, 'corporate'),
        ]

        for name, mbps, price, pkg_type in packages_data:
            pkg, created = Package.objects.get_or_create(
                name=name,
                defaults={
                    'bandwidth_mbps': mbps,
                    'price': price,
                    'package_type': pkg_type,
                }
            )
            status = 'Created' if created else 'Exists'
            self.stdout.write(f'  Package: {name} [{status}]')

        # --- Stock Categories ---
        categories_data = [
            ('Cable', 'cable', 'Fiber and coaxial cables'),
            ('Router', 'router', 'Routers and ONUs'),
            ('Connector', 'connector', 'RJ45, fiber connectors, splitters'),
            ('Adapter', 'adapter', 'Power adapters and media converters'),
            ('Switch', 'switch', 'Network switches'),
            ('Tools', 'tools', 'Installation tools'),
            ('Accessories', 'accessories', 'Misc accessories'),
        ]

        for name, slug, desc in categories_data:
            cat, created = StockCategory.objects.get_or_create(
                slug=slug,
                defaults={'name': name, 'description': desc}
            )
            status = 'Created' if created else 'Exists'
            self.stdout.write(f'  Stock Category: {name} [{status}]')

        # --- Optional deploy superuser (env-based) ---
        self.stdout.write('\n  Running optional superuser bootstrap from environment...')
        call_command('ensure_superuser')

        self.stdout.write(self.style.SUCCESS('\n✅ Initial data setup complete!'))
