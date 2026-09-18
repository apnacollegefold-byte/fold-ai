export async function initAuth() {
    // Wait for the Clerk script tag to attach window.Clerk
    while (!window.Clerk) {
        await new Promise(r => setTimeout(r, 50));
    }
    await window.Clerk.load();
    return window.Clerk;
}

export async function getAuthHeaders() {
    if (!window.Clerk || !window.Clerk.session) {
        throw new Error('User is not authenticated');
    }
    const token = await window.Clerk.session.getToken();
    return { 'Authorization': `Bearer ${token}` };
}
