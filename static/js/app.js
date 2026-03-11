/**
 * TaskFiber ISP Manager — Modern App Controller
 */
(function () {
    'use strict';

    /* ── Sidebar ── */
    const Sidebar = {
        sidebar: null, overlay: null,

        init() {
            this.sidebar = document.getElementById('sidebar');
            this.overlay = document.getElementById('sidebarOverlay');
            if (!this.sidebar) return;

            document.getElementById('sidebarToggle')?.addEventListener('click', () => this.toggleMobile());
            document.getElementById('sidebarClose')?.addEventListener('click', () => this.closeMobile());
            this.overlay?.addEventListener('click', () => this.closeMobile());
            document.getElementById('sidebarCollapse')?.addEventListener('click', () => this.toggleCollapse());

            this.loadState();
            window.addEventListener('resize', () => { if (window.innerWidth >= 992) this.closeMobile(); });

            this.sidebar.querySelectorAll('.nav-link').forEach(link => {
                link.addEventListener('click', () => { if (window.innerWidth < 992) this.closeMobile(); });
            });

            document.addEventListener('keydown', e => {
                if ((e.ctrlKey || e.metaKey) && e.key === 'b') {
                    e.preventDefault();
                    window.innerWidth >= 992 ? this.toggleCollapse() : this.toggleMobile();
                }
            });
        },

        toggleMobile() {
            this.sidebar.classList.toggle('mobile-open');
            this.overlay?.classList.toggle('active');
            document.body.style.overflow = this.sidebar.classList.contains('mobile-open') ? 'hidden' : '';
        },
        closeMobile() {
            this.sidebar.classList.remove('mobile-open');
            this.overlay?.classList.remove('active');
            document.body.style.overflow = '';
        },
        toggleCollapse() {
            this.sidebar.classList.toggle('collapsed');
            localStorage.setItem('sidebar_collapsed', this.sidebar.classList.contains('collapsed'));
        },
        loadState() {
            if (window.innerWidth >= 992 && localStorage.getItem('sidebar_collapsed') === 'true') {
                this.sidebar.classList.add('collapsed');
            }
        }
    };

    /* ── Search ── */
    const Search = {
        init() {
            const input = document.getElementById('globalSearch');
            if (!input) return;
            document.addEventListener('keydown', e => {
                if ((e.ctrlKey || e.metaKey) && e.key === 'k') { e.preventDefault(); input.focus(); }
            });
            input.addEventListener('keydown', e => {
                if (e.key === 'Enter' && input.value.trim()) {
                    window.location.href = '/tickets/?search=' + encodeURIComponent(input.value.trim());
                }
                if (e.key === 'Escape') input.blur();
            });
        }
    };

    /* ── Alerts ── */
    const Alerts = {
        init() {
            setTimeout(() => {
                document.querySelectorAll('.alert-dismissible').forEach(alert => {
                    alert.style.transition = 'opacity .3s ease, transform .3s ease';
                    alert.style.opacity = '0';
                    alert.style.transform = 'translateY(-8px)';
                    setTimeout(() => {
                        if (typeof bootstrap !== 'undefined') {
                            bootstrap.Alert.getOrCreateInstance(alert)?.close();
                        }
                    }, 300);
                });
            }, 5000);
        }
    };

    /* ── Forms ── */
    const Forms = {
        init() {
            this.initTicketTypeToggle();
            this.initQuickTypeButtons();
            this.initPasswordToggle();
            this.initDateDefaults();
        },
        initTicketTypeToggle() {
            const typeField = document.getElementById('id_ticket_type');
            const lineCutFields = document.getElementById('line-cut-fields');
            const customerField = document.getElementById('id_customer');
            const newContactFields = document.getElementById('new-contact-fields');
            if (!typeField) return;
            const toggle = () => { if (lineCutFields) lineCutFields.style.display = typeField.value === 'line_cut' ? 'block' : 'none'; };
            typeField.addEventListener('change', toggle);
            toggle();
            if (customerField && newContactFields) {
                const tc = () => { newContactFields.style.display = customerField.value ? 'none' : 'block'; };
                customerField.addEventListener('change', tc);
                tc();
            }
        },
        initQuickTypeButtons() {
            document.querySelectorAll('.quick-type-btn').forEach(btn => {
                btn.addEventListener('click', function () {
                    const tF = document.getElementById('id_ticket_type');
                    const aF = document.getElementById('id_assigned_team');
                    const pF = document.getElementById('id_priority');
                    if (tF) tF.value = this.dataset.type;
                    if (aF) aF.value = this.dataset.team;
                    if (pF) pF.value = this.dataset.priority;
                    tF?.dispatchEvent(new Event('change'));
                    document.querySelectorAll('.quick-type-btn').forEach(b => b.classList.remove('active'));
                    this.classList.add('active');
                });
            });
        },
        initPasswordToggle() {
            document.querySelectorAll('.toggle-password').forEach(btn => {
                btn.addEventListener('click', function () {
                    const input = document.getElementById(this.dataset.target);
                    const icon = this.querySelector('i');
                    if (input.type === 'password') { input.type = 'text'; icon.className = 'bi bi-eye-slash'; }
                    else { input.type = 'password'; icon.className = 'bi bi-eye'; }
                });
            });
        },
        initDateDefaults() {
            document.querySelectorAll('input[type="date"][data-default-today]').forEach(input => {
                if (!input.value) input.value = new Date().toISOString().split('T')[0];
            });
        }
    };

    /* ── Clipboard ── */
    const Clipboard = {
        init() {
            document.querySelectorAll('[data-clipboard]').forEach(btn => {
                btn.addEventListener('click', function () {
                    const target = document.getElementById(this.dataset.clipboard);
                    if (!target) return;
                    navigator.clipboard.writeText(target.textContent || target.value).then(() => {
                        const orig = btn.innerHTML;
                        btn.innerHTML = '<i class="bi bi-check-lg me-1"></i>Copied!';
                        btn.classList.add('btn-success');
                        btn.classList.remove('btn-outline-success', 'btn-outline-primary');
                        setTimeout(() => {
                            btn.innerHTML = orig;
                            btn.classList.remove('btn-success');
                            btn.classList.add('btn-outline-success');
                        }, 2000);
                    });
                });
            });
        }
    };

    /* ── Tables ── */
    const Tables = {
        init() {
            document.querySelectorAll('tr[data-href]').forEach(row => {
                row.style.cursor = 'pointer';
                row.addEventListener('click', e => {
                    if (e.target.tagName === 'A' || e.target.tagName === 'BUTTON' || e.target.closest('a, button')) return;
                    window.location.href = row.dataset.href;
                });
            });
        }
    };

    /* ── Status Change ── */
    const StatusChange = {
        init() {
            const s = document.querySelector('select[name="status"]');
            const r = document.getElementById('resolution-group');
            if (!s || !r) return;
            const t = () => { r.style.display = s.value === 'resolved' ? 'block' : 'none'; };
            s.addEventListener('change', t);
            t();
        }
    };

    /* ── Confirm Actions ── */
    const ConfirmActions = {
        init() {
            document.querySelectorAll('[data-confirm]').forEach(el => {
                el.addEventListener('click', e => {
                    if (!confirm(el.dataset.confirm || 'Are you sure?')) e.preventDefault();
                });
            });
        }
    };

    /* ── Tooltips ── */
    const Tooltips = {
        init() {
            if (typeof bootstrap !== 'undefined') {
                document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(el => new bootstrap.Tooltip(el));
            }
        }
    };

    /* ── Counter Animation ── */
    const CountUp = {
        init() {
            document.querySelectorAll('.stat-value').forEach(el => {
                const target = parseInt(el.textContent, 10);
                if (isNaN(target) || target === 0) return;
                const duration = 600;
                const start = performance.now();
                el.textContent = '0';
                const step = now => {
                    const progress = Math.min((now - start) / duration, 1);
                    const eased = 1 - Math.pow(1 - progress, 3);
                    el.textContent = Math.round(target * eased);
                    if (progress < 1) requestAnimationFrame(step);
                };
                requestAnimationFrame(step);
            });
        }
    };

    /* ── Init ── */
    document.addEventListener('DOMContentLoaded', () => {
        Sidebar.init();
        Search.init();
        Alerts.init();
        Forms.init();
        Clipboard.init();
        Tables.init();
        StatusChange.init();
        ConfirmActions.init();
        Tooltips.init();
        CountUp.init();
    });
})();

