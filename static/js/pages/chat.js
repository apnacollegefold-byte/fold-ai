import { sendTextTransaction, sendImageTransaction, sendAudioTransaction } from '../api.js';

export function initChatPage() {
    const textInput    = document.getElementById('text-input');
    const sendBtn      = document.getElementById('send-btn');
    const recordBtn    = document.getElementById('record-btn');
    const imageInput   = document.getElementById('image-input');
    const statusArea   = document.getElementById('status-area');
    const resultArea   = document.getElementById('result-area');

    if (!sendBtn || !textInput) return;

    function showStatus(msg) {
        statusArea.textContent = msg;
    }

    function showResult(result, isError) {
        const data    = result.extracted_data || {};
        const ledger  = result.ledger_result  || {};
        const message = result.message || (isError ? 'Something went wrong' : 'Done');

        if (isError) {
            const card = document.createElement('div');
            card.className = 'result-card error';
            card.innerHTML = `<div class="msg">❌ ${message}</div>`;
            resultArea.prepend(card);
            statusArea.textContent = '';
            return;
        }

        // Build payment method display
        let paymentDisplay = '';
        if (data.payment_method && data.payment_provider) {
            paymentDisplay = `${data.payment_method} • ${data.payment_provider}`;
        } else if (data.payment_method) {
            paymentDisplay = data.payment_method;
        } else if (data.payment_provider) {
            paymentDisplay = `upi • ${data.payment_provider}`;
        }

        // Format amount
        const amount = data.amount != null ? `₹${parseFloat(data.amount).toFixed(2)}` : 'N/A'; //13.50
        
        // Build debug details
        const debugDetails = `
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; margin-top: 0.75rem;">
                <div style="grid-column: 1 / -1; background: #2a2a2a; padding: 0.75rem; border-radius: 0.5rem; border-left: 3px solid var(--accent);">
                    <div style="color: #888; font-size: 0.75rem; margin-bottom: 0.25rem;">💳 CHARGED ACCOUNT</div>
                    <div style="font-weight: 600; font-size: 1rem; color: var(--accent);">${ledger._resolved_account_name || 'Unknown'}</div>
                    <div style="color: #888; font-size: 0.75rem; margin-top: 0.25rem;">Resolution: ${ledger._resolution_method || 'unknown'}</div>
                </div>
                <div>
                    <div style="color: #888; font-size: 0.75rem; margin-bottom: 0.25rem;">Amount Source</div>
                    <div style="font-weight: 500;">${data.amount_source || 'nlp'}</div>
                </div>
                <div>
                    <div style="color: #888; font-size: 0.75rem; margin-bottom: 0.25rem;">Provider</div>
                    <div style="font-weight: 500;">${data.payment_provider || '—'}</div>
                </div>
                <div>
                    <div style="color: #888; font-size: 0.75rem; margin-bottom: 0.25rem;">Bank Hint (NLP)</div>
                    <div style="font-weight: 500;">${data.bank_account || '—'}</div>
                </div>
                <div>
                    <div style="color: #888; font-size: 0.75rem; margin-bottom: 0.25rem;">Payment Method</div>
                    <div style="font-weight: 500;">${data.payment_method || '—'}</div>
                </div>
                ${result.source === 'image' && data.receipt_account_last4 ? `
                <div>
                    <div style="color: #888; font-size: 0.75rem; margin-bottom: 0.25rem;">Receipt Last 4</div>
                    <div style="font-weight: 500;">${data.receipt_account_last4}</div>
                </div>
                ` : ''}
                ${result.source === 'audio' && data.transcript ? `
                <div style="grid-column: 1 / -1;">
                    <div style="color: #888; font-size: 0.75rem; margin-bottom: 0.25rem;">Transcript</div>
                    <div style="font-weight: 500; font-size: 0.875rem; font-style: italic;">"${data.transcript}"</div>
                </div>
                ` : ''}
            </div>
        `;

        const card = document.createElement('div');
        card.className = 'result-card success';
        card.innerHTML = `
            <div style="background: linear-gradient(135deg, #2d7a6e 0%, #1e5a4f 100%); color: white; padding: 1.25rem; border-radius: 0.75rem 0.75rem 0 0; margin: -0.75rem -0.75rem 0.75rem -0.75rem;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
                    <div style="font-size: 0.875rem; opacity: 0.9;">Transaction Recorded</div>
                    <div style="font-size: 1.75rem; font-weight: 700;">${amount}</div>
                </div>
                <div style="font-size: 0.875rem; opacity: 0.9;">
                    ${paymentDisplay ? paymentDisplay + ' • ' : ''}${data.category || 'expense'}
                </div>
            </div>
            
            <div style="background: #1a1a1a; padding: 1rem; border-radius: 0.5rem; margin-bottom: 0.75rem;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <div>
                        <div style="color: #888; font-size: 0.75rem; margin-bottom: 0.25rem;">CATEGORY</div>
                        <div style="font-size: 1.25rem; font-weight: 600; text-transform: capitalize;">${data.category || 'expense'}</div>
                    </div>
                    <div style="text-align: right;">
                        <div style="color: #888; font-size: 0.75rem; margin-bottom: 0.25rem;">Journal ID</div>
                        <div style="font-size: 1.25rem; font-weight: 600;">#${ledger.journal_id || ledger.id || '—'}</div>
                    </div>
                </div>
                ${ledger.journal_id || ledger.id ? '<div style="margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid #333; color: #888; font-size: 0.875rem;">Wrong category? <span style="color: #2d7a6e; cursor: pointer;">Change it</span></div>' : ''}
            </div>
            
            <details style="background: #1a1a1a; padding: 1rem; border-radius: 0.5rem; cursor: pointer;">
                <summary style="color: #888; font-size: 0.875rem; font-weight: 500; list-style: none; display: flex; justify-content: space-between; align-items: center;">
                    <span>Technical Details</span>
                    <span style="font-size: 1.25rem;">▼</span>
                </summary>
                ${debugDetails}
            </details>
            
            <div style="margin-top: 0.75rem; padding-top: 0.75rem; border-top: 1px solid #333; color: #888; font-size: 0.875rem; display: flex; justify-content: space-between; align-items: center;">
                <span>Saved successfully</span>
                <span style="color: #2d7a6e; cursor: pointer;">View all transactions →</span>
            </div>
        `;
        resultArea.prepend(card);
        statusArea.textContent = '';
    }

    sendBtn.addEventListener('click', async () => {
        const text = textInput.value.trim();
        if (!text) { alert('Please enter a transaction.'); return; }

        showStatus('Processing text…');
        sendBtn.disabled = true;
        try {
            const result = await sendTextTransaction(text);
            showResult(result, false);
            textInput.value = '';
        } catch (err) {
            showResult({ message: err.message }, true);
        } finally {
            sendBtn.disabled = false;
        }
    });

    textInput.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
            sendBtn.click();
        }
    });

    imageInput.addEventListener('change', async (e) => {
        const file = e.target.files[0];
        if (!file) return;

        showStatus('Processing receipt image…');
        try {
            const result = await sendImageTransaction(file);
            showResult(result, false);
        } catch (err) {
            showResult({ message: err.message }, true);
        } finally {
            imageInput.value = '';
        }
    });
    
    let mediaRecorder = null;
    let audioChunks   = [];

    recordBtn.addEventListener('click', async () => {
        if (!mediaRecorder) {
            // Start recording
            try {
                const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
                mediaRecorder = new MediaRecorder(stream);

                mediaRecorder.ondataavailable = (e) => {
                    if (e.data.size > 0) audioChunks.push(e.data);
                };

                mediaRecorder.onstop = async () => {
                    const blob = new Blob(audioChunks, { type: 'audio/webm' });
                    audioChunks = [];

                    showStatus('Processing audio…');
                    try {
                        const result = await sendAudioTransaction(blob);
                        showResult(result, false);
                    } catch (err) {
                        showResult({ message: err.message }, true);
                    }
                };

                audioChunks = [];
                mediaRecorder.start();
                recordBtn.textContent = '🛑 Stop Recording';
                recordBtn.style.background = '#e17055';
                recordBtn.style.color = '#fff';
                showStatus('Recording audio…');
            } catch (err) {
                alert('Microphone access denied.');
                console.error(err);
            }
        } else {
            // Stop recording
            mediaRecorder.stop();
            mediaRecorder.stream.getTracks().forEach(t => t.stop());
            mediaRecorder = null;
            recordBtn.textContent = '🎤 Record Audio';
            recordBtn.style.background = '';
            recordBtn.style.color = '';
        }
    });
}
