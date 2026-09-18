import { fetchAccounts, createAccount } from '../api.js';

export async function initAccountsPage() {
   const loading   = document.getElementById('acc-loading');
    const listDiv   = document.getElementById('acc-list');
    const addBtn    = document.getElementById('acc-add-btn');
    const statusDiv = document.getElementById('acc-status');

    if (!addBtn || !listDiv) return;

    async function loadAccounts() {
        try {
            const data = await fetchAccounts();
            const accounts = data.accounts || [];
            loading.style.display = 'none';

            if (accounts.length === 0) {
                listDiv.innerHTML = '<p class="empty-msg">No accounts yet. Add one above.</p>';
                return;
            }

            listDiv.innerHTML = accounts.map(a => {
                // Database stores balance in minor units (paisa)
                const bal = a.balance != null ? '₹' + (a.balance / 100).toFixed(2) : '₹0.00';
                const last4 = a.account_number_last4 ? ` •••• ${a.account_number_last4}` : '';
                const typeLabel = (a.account_type || '').toUpperCase();
                const institution = a.institution_name || '';

                return `<div class="account-card">
                    <div class="acc-name">${a.name || '—'}</div>
                    <div class="acc-meta">${typeLabel}${institution ? ' · ' + institution : ''}${last4}</div>
                    <div class="acc-balance">${bal}</div>
                </div>`;
            }).join('');
        } catch (err) {
            loading.textContent = 'Failed to load accounts.';
            console.error(err);
        }
    }

    await loadAccounts();

    addBtn.addEventListener('click', async () => {
        const name        = document.getElementById('acc-name').value.trim();
        const type        = document.getElementById('acc-type').value;
        const institution = document.getElementById('acc-institution').value.trim();
        const last4        = document.getElementById('acc-last4').value.trim();
        const balance      = parseFloat(document.getElementById('acc-balance').value) || 0;

        if (!name) { alert('Account name is required.'); return; }

        addBtn.disabled = true;
        statusDiv.textContent = 'Creating account…';

        try {
            await createAccount({
                name,
                account_type: type,
                institution_name: institution || null,
                account_number_last4: last4 || null,
                opening_balance: balance || null,
            });
            statusDiv.innerHTML = '<span style="color:var(--success)">✅ Account created!</span>';

            // Reset form
            document.getElementById('acc-name').value = '';
            document.getElementById('acc-institution').value = '';
            document.getElementById('acc-last4').value = '';
            document.getElementById('acc-balance').value = '';

            // Reload list
            await loadAccounts();
        } catch (err) {
            statusDiv.innerHTML = `<span style="color:var(--danger)">❌ ${err.message}</span>`;
        } finally {
            addBtn.disabled = false;
        }
    });

}