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
        DEFAULT_PASSWORD = 'test1234'

        employees_data = [
            # (first, last, phone, role_slug, department, salary)
            ('Kamal', 'Hossain', '01911001001', 'owner', 'management', 60000),
            ('Shahana', 'Parveen', '01811002002', 'manager', 'management', 40000),
            ('Mizanur', 'Rahman', '01711003003', 'support_agent', 'support', 20000),
            ('Tahmina', 'Sultana', '01611004004', 'support_agent', 'support', 19000),
            ('Liton', 'Barua', '01511005005', 'support_agent', 'support', 18500),
            ('Alamgir', 'Kabir', '01911006006', 'cable_technician', 'technical', 16000),
            ('Sumon', 'Dey', '01811007007', 'cable_technician', 'technical', 15500),
            ('Hasibul', 'Haque', '01711008008', 'field_technician', 'technical', 15000),
            ('Palash', 'Ghosh', '01311009009', 'field_technician', 'technical', 14500),
            ('Nazmul', 'Huda', '01511010010', 'field_technician', 'technical', 14000),
            ('Sharmin', 'Jahan', '01611011011', 'marketing', 'marketing', 18000),
            ('Roksana', 'Akhter', '01911012012', 'accountant', 'accounts', 22000),
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
                user=user, employee_id=f'EMP-{2001 + i}',
                role=roles[role_slug], phone=phone,
                department=dept, salary=salary,
                date_joined_company=now.date() - timedelta(days=random.randint(90, 700)),
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
        team_install = Team.objects.create(name='Installation Squad', description='New fiber and cable installations across all zones')
        team_install.leader = emps['cable_technician'][0]
        team_install.save()
        team_install.members.set(emps['cable_technician'])

        team_maintenance = Team.objects.create(name='Maintenance Crew', description='Ongoing repairs, troubleshooting, and equipment replacement')
        team_maintenance.leader = emps['field_technician'][0]
        team_maintenance.save()
        team_maintenance.members.set(emps['field_technician'])

        team_network = Team.objects.create(name='Network Response Unit', description='Emergency network outages and critical issue response')
        team_network.leader = emps['cable_technician'][1]
        team_network.save()
        team_network.members.add(emps['cable_technician'][1], emps['field_technician'][0])

        teams = [team_install, team_maintenance, team_network]

        # ── 4. Areas / Zones ──
        self.stdout.write('Creating Zones...')
        areas_data = [
            ('Khilgaon', 'KHL01', 'Khilgaon and Goran residential area'),
            ('Rampura', 'RMP01', 'Rampura TV Gate to Banasree'),
            ('Malibagh', 'MLB01', 'Malibagh Chowdhury Para and surroundings'),
            ('Shantinagar', 'SHN01', 'Shantinagar, Kakrail, and Ramna'),
            ('Jatrabari', 'JTR01', 'Jatrabari to Postogola zone'),
            ('Mugda', 'MGD01', 'Mugda Medical and surrounding blocks'),
            ('Motijheel', 'MTJ01', 'Motijheel commercial area'),
            ('Paltan', 'PLT01', 'Paltan and Purana Paltan'),
            ('Kamalapur', 'KML01', 'Kamalapur railway station area'),
            ('Wari', 'WAR01', 'Wari and Narinda old town'),
        ]
        areas = []
        for name, code, desc in areas_data:
            areas.append(Area.objects.create(name=name, zone_code=code, description=desc))
        # two inactive zones
        areas.append(Area.objects.create(name='Demra', zone_code='DMR01', description='Coverage discontinued', is_active=False))
        areas.append(Area.objects.create(name='Keraniganj', zone_code='KRN01', description='Under evaluation', is_active=False))

        # ── 5. Packages ──
        self.stdout.write('Creating Packages...')
        pkgs_data = [
            ('Lite 5 Mbps', 5, 400, 'home'),
            ('Home 10 Mbps', 10, 600, 'home'),
            ('Home Plus 20 Mbps', 20, 850, 'home'),
            ('Family 30 Mbps', 30, 1100, 'home'),
            ('Pro 50 Mbps', 50, 1600, 'home'),
            ('SME 60 Mbps', 60, 2500, 'business'),
            ('Enterprise 100 Mbps', 100, 4500, 'business'),
            ('Dedicated 150 Mbps', 150, 7500, 'corporate'),
            ('Dedicated 250 Mbps', 250, 12000, 'corporate'),
        ]
        pkgs = [Package.objects.create(name=n, bandwidth_mbps=m, price=p, package_type=t) for n, m, p, t in pkgs_data]

        # ── 6. Customers ──
        self.stdout.write('Creating Customers...')
        bd_first = ['Abul', 'Rafiq', 'Shahin', 'Masud', 'Babul', 'Hanif', 'Salim', 'Dulal', 'Jasim',
                     'Monir', 'Iqbal', 'Selim', 'Faruk', 'Kabir', 'Nurul', 'Jahid', 'Shohag', 'Liakat',
                     'Rubel', 'Shuvo', 'Shimul', 'Ratan', 'Polash', 'Mizan', 'Sujan',
                     'Nazma', 'Rehana', 'Shathi', 'Lovely', 'Moni']
        bd_last = ['Hossain', 'Mollah', 'Talukder', 'Bepari', 'Mondol', 'Pramanik', 'Biswas', 'Sikder',
                   'Majumder', 'Saha', 'Roy', 'Nath', 'Gazi', 'Sheikh', 'Matubbar']

        active_areas = [a for a in areas if a.is_active]
        home_pkgs = [p for p in pkgs if p.package_type == 'home']
        biz_pkgs = [p for p in pkgs if p.package_type in ['business', 'corporate']]
        statuses = ['active'] * 7 + ['suspended', 'pending', 'inactive']
        connection_types = ['fiber', 'fiber', 'fiber', 'cable', 'wireless']

        customers = []
        used_phones = set()
        for i in range(1, 51):
            fname = random.choice(bd_first)
            lname = random.choice(bd_last)
            area = random.choice(active_areas)
            pkg = random.choice(home_pkgs) if random.random() < 0.75 else random.choice(biz_pkgs)
            status = random.choice(statuses)

            while True:
                phone = f'018{random.randint(10000000, 99999999)}'
                if phone not in used_phones:
                    used_phones.add(phone)
                    break

            c = Customer.objects.create(
                name=f'{fname} {lname}',
                phone=phone,
                address=f'Basha {random.randint(1, 200)}, Lane {random.randint(1, 40)}, {area.name}',
                area=area,
                package=pkg,
                monthly_amount=pkg.price,
                connection_type=random.choice(connection_types),
                connection_date=now.date() - timedelta(days=random.randint(15, 500)),
                status=status,
                billing_date=random.choice([1, 5, 10, 15, 20, 25]),
                ip_address=f'10.{random.randint(0,5)}.{random.randint(1,254)}.{random.randint(2,254)}',
                pppoe_username=f'{fname.lower()}{i}@taskfiber',
                due_amount=random.choice([0, 0, 0, 0, pkg.price, pkg.price * 2]) if status in ['active', 'suspended'] else 0,
                last_payment_date=now.date() - timedelta(days=random.randint(1, 60)) if status == 'active' else None,
            )
            customers.append(c)

        # ── 7. Stock ──
        self.stdout.write('Creating Stock...')
        cats = {
            'router': StockCategory.objects.create(name='Router', slug='router', description='Routers and ONUs'),
            'cable': StockCategory.objects.create(name='Cable', slug='cable', description='Fiber and coaxial cables'),
            'connector': StockCategory.objects.create(name='Connector', slug='connector', description='Connectors, splitters, and adapters'),
            'tools': StockCategory.objects.create(name='Tools', slug='tools', description='Installation and repair tools'),
            'switch': StockCategory.objects.create(name='Switch', slug='switch', description='Network switches'),
        }
        stock_data = [
            ('TP-Link Archer C80', cats['router'], 'RTR-ARC80', 'piece', 35, 5, 3200, 4000),
            ('Huawei EG8141A5 ONU', cats['router'], 'ONU-HW14', 'piece', 50, 8, 1400, 2000),
            ('Tenda AC10', cats['router'], 'RTR-TND10', 'piece', 20, 3, 1800, 2500),
            ('Nokia G-010G-A ONU', cats['router'], 'ONU-NK01', 'piece', 30, 5, 1600, 2200),
            ('1 Core Drop Cable', cats['cable'], 'CBL-1CD', 'meter', 12000, 1000, 6, 12),
            ('2 Core Drop Cable', cats['cable'], 'CBL-2CD', 'meter', 6000, 500, 9, 16),
            ('8 Core Outdoor Cable', cats['cable'], 'CBL-8CO', 'meter', 2000, 300, 18, 30),
            ('SC/UPC Fast Connector', cats['connector'], 'CON-SCUP', 'piece', 300, 40, 20, 40),
            ('SC/APC Fast Connector', cats['connector'], 'CON-SCAP', 'piece', 250, 30, 28, 55),
            ('PLC Splitter 1x4', cats['connector'], 'SPL-1X4', 'piece', 40, 8, 350, 600),
            ('PLC Splitter 1x8', cats['connector'], 'SPL-1X8', 'piece', 25, 5, 650, 1100),
            ('RJ45 Cat6 (box of 100)', cats['connector'], 'CON-RJ6B', 'box', 30, 5, 400, 650),
            ('Fiber Cleaver', cats['tools'], 'TL-CLVR', 'piece', 5, 1, 3500, 0),
            ('Crimping Tool Set', cats['tools'], 'TL-CRMS', 'set', 6, 2, 1200, 0),
            ('Power Meter + VFL', cats['tools'], 'TL-PMVF', 'piece', 3, 1, 5500, 0),
            ('D-Link DGS-1016D 16-Port', cats['switch'], 'SW-DL16', 'piece', 10, 2, 4200, 5500),
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
                performed_by=manager, notes='Initial stock purchase', unit_price=pp,
            )

        # ── 8. Tickets ──
        self.stdout.write('Creating Tickets...')
        ticket_templates = [
            ('new_connection', 'New fiber connection request for residential flat'),
            ('new_connection', 'New office connection setup required'),
            ('line_cut', 'Internet down since last night, no signal on ONU'),
            ('line_cut', 'Cable damaged by construction work near road'),
            ('line_cut', 'Connection lost after heavy rainstorm'),
            ('speed_slow', 'Speed dropping to 1 Mbps during peak hours'),
            ('speed_slow', 'YouTube buffering on 20 Mbps plan'),
            ('speed_slow', 'Download speed much lower than subscribed bandwidth'),
            ('adapter_issue', 'ONU showing red PON light'),
            ('adapter_issue', 'Router WiFi range very poor, only works in one room'),
            ('adapter_issue', 'Router keeps disconnecting every 30 minutes'),
            ('password_change', 'Forgot PPPoE password, need reset'),
            ('tv_connect', 'Want IPTV service along with internet'),
            ('line_shift', 'Moving to new flat in same building, need line shift'),
            ('line_shift', 'Relocating to different area, need connection transfer'),
            ('area_coverage', 'Checking if fiber available in Lane 15, Mugda'),
            ('support_other', 'Billing dispute — double charged this month'),
            ('support_other', 'Want to upgrade from 10 Mbps to 30 Mbps plan'),
            ('support_other', 'Request temporary suspension for 2 months'),
        ]
        priorities = ['low', 'medium', 'medium', 'high', 'urgent']
        sources = ['phone', 'phone', 'phone', 'whatsapp', 'walk_in', 'marketing']

        comments_pool = [
            'Called customer, phone was busy. Will retry.',
            'Technician dispatched, ETA 45 minutes.',
            'Customer confirmed they will be available after 3 PM.',
            'Checked signal at ONU — red light confirmed. Need replacement unit.',
            'Splice work completed at junction box. Running line test now.',
            'Customer confirmed internet is restored and speed is fine.',
            'Issue escalated to senior tech — requires OTDR testing.',
            'Waiting for customer to share location on WhatsApp.',
            'Router replaced with new Huawei ONU. Working fine now.',
            'Payment confirmed by accounts. Ready to reconnect.',
            'Customer was not home. Rescheduled for tomorrow morning.',
            'Cable re-routed through alternate path to avoid construction zone.',
        ]

        for i in range(1, 31):
            ttype, desc = random.choice(ticket_templates)
            created_dt = now - timedelta(days=random.randint(0, 10), hours=random.randint(1, 18))
            cust = random.choice(customers)
            creator = random.choice(support_agents)

            line_cut_reason = ''
            if ttype == 'line_cut':
                line_cut_reason = random.choice(['technical', 'cable_damage', 'pay_off', 'other'])

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
                line_cut_reason=line_cut_reason,
            )
            Ticket.objects.filter(id=t.id).update(created_at=created_dt)

            action_dt = created_dt + timedelta(minutes=random.randint(5, 120))

            # ~75% get assigned
            if random.random() > 0.25:
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

                # Add 1-2 comments
                for _ in range(random.randint(1, 2)):
                    TicketComment.objects.create(
                        ticket=t, author=random.choice(support_agents + [assignee]),
                        comment=random.choice(comments_pool),
                    )
                TicketComment.objects.filter(ticket=t, created_at__gte=now - timedelta(seconds=10)).update(
                    created_at=action_dt + timedelta(minutes=random.randint(5, 60))
                )

                action_dt += timedelta(minutes=random.randint(30, 240))

                # ~65% go in_progress
                if random.random() > 0.35:
                    t.status = 'in_progress'
                    t.save()
                    log = TicketStatusLog.objects.create(
                        ticket=t, old_status='assigned', new_status='in_progress',
                        changed_by=assignee,
                    )
                    TicketStatusLog.objects.filter(id=log.id).update(created_at=action_dt)

                    # Stock usage for physical work tickets
                    if ttype in ['line_cut', 'new_connection', 'adapter_issue', 'line_shift']:
                        item = random.choice(stock_items[:8])  # routers, cables, connectors
                        qty = random.randint(1, 3) if item.unit == 'piece' else random.randint(10, 100)
                        uso = TicketStockUsage.objects.create(
                            ticket=t, stock_item=item, quantity_used=qty,
                            added_by=assignee, notes='Material used for repair/installation',
                        )
                        TicketStockUsage.objects.filter(id=uso.id).update(created_at=action_dt)

                    action_dt += timedelta(minutes=random.randint(20, 180))

                    # ~40% go to waiting_customer
                    if random.random() > 0.6:
                        t.status = 'waiting_customer'
                        t.save()
                        log = TicketStatusLog.objects.create(
                            ticket=t, old_status='in_progress', new_status='waiting_customer',
                            changed_by=assignee, notes='Customer not available at location',
                        )
                        TicketStatusLog.objects.filter(id=log.id).update(created_at=action_dt)
                        action_dt += timedelta(hours=random.randint(2, 24))

                    # ~55% get resolved
                    if random.random() > 0.45:
                        t.status = 'resolved'
                        t.resolution_notes = random.choice([
                            'Fiber spliced and signal restored. Customer verified.',
                            'Router replaced with new Huawei ONU. All OK.',
                            'Cable re-routed. Speed test shows full bandwidth.',
                            'PPPoE credentials reset. Customer can connect now.',
                            'New connection installed. ONU configured and tested.',
                            'Connector replaced at ODB. Signal level normal.',
                            'Upgraded package in system. Speed verified at customer end.',
                        ])
                        t.resolved_at = action_dt
                        t.resolved_by = assignee
                        t.save()
                        log = TicketStatusLog.objects.create(
                            ticket=t, old_status=t.status if t.status != 'resolved' else 'in_progress',
                            new_status='resolved',
                            changed_by=assignee, notes=t.resolution_notes,
                        )
                        TicketStatusLog.objects.filter(id=log.id).update(created_at=action_dt)

                        # ~50% of resolved get closed
                        if random.random() > 0.5:
                            close_dt = action_dt + timedelta(hours=random.randint(1, 48))
                            t.status = 'closed'
                            t.closed_at = close_dt
                            t.save()
                            log = TicketStatusLog.objects.create(
                                ticket=t, old_status='resolved', new_status='closed',
                                changed_by=creator, notes='Confirmed resolved. Closing ticket.',
                            )
                            TicketStatusLog.objects.filter(id=log.id).update(created_at=close_dt)

        # ── 9. Schedule & Attendance (last 10 days) ──
        self.stdout.write('Creating Schedules & Attendance...')
        shifts = ['morning', 'morning', 'morning', 'evening', 'full_day']
        for day_offset in range(10):
            d = now.date() - timedelta(days=day_offset)
            for tech in techs:
                shift = random.choice(shifts)
                Schedule.objects.create(
                    employee=tech, date=d, shift=shift,
                    assigned_area=random.choice(active_areas),
                    created_by=manager,
                )
                if day_offset > 0:  # attendance for past days only
                    att_status = random.choices(
                        ['present', 'late', 'absent', 'half_day'],
                        weights=[6, 2, 1, 1], k=1
                    )[0]
                    check_in = None
                    check_out = None
                    if att_status == 'present':
                        check_in = '08:00'
                        check_out = '16:00'
                    elif att_status == 'late':
                        check_in = f'0{random.randint(8,9)}:{random.choice(["15","30","45"])}'
                        check_out = '16:30'
                    elif att_status == 'half_day':
                        check_in = '08:00'
                        check_out = '12:00'

                    Attendance.objects.create(
                        employee=tech, date=d, status=att_status,
                        check_in=check_in, check_out=check_out,
                        marked_by=manager,
                    )

        # ── 10. Leave Requests ──
        self.stdout.write('Creating Leave Requests...')
        leave_data = [
            (support_agents[0], 'casual', 3, 5, 'Family event — need 3 days off', 'pending'),
            (support_agents[1], 'sick', 1, 3, 'Fever and cold, doctor advised rest', 'approved'),
            (techs[0], 'emergency', 0, 1, 'Family emergency at hometown', 'approved'),
            (techs[2], 'annual', 7, 14, 'Annual family vacation', 'pending'),
            (support_agents[2], 'casual', 5, 6, 'Personal work', 'rejected'),
            (techs[3], 'sick', 2, 4, 'Back pain, cannot do field work', 'pending'),
        ]
        for emp, ltype, start_offset, end_offset, reason, status in leave_data:
            lr = LeaveRequest.objects.create(
                employee=emp,
                leave_type=ltype,
                start_date=now.date() + timedelta(days=start_offset),
                end_date=now.date() + timedelta(days=end_offset),
                reason=reason,
                status=status,
            )
            if status == 'approved':
                lr.approved_by = manager
                lr.approval_notes = 'Approved. Please coordinate with team.'
                lr.save()
            elif status == 'rejected':
                lr.approved_by = manager
                lr.approval_notes = 'Cannot approve — short staffed this week.'
                lr.save()

        # ── Summary ──
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write(self.style.SUCCESS('  Test data populated successfully!'))
        self.stdout.write(self.style.SUCCESS('=' * 50))
        self.stdout.write('')
        self.stdout.write(f'  Employees:  {Employee.objects.count()}')
        self.stdout.write(f'  Teams:      {Team.objects.count()}')
        self.stdout.write(f'  Customers:  {Customer.objects.count()}')
        self.stdout.write(f'  Zones:      {Area.objects.count()}')
        self.stdout.write(f'  Packages:   {Package.objects.count()}')
        self.stdout.write(f'  Stock:      {StockItem.objects.count()} items')
        self.stdout.write(f'  Tickets:    {Ticket.objects.count()}')
        self.stdout.write(f'  Schedules:  {Schedule.objects.count()}')
        self.stdout.write(f'  Attendance: {Attendance.objects.count()}')
        self.stdout.write(f'  Leaves:     {LeaveRequest.objects.count()}')
        self.stdout.write('')
        self.stdout.write(self.style.WARNING('  Login Credentials (phone -> password):'))
        self.stdout.write(f'  Owner:       01911001001 -> {DEFAULT_PASSWORD}')
        self.stdout.write(f'  Manager:     01811002002 -> {DEFAULT_PASSWORD}')
        self.stdout.write(f'  Support:     01711003003 -> {DEFAULT_PASSWORD}')
        self.stdout.write(f'  Cable Tech:  01911006006 -> {DEFAULT_PASSWORD}')
        self.stdout.write(f'  Field Tech:  01711008008 -> {DEFAULT_PASSWORD}')
        self.stdout.write(f'  Marketing:   01611011011 -> {DEFAULT_PASSWORD}')
        self.stdout.write(f'  Accountant:  01911012012 -> {DEFAULT_PASSWORD}')
        self.stdout.write('')
