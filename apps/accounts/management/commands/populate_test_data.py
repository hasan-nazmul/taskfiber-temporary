import random
from datetime import timedelta
from django.utils import timezone
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from apps.accounts.models import Role, Employee, ModuleAccess, Team
from apps.customers.models import Area, Package, Customer
from apps.stock.models import StockCategory, StockItem, StockTransaction
from apps.tickets.models import Ticket, TicketComment, TicketStatusLog, TicketStockUsage
from apps.schedule.models import Schedule, Attendance, LeaveRequest


class Command(BaseCommand):
    help = 'Wipes the database and populates it with realistic test data'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING('Wiping existing data...'))

        # Delete in dependency order to avoid ProtectedErrors
        LeaveRequest.objects.all().delete()
        Attendance.objects.all().delete()
        Schedule.objects.all().delete()
        TicketStockUsage.objects.all().delete()
        TicketStatusLog.objects.all().delete()
        TicketComment.objects.all().delete()
        Ticket.objects.all().delete()
        Customer.objects.all().delete()
        StockTransaction.objects.all().delete()
        StockItem.objects.all().delete()
        StockCategory.objects.all().delete()
        Package.objects.all().delete()
        Area.objects.all().delete()
        Team.objects.all().delete()
        ModuleAccess.objects.all().delete()
        Employee.objects.all().delete()
        User.objects.all().delete()
        Role.objects.all().delete()

        self.stdout.write(self.style.SUCCESS('Data wiped. Starting population...'))
        now = timezone.now()

        # ── 1. Roles ──
        roles = {}
        for name, slug, desc in [
            ('Owner', 'owner', 'System owner with full access'),
            ('Manager', 'manager', 'Office manager'),
            ('Marketing', 'marketing', 'Marketing team member'),
            ('Support Agent', 'support_agent', 'Customer support agent'),
            ('Cable Technician', 'cable_technician', 'Cable/fiber technician'),
            ('Field Technician', 'field_technician', 'Field technician'),
            ('Accountant', 'accountant', 'Accounts/billing staff'),
        ]:
            roles[slug], _ = Role.objects.get_or_create(slug=slug, defaults={'name': name, 'description': desc})
        self.stdout.write('  Roles created')

        # ── 2. Employees (phone = login credential) ──
        self.stdout.write('Creating Employees...')
        DEFAULT_PASSWORD = 'taskfiber2026'

        employees_data = [
            # (first, last, phone, role_slug, department, salary)
            ('Rafiq', 'Ahmed', '01712345601', 'owner', 'management', 50000),
            ('Nasrin', 'Akter', '01812345602', 'manager', 'management', 35000),
            ('Jamal', 'Hossain', '01912345603', 'support_agent', 'support', 18000),
            ('Shima', 'Begum', '01612345604', 'support_agent', 'support', 17000),
            ('Belal', 'Mia', '01712345605', 'cable_technician', 'technical', 15000),
            ('Sohel', 'Rana', '01812345606', 'cable_technician', 'technical', 15000),
            ('Tofazzal', 'Sarker', '01912345607', 'field_technician', 'technical', 14000),
            ('Rony', 'Das', '01312345608', 'field_technician', 'technical', 14000),
            ('Monowar', 'Islam', '01512345609', 'marketing', 'marketing', 16000),
            ('Fatema', 'Khatun', '01612345610', 'accountant', 'accounts', 20000),
        ]

        emps = {}
        for i, (fname, lname, phone, role_slug, dept, salary) in enumerate(employees_data):
            user = User.objects.create_user(
                username=phone, password=DEFAULT_PASSWORD,
                first_name=fname, last_name=lname,
            )
            if role_slug == 'owner':
                user.is_superuser = True
                user.is_staff = True
                user.save()

            emp = Employee.objects.create(
                user=user, employee_id=f'EMP-{1001 + i}',
                role=roles[role_slug], phone=phone,
                department=dept, salary=salary,
                date_joined_company=now.date() - timedelta(days=random.randint(60, 500)),
            )
            emps[role_slug] = emps.get(role_slug, [])
            emps[role_slug].append(emp)

            # Module access
            access_map = {
                'owner': dict(tickets_access='full', customers_access='full', zones_access='full', stock_access='full', schedule_access='full', employees_access='full', teams_access='full', accounts_finance_access='full'),
                'manager': dict(tickets_access='full', customers_access='full', zones_access='full', stock_access='full', schedule_access='full', employees_access='full', teams_access='full', accounts_finance_access='full'),
                'support_agent': dict(tickets_access='full', customers_access='edit', zones_access='view', stock_access='view', schedule_access='view', employees_access='none', teams_access='none', accounts_finance_access='none'),
                'cable_technician': dict(tickets_access='edit', customers_access='view', zones_access='none', stock_access='view', schedule_access='view', employees_access='none', teams_access='none', accounts_finance_access='none'),
                'field_technician': dict(tickets_access='edit', customers_access='view', zones_access='none', stock_access='view', schedule_access='view', employees_access='none', teams_access='none', accounts_finance_access='none'),
                'marketing': dict(tickets_access='view', customers_access='edit', zones_access='view', stock_access='none', schedule_access='view', employees_access='none', teams_access='none', accounts_finance_access='none'),
                'accountant': dict(tickets_access='view', customers_access='view', zones_access='none', stock_access='view', schedule_access='none', employees_access='none', teams_access='none', accounts_finance_access='full'),
            }
            ModuleAccess.objects.create(employee=emp, **access_map[role_slug])

        owner = emps['owner'][0]
        manager = emps['manager'][0]
        techs = emps['cable_technician'] + emps['field_technician']
        support_agents = emps['support_agent']

        # ── 3. Teams ──
        self.stdout.write('Creating Teams...')
        team_fiber = Team.objects.create(name='Fiber Installation Team', description='Handles new fiber connections and line repairs')
        team_fiber.leader = emps['cable_technician'][0]
        team_fiber.save()
        team_fiber.members.set(emps['cable_technician'])

        team_field = Team.objects.create(name='Field Support Team', description='On-site troubleshooting and router replacement')
        team_field.leader = emps['field_technician'][0]
        team_field.save()
        team_field.members.set(emps['field_technician'])

        teams = [team_fiber, team_field]

        # ── 4. Areas / Zones ──
        self.stdout.write('Creating Zones...')
        areas_data = [
            ('Gulshan', 'GUL01', 'Gulshan area including Circle 1 & 2'),
            ('Banani', 'BAN01', 'Banani residential and commercial zone'),
            ('Dhanmondi', 'DHN01', 'Dhanmondi residential area'),
            ('Uttara', 'UTT01', 'Uttara Sector 1 to 14'),
            ('Mirpur', 'MIR01', 'Mirpur and surrounding areas'),
            ('Mohammadpur', 'MOH01', 'Mohammadpur and Adabor'),
            ('Bashundhara', 'BSH01', 'Bashundhara R/A blocks'),
            ('Badda', 'BAD01', 'Badda, Merul Badda, Aftab Nagar'),
        ]
        areas = []
        for name, code, desc in areas_data:
            areas.append(Area.objects.create(name=name, zone_code=code, description=desc))
        # one inactive zone
        areas.append(Area.objects.create(name='Old Town', zone_code='OLD01', description='Discontinued coverage', is_active=False))

        # ── 5. Packages ──
        self.stdout.write('Creating Packages...')
        pkgs_data = [
            ('Starter 5 Mbps', 5, 500, 'home'),
            ('Basic 10 Mbps', 10, 700, 'home'),
            ('Standard 15 Mbps', 15, 900, 'home'),
            ('Premium 25 Mbps', 25, 1200, 'home'),
            ('Ultra 40 Mbps', 40, 1800, 'home'),
            ('Business 50 Mbps', 50, 3000, 'business'),
            ('Business Plus 100 Mbps', 100, 5000, 'business'),
            ('Corporate 200 Mbps', 200, 10000, 'corporate'),
        ]
        pkgs = [Package.objects.create(name=n, bandwidth_mbps=m, price=p, package_type=t) for n, m, p, t in pkgs_data]

        # ── 6. Customers ──
        self.stdout.write('Creating Customers...')
        bd_first = ['Abdul', 'Mohammad', 'Nur', 'Shahid', 'Aminul', 'Kamrul', 'Zahir', 'Rakib', 'Tanvir',
                     'Shafiq', 'Masum', 'Habib', 'Faisal', 'Imran', 'Nayeem', 'Tareq', 'Jubayer', 'Sajid',
                     'Arif', 'Rezaul', 'Sazzad', 'Maruf', 'Joynal', 'Ashik', 'Billal',
                     'Rumana', 'Taslima', 'Farzana', 'Sabina', 'Mithila']
        bd_last = ['Hasan', 'Islam', 'Rahman', 'Alam', 'Hossain', 'Uddin', 'Khan', 'Chowdhury', 'Mia',
                   'Sarker', 'Ahmed', 'Karim', 'Jahan', 'Khatun', 'Begum']

        active_areas = [a for a in areas if a.is_active]
        home_pkgs = [p for p in pkgs if p.package_type == 'home']
        biz_pkgs = [p for p in pkgs if p.package_type in ['business', 'corporate']]
        statuses = ['active'] * 7 + ['suspended', 'pending', 'inactive']

        customers = []
        for i in range(1, 41):
            fname = random.choice(bd_first)
            lname = random.choice(bd_last)
            area = random.choice(active_areas)
            pkg = random.choice(home_pkgs) if random.random() < 0.8 else random.choice(biz_pkgs)
            c = Customer.objects.create(
                name=f'{fname} {lname}',
                phone=f'017{random.randint(10000000, 99999999)}',
                address=f'House {random.randint(1, 120)}, Road {random.randint(1, 30)}, {area.name}',
                area=area,
                package=pkg,
                monthly_amount=pkg.price,
                connection_type=random.choice(['fiber', 'fiber', 'fiber', 'cable']),
                connection_date=now.date() - timedelta(days=random.randint(30, 400)),
                status=random.choice(statuses),
                billing_date=random.choice([1, 5, 10, 15]),
                ip_address=f'10.{random.randint(0,3)}.{random.randint(1,254)}.{random.randint(2,254)}',
                pppoe_username=f'{fname.lower()}{i}@taskfiber',
            )
            customers.append(c)

        # ── 7. Stock ──
        self.stdout.write('Creating Stock...')
        cats = {
            'router': StockCategory.objects.create(name='Router', slug='router', description='Routers and ONUs'),
            'cable': StockCategory.objects.create(name='Cable', slug='cable', description='Fiber and coaxial cables'),
            'connector': StockCategory.objects.create(name='Connector', slug='connector', description='Connectors and splitters'),
            'tools': StockCategory.objects.create(name='Tools', slug='tools', description='Installation tools'),
        }
        stock_data = [
            ('TP-Link Archer C6 v4', cats['router'], 'RTR-TPC6', 'piece', 45, 5, 2800, 3500),
            ('V-Sol ONU 1GE', cats['router'], 'ONU-VS1G', 'piece', 60, 10, 1200, 1800),
            ('Netis WF2780', cats['router'], 'RTR-NTW8', 'piece', 15, 3, 2200, 3000),
            ('2 Core Drop Cable', cats['cable'], 'CBL-2CD', 'meter', 8000, 500, 8, 15),
            ('4 Core Drop Cable', cats['cable'], 'CBL-4CD', 'meter', 3000, 200, 12, 22),
            ('SC/APC Connector', cats['connector'], 'CON-SCAP', 'piece', 200, 30, 25, 50),
            ('RJ45 Cat6', cats['connector'], 'CON-RJ45', 'box', 40, 5, 350, 600),
            ('Fiber Splitter 1x8', cats['connector'], 'SPL-1X8', 'piece', 20, 5, 600, 1000),
            ('Crimping Tool', cats['tools'], 'TL-CRMP', 'piece', 8, 2, 800, 0),
            ('OTDR Meter', cats['tools'], 'TL-OTDR', 'piece', 2, 1, 45000, 0),
        ]
        stock_items = []
        for name, cat, sku, unit, qty, min_lvl, pp, sp in stock_data:
            item = StockItem.objects.create(
                name=name, category=cat, sku=sku, unit=unit,
                quantity_in_stock=qty, minimum_stock_level=min_lvl,
                purchase_price=pp, selling_price=sp,
            )
            stock_items.append(item)
            StockTransaction.objects.create(
                stock_item=item, transaction_type='purchase', quantity=qty,
                performed_by=manager, notes='Initial stock entry', unit_price=pp,
            )

        # ── 8. Tickets ──
        self.stdout.write('Creating Tickets...')
        ticket_templates = [
            ('new_connection', 'New fiber connection request'),
            ('line_cut', 'Internet disconnected since morning'),
            ('speed_slow', 'Getting only 2 Mbps on 20 Mbps plan'),
            ('adapter_issue', 'ONU showing red light'),
            ('line_cut', 'Cable cut during road construction'),
            ('password_change', 'PPPoE password reset needed'),
            ('tv_connect', 'Want to connect smart TV via fiber'),
            ('support_other', 'Billing query about last month'),
            ('line_shift', 'Shifting to new house same area'),
            ('speed_slow', 'Buffering on YouTube in the evening'),
            ('new_connection', 'New connection for office'),
            ('adapter_issue', 'Router keeps restarting'),
            ('line_cut', 'No internet after power cut'),
            ('area_coverage', 'Checking coverage for Sector 12'),
            ('support_other', 'Want to upgrade package'),
        ]
        priorities = ['low', 'medium', 'medium', 'high', 'urgent']
        sources = ['phone', 'phone', 'whatsapp', 'walk_in', 'marketing']

        comments_pool = [
            'Called customer, confirmed the issue.',
            'Technician dispatched to the location.',
            'Customer not available, will try again tomorrow.',
            'Checked ONU — red light confirmed. Replacing unit.',
            'Cable splice done. Testing signal.',
            'Customer confirmed internet is back.',
            'Escalated to senior technician.',
            'Waiting for customer to confirm timing.',
            'Router replaced successfully.',
            'Payment pending, customer will pay tomorrow.',
        ]

        for i in range(1, 26):
            ttype, desc = random.choice(ticket_templates)
            created_dt = now - timedelta(days=random.randint(0, 7), hours=random.randint(1, 16))
            cust = random.choice(customers)
            creator = random.choice(support_agents)

            t = Ticket.objects.create(
                ticket_type=ttype,
                source=random.choice(sources),
                priority=random.choice(priorities),
                customer=cust,
                contact_name=cust.name,
                contact_phone=cust.phone,
                area=cust.area,
                title=desc,
                description=f'{cust.name} reported: {desc.lower()}',
                status='open',
                created_by=creator,
            )
            Ticket.objects.filter(id=t.id).update(created_at=created_dt)

            action_dt = created_dt + timedelta(minutes=random.randint(5, 90))

            # ~70% get assigned
            if random.random() > 0.3:
                team = random.choice(teams)
                assignee = random.choice(list(team.members.all()))
                t.assigned_team = team
                t.assigned_to = assignee
                t.status = 'assigned'
                t.assigned_at = action_dt
                t.save()

                TicketStatusLog.objects.create(
                    ticket=t, old_status='open', new_status='assigned',
                    changed_by=creator, notes=f'Assigned to {assignee.full_name}',
                )
                TicketStatusLog.objects.filter(ticket=t).update(created_at=action_dt)

                # Add a comment
                TicketComment.objects.create(
                    ticket=t, author=random.choice(support_agents + [assignee]),
                    comment=random.choice(comments_pool),
                )
                TicketComment.objects.filter(ticket=t, created_at__gte=now - timedelta(seconds=5)).update(created_at=action_dt + timedelta(minutes=random.randint(5, 30)))

                action_dt += timedelta(minutes=random.randint(30, 180))

                # ~60% go in_progress
                if random.random() > 0.4:
                    t.status = 'in_progress'
                    t.save()
                    log = TicketStatusLog.objects.create(
                        ticket=t, old_status='assigned', new_status='in_progress',
                        changed_by=assignee,
                    )
                    TicketStatusLog.objects.filter(id=log.id).update(created_at=action_dt)

                    # Stock usage for physical work tickets
                    if ttype in ['line_cut', 'new_connection', 'adapter_issue', 'line_shift']:
                        item = random.choice(stock_items[:6])  # routers, cables, connectors
                        qty = random.randint(1, 3) if item.unit == 'piece' else random.randint(10, 80)
                        uso = TicketStockUsage.objects.create(
                            ticket=t, stock_item=item, quantity_used=qty,
                            added_by=assignee, notes='Used for repair/installation',
                        )
                        TicketStockUsage.objects.filter(id=uso.id).update(created_at=action_dt)

                    action_dt += timedelta(minutes=random.randint(20, 120))

                    # ~50% get resolved
                    if random.random() > 0.5:
                        t.status = 'resolved'
                        t.resolution_notes = random.choice([
                            'Issue fixed at customer end.',
                            'Router replaced, signal restored.',
                            'Cable re-spliced, connection stable.',
                            'PPPoE credentials reset and tested.',
                            'New connection installed successfully.',
                        ])
                        t.resolved_at = action_dt
                        t.resolved_by = assignee
                        t.save()
                        log = TicketStatusLog.objects.create(
                            ticket=t, old_status='in_progress', new_status='resolved',
                            changed_by=assignee, notes=t.resolution_notes,
                        )
                        TicketStatusLog.objects.filter(id=log.id).update(created_at=action_dt)

        # ── 9. Schedule & Attendance (last 7 days) ──
        self.stdout.write('Creating Schedules & Attendance...')
        shifts = ['morning', 'morning', 'morning', 'evening', 'full_day']
        for day_offset in range(7):
            d = now.date() - timedelta(days=day_offset)
            for tech in techs:
                Schedule.objects.create(
                    employee=tech, date=d, shift=random.choice(shifts),
                    assigned_area=random.choice(active_areas),
                    created_by=manager,
                )
                if day_offset > 0:  # attendance for past days only
                    att_status = random.choices(
                        ['present', 'present', 'present', 'late', 'absent'],
                        weights=[5, 5, 5, 2, 1], k=1
                    )[0]
                    Attendance.objects.create(
                        employee=tech, date=d, status=att_status,
                        check_in='08:00' if att_status != 'absent' else None,
                        check_out='16:00' if att_status == 'present' else ('16:30' if att_status == 'late' else None),
                        marked_by=manager,
                    )

        # ── 10. Leave Requests ──
        for agent in support_agents:
            LeaveRequest.objects.create(
                employee=agent,
                leave_type=random.choice(['casual', 'sick']),
                start_date=now.date() + timedelta(days=random.randint(3, 10)),
                end_date=now.date() + timedelta(days=random.randint(11, 14)),
                reason='Personal matter / feeling unwell',
                status='pending',
            )

        # ── Summary ──
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS('  Test data populated successfully!'))
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write('')
        self.stdout.write(f'  Employees: {Employee.objects.count()}')
        self.stdout.write(f'  Customers: {Customer.objects.count()}')
        self.stdout.write(f'  Zones:     {Area.objects.count()}')
        self.stdout.write(f'  Packages:  {Package.objects.count()}')
        self.stdout.write(f'  Stock:     {StockItem.objects.count()} items')
        self.stdout.write(f'  Tickets:   {Ticket.objects.count()}')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('  Login Credentials (phone → password):'))
        self.stdout.write(f'  Owner:      01712345601 → {DEFAULT_PASSWORD}')
        self.stdout.write(f'  Manager:    01812345602 → {DEFAULT_PASSWORD}')
        self.stdout.write(f'  Support:    01912345603 → {DEFAULT_PASSWORD}')
        self.stdout.write(f'  Technician: 01712345605 → {DEFAULT_PASSWORD}')
        self.stdout.write(f'  Accountant: 01612345610 → {DEFAULT_PASSWORD}')
        self.stdout.write('')

