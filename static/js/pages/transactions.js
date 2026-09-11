import { fetchTransactions } from '../api.js';

export async function initTransactionsPage() {
    const loading = document.getElementById('tx-loading');
    const table   = document.getElementById('tx-table');
    const body    = document.getElementById('tx-body');
    const empty   = document.getElementById('tx-empty');

    if (!loading || !table || !body) return;

    try {
        const data = await fetchTransactions(50, 0);
        const rows = data.transactions || [];

        loading.style.display = 'none';

        if (rows.length === 0) {
            empty.style.display = 'block';
            return;
        }

        table.style.display = 'table';
        body.innerHTML = rows.map(tx => {
            const date   = tx.occurred_at ? new Date(tx.occurred_at).toLocaleDateString() : '—';
            const desc   = tx.description || tx.text_transcript || '—';
            const cat    = tx.category || '—';
            // Database stores as 'amount' in minor units (paisa)
            const amt    = tx.amount != null ? '₹' + (tx.amount / 100).toFixed(2) : '—';
            
            // Derive payment method display
            let method = '—';
            if (tx.payment_provider) {
                method = `upi • ${tx.payment_provider}`;
            } else if (tx.account_type === 'credit') {
                method = 'card';
            } else if (tx.account_type === 'cash') {
                method = 'cash';
            } else if (tx.account_name) {
                method = tx.account_name;
            }
            
            return `<tr>
                <td>${date}</td>
                <td>${desc}</td>
                <td>${cat}</td>
                <td>${amt}</td>
                <td>${method}</td>
            </tr>`;
        }).join('');

    } catch (err) {
        loading.textContent = 'Failed to load transactions.';
        console.error(err);
    }
}
