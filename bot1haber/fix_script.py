
import os

path = 'd:/Projelerim/bot1haber yeni/bot1haber/src/static/script.js'
with open(path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Find the start of the bad section
marker = '/* Scanner Logic */'
idx = content.find(marker)

if idx != -1:
    # Keep everything before the marker
    good_content = content[:idx]
    
    # New correct code
    new_code = """/* Scanner Logic */
async function updateScanner() {
    const tableBody = document.getElementById('scanner-body');
    const statusLabel = document.getElementById('scan-status');
    
    if (statusLabel) statusLabel.innerText = 'Taranıyor...';
    if (tableBody) tableBody.innerHTML = '<tr><td colspan="7" style="text-align:center;"><div class="loading-spinner"></div></td></tr>';

    try {
        const res = await fetch(`${API_BASE}/scanner`);
        const data = await res.json();
        
        if (data.status === 'success') {
            if (statusLabel) statusLabel.innerText = `Son güncelleme: ${data.timestamp}`;
            if (tableBody) {
                tableBody.innerHTML = '';
                data.data.forEach(coin => {
                    const priceFixed = coin.price < 1 ? 4 : 2;
                    let signalColor = '#9ca3af'; // Gray
                    if (coin.score > 0) signalColor = '#10b981'; // Green
                    if (coin.score < 0) signalColor = '#ef4444'; // Red
                    
                    const row = `
                        <tr>
                            <td><span style="font-weight:600">${coin.symbol}</span></td>
                            <td>$${coin.price.toFixed(priceFixed)}</td>
                            <td style="color:${coin.change >= 0 ? '#10b981' : '#ef4444'}">%${coin.change.toFixed(2)}</td>
                            <td style="font-weight:bold; color:${coin.rsi < 30 ? '#10b981' : (coin.rsi > 70 ? '#ef4444' : 'inherit')}">${coin.rsi}</td>
                            <td>$${(coin.volume / 1000000).toFixed(1)}M</td>
                            <td><span class="badge" style="background:${signalColor}20; color:${signalColor}">${coin.signal}</span></td>
                            <td>${coin.score}</td>
                        </tr>
                    `;
                    tableBody.innerHTML += row;
                });
            }
        }
    } catch (e) {
        console.error("Scanner Error:", e);
        if (statusLabel) statusLabel.innerText = 'Hata oluştu';
        if (tableBody) tableBody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:red;">Veri alınamadı.</td></tr>';
    }
}
"""
    with open(path, 'w', encoding='utf-8') as f:
        f.write(good_content + new_code)
    print("Fixed script.js")
else:
    print("Marker not found")
