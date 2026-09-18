import { fetchDashboard } from '../api.js';

export async function initReportsPage() {
    const loading      = document.getElementById('report-loading');
    const content      = document.getElementById('report-content');
    const periodSelect = document.getElementById('report-period');
    const refreshBtn   = document.getElementById('report-refresh');

    if (!loading || !content) return;

    // Store chart instances to destroy them before re-rendering
    let charts = {
        category: null,
        payment: null,
        incomeExpense: null,
        accounts: null
    };

    async function load() {
        loading.style.display = 'block';
        content.style.display = 'none';

        try {
            const period = periodSelect ? periodSelect.value : 'monthly';
            const data = await fetchDashboard(period);

            loading.style.display = 'none';
            content.style.display = 'block';

            // Render all components
            renderSummary(data.summary, data.period_label);
            renderCategoryChart(data.by_category || []);
            renderPaymentChart(data.by_payment_method || []);
            renderIncomeExpenseChart(data.summary);
            renderAccountsChart(data.accounts || []);
            renderRecentTx(data.recent_transactions || []);

        } catch (err) {
            loading.textContent = 'Failed to load report.';
            console.error(err);
        }
    }

    function fmt(minor) {
        return '₹' + (Math.abs(minor) / 100).toLocaleString('en-IN', {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        });
    }

    function renderSummary(s, label) {
        const el = document.getElementById('summary-cards');
        if (!el || !s) return;
        
        el.innerHTML = `
            <div class="summary-card">
                <div class="label">Income</div>
                <div class="value income">${fmt(s.income_minor)}</div>
            </div>
            <div class="summary-card">
                <div class="label">Expenses</div>
                <div class="value expense">${fmt(s.expense_minor)}</div>
            </div>
            <div class="summary-card">
                <div class="label">Net Cash Flow</div>
                <div class="value net">${fmt(s.net_cashflow_minor)}</div>
            </div>
        `;
    }

    function renderCategoryChart(rows) {
        const canvas = document.getElementById('chart-category');
        if (!canvas) return;

        // Destroy previous chart instance if exists
        if (charts.category) {
            charts.category.destroy();
        }

        if (rows.length === 0) {
            canvas.parentElement.innerHTML = '<p class="empty-msg">No category data for this period.</p>';
            return;
        }

        // Prepare data: extract labels and values
        const labels = rows.map(r => r.key || r.category || 'Unknown');
        const values = rows.map(r => Math.abs(r.amount_minor || 0) / 100);

        // Color palette for categories
        const colors = [
            '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF',
            '#FF9F40', '#FF6384', '#C9CBCF', '#4BC0C0', '#FF6384'
        ];

        // Create doughnut chart
        charts.category = new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: colors,
                    borderWidth: 2,
                    borderColor: '#1a1a1a'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: {
                        position: 'right',
                        labels: {
                            color: '#e0e0e0',
                            padding: 15,
                            font: { size: 12 }
                        }
                    },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                const label = context.label || '';
                                const value = context.parsed || 0;
                                return `${label}: ₹${value.toLocaleString('en-IN')}`;
                            }
                        }
                    }
                }
            }
        });
    }


    function renderPaymentChart(rows) {
        const canvas = document.getElementById('chart-payment');
        if (!canvas) return;

        if (charts.payment) {
            charts.payment.destroy();
        }

        if (rows.length === 0) {
            canvas.parentElement.innerHTML = '<p class="empty-msg">No payment method data.</p>';
            return;
        }

        const labels = rows.map(r => r.key || r.payment_method || 'Direct');
        const values = rows.map(r => Math.abs(r.amount_minor || 0) / 100);

        charts.payment = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Amount Spent',
                    data: values,
                    backgroundColor: '#2d7a6e',
                    borderRadius: 6
                }]
            },
            options: {
                indexAxis: 'y', // Horizontal bars
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `₹${context.parsed.x.toLocaleString('en-IN')}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color: '#888',
                            callback: function(value) {
                                return '₹' + value.toLocaleString('en-IN');
                            }
                        },
                        grid: { color: '#333' }
                    },
                    y: {
                        ticks: { color: '#e0e0e0' },
                        grid: { display: false }
                    }
                }
            }
        });
    }

    function renderIncomeExpenseChart(summary) {
        const canvas = document.getElementById('chart-income-expense');
        if (!canvas || !summary) return;

        if (charts.incomeExpense) {
            charts.incomeExpense.destroy();
        }

        const income = Math.abs(summary.income_minor || 0) / 100;
        const expense = Math.abs(summary.expense_minor || 0) / 100;

        charts.incomeExpense = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: ['Income', 'Expense'],
                datasets: [{
                    label: 'Amount',
                    data: [income, expense],
                    backgroundColor: ['#4BC0C0', '#FF6384'],
                    borderRadius: 8,
                    barThickness: 80
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `₹${context.parsed.y.toLocaleString('en-IN')}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        ticks: {
                            color: '#888',
                            callback: function(value) {
                                return '₹' + value.toLocaleString('en-IN');
                            }
                        },
                        grid: { color: '#333' }
                    },
                    x: {
                        ticks: { color: '#e0e0e0', font: { size: 14, weight: 'bold' } },
                        grid: { display: false }
                    }
                }
            }
        });
    }


    function renderAccountsChart(accounts) {
        const canvas = document.getElementById('chart-accounts');
        if (!canvas) return;

        if (charts.accounts) {
            charts.accounts.destroy();
        }

        if (accounts.length === 0) {
            canvas.parentElement.innerHTML = '<p class="empty-msg">No accounts found.</p>';
            return;
        }

        const labels = accounts.map(a => a.name || 'Unknown');
        const values = accounts.map(a => (a.balance || 0) / 100);
        
        // Color code by account type
        const colors = accounts.map(a => {
            if (a.account_type === 'cash') return '#4BC0C0';
            if (a.account_type === 'credit') return '#FF6384';
            return '#36A2EB'; // bank
        });

        charts.accounts = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Balance',
                    data: values,
                    backgroundColor: colors,
                    borderRadius: 6
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: function(context) {
                                return `₹${context.parsed.x.toLocaleString('en-IN')}`;
                            }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            color: '#888',
                            callback: function(value) {
                                return '₹' + value.toLocaleString('en-IN');
                            }
                        },
                        grid: { color: '#333' }
                    },
                    y: {
                        ticks: { color: '#e0e0e0' },
                        grid: { display: false }
                    }
                }
            }
        });
    }

    function renderRecentTx(txs) {
        const el = document.getElementById('report-recent-tx');
        if (!el) return;

        if (txs.length === 0) {
            el.innerHTML = '<p class="empty-msg">No recent transactions.</p>';
            return;
        }

        let html = '<table class="data-table"><thead><tr><th>Date</th><th>Description</th><th>Category</th><th>Amount</th></tr></thead><tbody>';
        for (const tx of txs.slice(0, 10)) {
            const date = tx.occurred_at ? new Date(tx.occurred_at).toLocaleDateString() : '—';
            const desc = tx.description || '—';
            const cat  = tx.category || '—';
            // Use 'amount' field (not amount_minor)
            const amt  = tx.amount != null ? '₹' + (tx.amount / 100).toFixed(2) : '—';
            html += `<tr><td>${date}</td><td>${desc}</td><td>${cat}</td><td>${amt}</td></tr>`;
        }
        html += '</tbody></table>';
        el.innerHTML = html;
    }

    
    
    if (refreshBtn) {
        refreshBtn.addEventListener('click', load);
    }

    // Period selector (weekly/monthly)
    if (periodSelect) {
        periodSelect.addEventListener('change', load);
    }

    // PDF Download (uses browser print)
    const downloadPdfBtn = document.getElementById('report-download-pdf');
    if (downloadPdfBtn) {
        downloadPdfBtn.addEventListener('click', () => {
            window.print();
        });
    }

    // Initial load
    await load();
}
