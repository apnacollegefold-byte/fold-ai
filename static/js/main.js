import { initAuth } from './auth.js';
import { initChatPage } from './pages/chat.js';
import { initTransactionsPage } from './pages/transactions.js';
import { initAccountsPage } from './pages/accounts.js';
import { initReportsPage } from './pages/report.js';

let clerk = null;

async function bootstrap() {
    try {
        clerk = await initAuth();
        const appDiv = document.getElementById('app');

        if (clerk.isSignedIn) {
            showShell(appDiv);
        } else {
            showAuth(appDiv);
        }
    } catch (err) {
        console.error('Bootstrap failed:', err);
        document.getElementById('app').innerHTML =
            '<p class="loading-text">Error loading app. Check console.</p>';
    }
}

function showAuth(appDiv) {
    appDiv.innerHTML = '';
    const tpl = document.getElementById('tpl-auth');
    appDiv.appendChild(tpl.content.cloneNode(true));

    const signInDiv = document.getElementById('clerk-sign-in');
    clerk.mountSignIn(signInDiv);
}

function showShell(appDiv) {
    appDiv.innerHTML = '';
    const tpl = document.getElementById('tpl-shell');
    appDiv.appendChild(tpl.content.cloneNode(true));

    // Mount Clerk's user menu (avatar, sign out)
    const userBtnDiv = document.getElementById('user-button');
    clerk.mountUserButton(userBtnDiv);

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
        case 'chat':         initChatPage();         break;  
        case 'transactions': initTransactionsPage(); break;  
        case 'accounts':     initAccountsPage();     break;
        case 'reports':      initReportsPage();      break;  
        // 'landing' and 'accounts' need no JS logic yet
    }
}

bootstrap()
