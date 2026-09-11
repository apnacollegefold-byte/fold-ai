export async function sendTextTransaction(text) {
    const res = await fetch('/api/v1/web/extract/text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
    });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    return res.json();
}

export async function sendImageTransaction(file) {
    const fd = new FormData();
    fd.append('file', file);

    const res = await fetch('/api/v1/web/extract/image', {
        method: 'POST',
        body: fd,
    });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    return res.json();
}

export async function sendAudioTransaction(blob) {
    const fd = new FormData();
    fd.append('file', blob, 'voice_note.webm');

    const res = await fetch('/api/v1/web/extract/audio', {
        method: 'POST',
        body: fd,
    });
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    return res.json();
}


export async function fetchTransactions(limit = 50, offset = 0) {
    const res = await fetch(`/api/v1/web/transactions?limit=${limit}&offset=${offset}`);
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    return res.json();
}

export async function fetchDashboard(period = 'monthly') {
    const res = await fetch(`/api/v1/web/dashboard?period=${period}`);
    if (!res.ok) throw new Error(`Server error ${res.status}`);
    return res.json();
}