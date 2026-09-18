import { getAuthHeaders } from './auth.js';

export async function sendTextTransaction(text) {
    const headers = await getAuthHeaders();
    headers['Content-Type'] = 'application/json';

    const res = await fetch('/api/v1/web/extract/text', {
        method: 'POST',
        headers,
        body: JSON.stringify({ text }),
    });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    return res.json();
}

export async function sendImageTransaction(file) {
    const headers = await getAuthHeaders();
    const fd = new FormData();
    fd.append('file', file);

    const res = await fetch('/api/v1/web/extract/image', {
        method: 'POST',
        headers,
        body: fd,
    });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    return res.json();
}

export async function sendAudioTransaction(blob) {
    const headers = await getAuthHeaders();
    const fd = new FormData();
    fd.append('file', blob, 'voice_note.webm');

    const res = await fetch('/api/v1/web/extract/audio', {
        method: 'POST',
        headers,
        body: fd,
    });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    return res.json();
}


export async function fetchTransactions(limit = 50, offset = 0) {
    const headers = await getAuthHeaders();
    const res = await fetch(`/api/v1/web/transactions?limit=${limit}&offset=${offset}`, {
        headers,
    });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    return res.json();
}

export async function fetchDashboard(period = 'monthly') {
    const headers = await getAuthHeaders();
    const res = await fetch(`/api/v1/web/dashboard?period=${period}`, {
        headers,
    });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    return res.json();
}

export async function fetchAccounts() {
    const headers = await getAuthHeaders();
    const res = await fetch('/api/v1/web/accounts', { headers });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    return res.json();
}

export async function createAccount(data) {
    const headers = await getAuthHeaders();
    headers['Content-Type'] = 'application/json';

    const res = await fetch('/api/v1/web/accounts', {
        method: 'POST',
        headers,
        body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    return res.json();
}