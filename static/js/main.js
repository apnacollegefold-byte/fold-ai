function bootstrap() {
    const appDiv = document.getElementById('app');
    showShell(appDiv);
}

function showShell(appDiv) {
    appDiv.innerHTML = '';
    const tpl = document.getElementById('tpl-shell');
    appDiv.appendChild(tpl.content.cloneNode(true));

    window.addEventListener('hashchange', navigate);
    navigate(); // handle initial hash
}

function navigate() {
    const hash = (location.hash || '#landing').replace('#', ''); //chat
    const container = document.getElementById('page-container');
    if (!container) return;

    // Clone the correct template
    const tpl = document.getElementById(`tpl-${hash}`);
    if (!tpl) {
        // Unknown hash → go to landing
        location.hash = '#landing';
        return;
    }

    container.innerHTML = '';
    container.appendChild(tpl.content.cloneNode(true));

    // Update active nav link
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.toggle('active', link.dataset.page === hash);
    });

    // Initialize page-specific logic — filled in module by module.
    switch (hash) {
        // case 'chat':         initChatPage();         break;  // Module 20
        // case 'transactions': initTransactionsPage(); break;  // Module 21
        // case 'reports':      initReportsPage();      break;  // Module 22
        // 'landing' and 'accounts' need no JS logic yet
    }
}

bootstrap()
