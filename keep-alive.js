// Keep-Alive Script for Render Free Tier
// This prevents your backend from sleeping by pinging it every 14 minutes

const BACKEND_URL = 'https://your-backend-name.onrender.com';
const PING_INTERVAL = 14 * 60 * 1000; // 14 minutes in milliseconds

async function pingBackend() {
    try {
        console.log(`Pinging backend at ${new Date().toISOString()}`);
        const response = await fetch(`${BACKEND_URL}/businesses`);
        
        if (response.ok) {
            console.log('✅ Backend is alive and responding');
        } else {
            console.log(`⚠️ Backend responded with status: ${response.status}`);
        }
    } catch (error) {
        console.log('❌ Failed to ping backend:', error.message);
    }
}

// Start pinging immediately and then every 14 minutes
pingBackend();
setInterval(pingBackend, PING_INTERVAL);

console.log('🚀 Keep-alive service started. Backend will be pinged every 14 minutes.');

// For Node.js environments
if (typeof module !== 'undefined' && module.exports) {
    module.exports = { pingBackend };
}