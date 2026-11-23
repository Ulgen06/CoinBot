/* ÜLGEN v30 Dashboard Script */

// Config
const API_BASE = '/api';
const REFRESH_RATE = 5000; // 5 seconds

// Globals
let equityChart = null;
let treemapChart = null;
let liqsChart = null;

document.addEventListener('DOMContentLoaded', () => {
    // 1. Essentials (Must load first)
    initNavigation();
    initTheme();
    initClock();

    // 2. Visuals (Charts must be ready before data)
    try {
        initChart();
        initProCharts();
        initTradingViewEvents();
    } catch (e) {
        console.warn("Chart Engine Error (Offline Mode?):", e);
    }

    try {
        initMarketInsights();
        initMatrixLog();
        initHeatmap();
        updateWidgets();
        simulateAIBoot();
    } catch (e) {
        console.warn("Widget Init Error:", e);
    }

    // 3. Data & Logic (Fetch LAST to ensure charts exist)
    fetchData();
    setupSSE();
    initAIChat();
    initTimeframeEvents();
    initLiqsChart();
    updateSignalDashboard();
    updateLiquidationRadar();

    // Auto Refresh
    setInterval(fetchData, REFRESH_RATE);
    // Widget Refresh
    setInterval(updateWidgets, 30000);
});

/* --- Restored Widgets --- */

function renderTreemap(coins) {
    const container = document.getElementById('market-treemap');
    if (!container || !coins || coins.length === 0) return;

    // CMC-style weights for top coins to determine box sizes
    const weights = {
        'BTC': 1200, 'ETH': 800, 'SOL': 500, 'BNB': 450, 'XRP': 400,
        'DOGE': 350, 'ADA': 300, 'AVAX': 280, 'TRX': 260, 'DOT': 240,
        'LINK': 220, 'NEAR': 200, 'POL': 180, 'LTC': 160, 'FET': 150,
        'PEPE': 140, 'TAO': 130, 'RENDER': 120, 'APT': 110, 'SUI': 100,
        'OP': 90, 'ARB': 80, 'TIA': 70, 'STX': 60, 'FIL': 55
    };

    const seriesData = coins.map(c => {
        const sym = c.symbol.replace('USDT', '');
        const change = c.change || 0;
        const price = c.price || 0;

        // Manual Color Calculation (TradingView/Coin360 Style)
        let color = '#4b5563'; // Neutral
        if (change >= 3) color = '#15803d'; // Deep Green
        else if (change > 0) color = '#22c55e'; // Green
        else if (change <= -3) color = '#991b1b'; // Deep Red
        else if (change < 0) color = '#ef4444'; // Red

        return {
            x: sym,
            y: weights[sym] || 50, // Volume/MarketCap Weight
            itemChange: change,
            itemPrice: price,
            color: color
        };
    }).sort((a, b) => b.y - a.y); // Maintain order by weight

    const options = {
        series: [{ data: seriesData }],
        chart: {
            type: 'treemap',
            height: 500,
            toolbar: { show: false },
            background: 'transparent',
            animations: { enabled: true, speed: 600 }
        },
        colors: seriesData.map(d => d.color),
        plotOptions: {
            treemap: {
                distributed: true,
                enableShades: false,
                useFillColorAsStroke: true
            }
        },
        stroke: {
            show: true,
            width: 3,
            colors: ['#0f172a']
        },
        dataLabels: {
            enabled: true,
            style: {
                fontSize: '16px',
                fontWeight: '800',
                fontFamily: 'Outfit, sans-serif',
                colors: ['#fff']
            },
            offsetY: 0,
            formatter: (text, op) => {
                const item = seriesData[op.dataPointIndex];
                if (!item) return text;
                const priceStr = item.itemPrice > 100 ? item.itemPrice.toFixed(2) :
                    (item.itemPrice > 1 ? item.itemPrice.toFixed(3) : item.itemPrice.toFixed(6));
                return [
                    text,
                    `$${priceStr}`,
                    `${item.itemChange >= 0 ? '+' : ''}${item.itemChange.toFixed(1)}%`
                ];
            }
        },
        tooltip: {
            theme: 'dark',
            custom: function ({ series, seriesIndex, dataPointIndex, w }) {
                const item = seriesData[dataPointIndex];
                const color = item.itemChange >= 0 ? '#10b981' : '#ef4444';
                return `
                    <div style="background: rgba(15, 23, 42, 0.95); padding: 12px; border-radius: 8px; border: 1px solid rgba(255,255,255,0.1); backdrop-filter: blur(10px);">
                        <div style="font-weight:bold; font-size:1.2rem; color:#fff; border-bottom: 1px solid rgba(255,255,255,0.1); padding-bottom: 5px; margin-bottom: 5px;">${item.x} / USDT</div>
                        <div style="font-size:1.1rem; color:#f8fafc">$${item.itemPrice.toLocaleString()}</div>
                        <div style="color:${color}; font-weight:bold; font-size:1.1rem; margin-top:5px;">${item.itemChange >= 0 ? '+' : ''}${item.itemChange.toFixed(2)}%</div>
                    </div>
                `;
            }
        }
    };

    if (treemapChart) {
        treemapChart.updateOptions(options);
    } else {
        container.innerHTML = '';
        treemapChart = new ApexCharts(container, options);
        treemapChart.render();
    }
}

function initHeatmap() {
    console.log("Heatmap logic initialized.");
}

/* Dedicated Liquidation Page Logic */
async function updateLiquidationPage(timeframe = '24h', btnElement = null) {
    if (btnElement) {
        document.querySelectorAll('.liq-tab-p').forEach(t => t.classList.remove('active'));
        btnElement.classList.add('active');
    }

    const chartContainer = document.getElementById('liq-walls-chart');
    const gridContainer = document.getElementById('liq-price-grid');
    const tableBody = document.getElementById('liq-impact-body');
    const totalShortEl = document.getElementById('page-total-short');
    const totalLongEl = document.getElementById('page-total-long');

    if (!chartContainer || !tableBody) return;

    try {
        const res = await fetch(`${API_BASE}/liquidation_levels?timeframe=${timeframe}`);
        const data = await res.json();

        const price = data.current_price || 0;
        const priceEl = document.getElementById('liq-page-price');
        if (priceEl) priceEl.innerText = `$${price.toLocaleString()}`;

        // Update Totals
        const fmtVal = (v) => "$" + (v / 1_000_000).toFixed(1) + "M";
        if (totalShortEl) totalShortEl.innerText = fmtVal(data.total_short);
        if (totalLongEl) totalLongEl.innerText = fmtVal(data.total_long);

        // 1. Render Table with Risk Categorization
        tableBody.innerHTML = '';
        data.levels.forEach(lvl => {
            const isShort = lvl.type === 'SHORT';
            const color = isShort ? '#ef4444' : '#10b981';

            // Heuristic Impact (%)
            const impactPct = (lvl.volume / 100_000_000) * 0.85;

            // Risk Levels
            let riskClass = '';
            let riskLabel = 'DÜŞÜK';
            let riskColor = '#4b5563';

            if (lvl.volume > 150_000_000) {
                riskClass = 'critical-row';
                riskLabel = 'KRİTİK';
                riskColor = color;
            } else if (lvl.volume > 75_000_000) {
                riskClass = 'major-row';
                riskLabel = 'YÜKSEK';
                riskColor = isShort ? '#f87171' : '#34d399';
            }

            const row = `
                <tr class="${riskClass}" style="border-bottom: 1px solid rgba(255,255,255,0.03); transition: background 0.3s;">
                    <td style="padding:12px 15px; font-weight:800; color: #fff; font-family: 'Courier New';">$${lvl.price.toLocaleString()}</td>
                    <td style="padding:12px 15px; color:${color}; font-weight:bold;">${isShort ? 'SHORT' : 'LONG'}</td>
                    <td style="padding:12px 15px;">${fmtVal(lvl.volume)}</td>
                    <td style="padding:12px 15px; text-align: right; color: #9ca3af;">%${lvl.distance.toFixed(2)}</td>
                    <td style="padding:12px 15px; text-align: right;">
                        <span style="background:${riskColor}22; color:${riskColor}; padding: 2px 8px; border-radius: 4px; font-weight:bold; font-size: 0.7rem; margin-right: 8px;">${riskLabel}</span>
                        <span style="color:#fff; font-weight:800;">%${impactPct.toFixed(2)}</span>
                    </td>
                </tr>
            `;
            tableBody.innerHTML += row;
        });

        // 2. Render Visualization with Grid & Glow
        const maxVol = Math.max(...data.levels.map(l => l.volume));
        const maxRange = 0.05; // 5% range display

        // Clear only bars, keep permanent elements if any
        // Remove old bars and price lines
        const oldElements = chartContainer.querySelectorAll('.liq-wall-bar, .price-grid-line, .price-grid-label');
        oldElements.forEach(el => el.remove());

        // Draw Price Grid Lines (+/- 1%, 2%, 3%, 4%, 5%)
        for (let i = -5; i <= 5; i++) {
            if (i === 0) continue;
            const gridDist = i / 100;
            const gridTop = 50 - (gridDist / maxRange * 50);
            const gridPrice = price * (1 + gridDist);

            const line = document.createElement('div');
            line.className = 'price-grid-line';
            line.style.top = `${gridTop}%`;

            const label = document.createElement('div');
            label.className = 'price-grid-label';
            label.style.top = `${gridTop}%`;
            label.innerText = `$${Math.round(gridPrice).toLocaleString()} (${i > 0 ? '+' : ''}${i}%)`;

            chartContainer.appendChild(line);
            chartContainer.appendChild(label);
        }

        data.levels.forEach(lvl => {
            const dist = (lvl.price - price) / price;
            if (Math.abs(dist) > maxRange) return;

            const topPct = 50 - (dist / maxRange * 50);
            const isShort = lvl.type === 'SHORT';
            const color = isShort ? '#ef4444' : '#10b981';
            const wallClass = isShort ? 'wall-short' : 'wall-long';

            // Width based on volume (5% to 60%)
            const widthPct = (lvl.volume / maxVol) * 55 + 5;

            const bar = document.createElement('div');
            bar.className = `liq-wall-bar ${wallClass}`;
            bar.style.position = 'absolute';
            bar.style.top = `${topPct}%`;
            bar.style.height = lvl.volume > 150_000_000 ? '6px' : '3px';
            bar.style.transition = 'all 0.5s ease-out';

            if (isShort) {
                bar.style.right = '50%';
                bar.style.width = '0%'; // Start at 0 for animation
                bar.style.background = `linear-gradient(to right, ${color}, transparent)`;
                setTimeout(() => bar.style.width = `${widthPct}%`, 50);
            } else {
                bar.style.left = '50%';
                bar.style.width = '0%';
                bar.style.background = `linear-gradient(to left, ${color}, transparent)`;
                setTimeout(() => bar.style.width = `${widthPct}%`, 50);
            }

            bar.style.transform = 'translateY(-50%)';
            bar.title = `$${lvl.price.toLocaleString()} | Vol: ${fmtVal(lvl.volume)}`;

            chartContainer.appendChild(bar);
        });

    } catch (e) {
        console.error("Page Liq Error:", e);
    }
}



async function updateBotChoice() {
    try {
        const res = await fetch(`${API_BASE}/bot_choice`);
        const data = await res.json();

        const container = document.querySelector('.bot-choice');
        if (container && data) {
            container.innerHTML = `
                <div class="coin-icon-lg" style="width:40px; height:40px;">
                    <img src="${data.icon}" alt="${data.symbol}">
                </div>
                <div class="choice-details">
                    <h3 style="font-size:1.2rem">$${data.symbol}</h3>
                    <span class="highlight" style="font-size:0.8rem; color:${data.confidence > 80 ? '#10b981' : '#f97316'}">
                        ${data.signal} (%${data.confidence})
                    </span>
                </div>
            `;
        }
    } catch (e) { console.error("Bot Choice Error:", e); }
}

async function updateWidgets() {
    // New Periodic Updates
    try { updateSentiment(); } catch (e) { }
    try {
        if (document.getElementById('risk-page') &&
            (document.getElementById('risk-page').style.display !== 'none' ||
                document.querySelector('.nav-item#nav-risk.active'))) {
            updateRiskMatrix();
        }
    } catch (e) { }

    // Calendar
    try {
        const r = await fetch('/api/calendar');
        if (r.status !== 200) return;
        const d = await r.json();
        const calDiv = document.getElementById('calendar-widget');
        if (calDiv) {
            if (!d || d.length === 0) calDiv.innerHTML = '<div class="empty-state">Yakın tarihli olay yok.</div>';
            else {
                calDiv.innerHTML = d.map(e => `
                    <div class="cal-item">
                        <div class="cal-date">${e.date.slice(5, 10)}</div>
                        <div class="cal-event">${e.event}</div>
                        <div class="cal-days">${e.days_left} Gün</div>
                    </div>
                `).join('');
            }
        }
    } catch (e) { console.error('Calendar Error', e); }
}

function initNavigation() {
    const navItems = document.querySelectorAll('.nav-item');
    const sections = document.querySelectorAll('.page-section');

    navItems.forEach(item => {
        item.addEventListener('click', (e) => {
            if (!item.id) return;
            e.preventDefault();

            console.log("-----------------------------------");
            console.log(`🖱️ TIKLANDI: ${item.id}`);

            // 1. Determine Target Page ID
            let targetId = '';
            if (item.id === 'nav-dashboard') targetId = 'dashboard-page';
            else if (item.id === 'nav-warroom') targetId = 'warroom-page';
            else if (item.id === 'nav-risk') targetId = 'risk-page';
            else if (item.id === 'nav-portfolio') targetId = 'portfolio-page';
            else if (item.id === 'nav-news') targetId = 'news-page';
            else if (item.id === 'nav-strategy') targetId = 'strategy-page';
            else if (item.id === 'nav-scanner') targetId = 'scanner-page';
            else if (item.id === 'nav-liq') targetId = 'liq-page';
            else if (item.id === 'nav-coti') targetId = 'coti-page';
            else if (item.id === 'nav-test') targetId = 'test-page';
            else if (item.id === 'nav-settings') targetId = 'settings-page';

            console.log(`🎯 HEDEF SAYFA ID: ${targetId}`);

            const targetSection = document.getElementById(targetId);
            if (!targetSection) {
                console.error(`❌ HEDEF KESİM BULUNAMADI: #${targetId}`);
                alert(`Sayfa yüklenemedi: #${targetId}`);
                return;
            } else {
                console.log(`✅ HEDEF KESİM BULUNDU:`, targetSection);
            }

            // 2. Update Active State
            navItems.forEach(nav => nav.classList.remove('active'));
            item.classList.add('active');

            sections.forEach(section => {
                section.classList.remove('active');
                // Force hide style to be sure
                section.style.display = 'none';
            });

            // Activate target
            targetSection.classList.add('active');
            targetSection.style.display = 'block'; // Force JS style override
            console.log(`✨ YENİ GÖRÜNÜM: display=${targetSection.style.display}, classes=${targetSection.className}`);

            // 3. Specific Logic
            if (targetId === 'strategy-page') loadBotConfig();
            if (targetId === 'scanner-page') updateScanner();
            if (targetId === 'liq-page') updateLiquidationPage('24h', item);
            if (targetId === 'warroom-page') initWarRoom();
            if (targetId === 'risk-page') updateRiskMatrix();
        });
    });
}

function initTheme() {
    const savedTheme = localStorage.getItem('ulgen_theme') || 'default';
    applyTheme(savedTheme);

    const themeCards = document.querySelectorAll('.theme-card');
    themeCards.forEach(card => {
        card.addEventListener('click', () => {
            const theme = card.getAttribute('data-theme');
            applyTheme(theme);
            localStorage.setItem('ulgen_theme', theme);
        });
    });
}

function applyTheme(themeName) {
    // Set Body Attribute
    if (themeName === 'default') {
        document.body.removeAttribute('data-theme');
    } else {
        document.body.setAttribute('data-theme', themeName);
    }

    // Update Active Card UI
    document.querySelectorAll('.theme-card').forEach(c => {
        c.classList.remove('active');
        if (c.getAttribute('data-theme') === themeName) {
            c.classList.add('active');
        }
    });
}

function initClock() {
    setInterval(() => {
        const now = new Date();
        document.getElementById('clock').innerText = now.toLocaleTimeString('tr-TR');
    }, 1000);
}

function initChart() {
    const options = {
        series: [{
            name: 'Toplam Varlık',
            data: []
        }],
        chart: {
            type: 'area',
            height: 350,
            toolbar: { show: false },
            background: 'transparent',
            animations: {
                enabled: true,
                easing: 'easeinout',
                speed: 800
            }
        },
        colors: ['#3b82f6'],
        fill: {
            type: 'gradient',
            gradient: {
                shadeIntensity: 1,
                opacityFrom: 0.7,
                opacityTo: 0.1,
                stops: [0, 90, 100]
            }
        },
        dataLabels: { enabled: false },
        stroke: {
            curve: 'smooth',
            width: 3
        },
        xaxis: {
            type: 'datetime',
            tooltip: { enabled: false },
            axisBorder: { show: false },
            axisTicks: { show: false },
            labels: { style: { colors: '#9ca3af' } }
        },
        yaxis: {
            labels: {
                style: { colors: '#9ca3af' },
                formatter: (value) => { return "$" + value.toFixed(0) }
            }
        },
        grid: {
            borderColor: 'rgba(255, 255, 255, 0.05)',
            strokeDashArray: 4,
        },
        theme: { mode: 'dark' }
    };

    equityChart = new ApexCharts(document.querySelector("#equityChart"), options);
    equityChart.render();
}

async function fetchData() {
    try {
        await Promise.all([
            updatePortfolio(),
            updatePrices(),
            updateNews(),
            updateBotChoice(),
            updateProMetrics('COTI'), // Focus on COTI Insights
            updateSignalDashboard(),
            updateLiquidationRadar()
        ]);
        updateStatus(true);
    } catch (e) {
        console.error("Data Fetch Error:", e);
        updateStatus(false);
    }
}

async function updatePortfolio() {
    try {
        const res = await fetch(`${API_BASE}/portfolio`);
        if (!res.ok) throw new Error("Portfolio Fetch Failed");
        const data = await res.json();
        currentData = data; // Store for timeframe filtering

        console.log("Portfolio Data:", data);

        // Update Stats with null checks
        if (document.getElementById('total-equity')) {
            document.getElementById('total-equity').innerText = `$${(data.equity || 0).toFixed(2)}`;
        }
        if (document.getElementById('total-profit')) {
            document.getElementById('total-profit').innerText = `$${(data.profit || 0).toFixed(2)}`;
        }

        // Open Positions Count
        const posCount = data.positions ? Object.keys(data.positions).length : 0;
        if (document.getElementById('open-positions-count')) {
            document.getElementById('open-positions-count').innerText = posCount;
        }

        // Colorize Profit
        const profitEl = document.getElementById('total-profit');
        if (profitEl) {
            profitEl.style.color = (data.profit || 0) >= 0 ? '#10b981' : '#ef4444';
        }

        // Update Chart
        // Fix Chart Data Mapping
        if (data.equity_history && data.equity_history.length > 0) {
            // Format: [[timestamp, value], ...]
            // FIX: user wallet uses 'time', not 'timestamp'
            const seriesData = data.equity_history.map(item => [(item.time || item.timestamp) * 1000, item.equity]);
            equityChart.updateSeries([{ data: seriesData }]);
        }

        // Update Trade History Table
        const tableBody = document.getElementById('trade-history-body');
        if (tableBody && data.trade_history) {
            tableBody.innerHTML = '';
            // Reverse to show newest first
            const history = [...data.trade_history].reverse();

            history.forEach(trade => {
                const row = `
                <tr>
                    <td>${trade.date || new Date(trade.timestamp ? trade.timestamp * 1000 : Date.now()).toLocaleDateString()}</td>
                    <td><span style="font-weight:600">${trade.symbol}</span></td>
                    <td><span class="type-badge ${trade.type.toLowerCase()}">${trade.type}</span></td>
                    <td>$${(trade.entry || trade.price || 0)}</td>
                    <td>$${(trade.amount || 0).toFixed(2)}</td>
                    <td style="color: ${trade.pnl_usd >= 0 ? '#10b981' : '#ef4444'}">
                        ${trade.pnl_usd >= 0 ? '+' : ''}${(trade.pnl_usd || 0).toFixed(2)}
                    </td>
                </tr>
            `;
                tableBody.innerHTML += row;
            });
        }

        // Elite: Update Sentiment & Performance
        updateSentiment();
        updatePerformance(data);
        renderPositions(data.positions);

    } catch (e) {
        console.error("Portfolio Update Error:", e);
    }
}

async function renderPositions(positions) {
    const tableBody = document.getElementById('active-positions-body');
    const dashBody = document.getElementById('dashboard-positions-body');
    if (!tableBody && !dashBody) return;

    const noPosHtml = '<tr><td colspan="6" style="text-align:center; padding:2rem; color:var(--text-muted);">Açık pozisyon bulunmuyor.</td></tr>';

    if (!positions || Object.keys(positions).length === 0) {
        if (tableBody) tableBody.innerHTML = noPosHtml;
        if (dashBody) dashBody.innerHTML = noPosHtml;
        return;
    }

    if (tableBody) tableBody.innerHTML = '';
    if (dashBody) dashBody.innerHTML = '';

    for (const [symbol, pos] of Object.entries(positions)) {
        // Fetch current price from lastPrices if available
        const curPrice = window.lastPrices && window.lastPrices[symbol] ? window.lastPrices[symbol].price :
            (window.lastPrices && window.lastPrices[symbol + 'USDT'] ? window.lastPrices[symbol + 'USDT'].price : 0);

        const entryPrice = pos.entry || pos.avg_price || 0;
        const margin = pos.amount || pos.qty || 0;
        const type = pos.type || 'LONG';
        const leverage = 10;

        let pnl = 0;
        if (curPrice > 0 && entryPrice > 0) {
            const pnlPct = type === 'LONG'
                ? ((curPrice - entryPrice) / entryPrice) * leverage
                : ((entryPrice - curPrice) / entryPrice) * leverage;
            pnl = margin * pnlPct;
        }

        const pnlColor = pnl >= 0 ? '#10b981' : '#ef4444';
        const displaySym = symbol.replace('USDT', '');

        const row = `
            <tr>
                <td>
                    <div style="display:flex; flex-direction:column;">
                        <span style="font-weight:600">${displaySym}</span>
                        <span style="font-size:0.7rem; color:${type === 'LONG' ? '#10b981' : '#ef4444'}">${type} x${leverage}</span>
                    </div>
                </td>
                <td>$${(margin).toFixed(2)}</td>
                <td>$${(entryPrice).toFixed(2)}</td>
                <td>$${curPrice > 0 ? curPrice.toFixed(2) : '---'}</td>
                <td style="color: ${pnlColor}; font-weight:bold;">
                    ${pnl >= 0 ? '+' : ''}$${pnl.toFixed(2)}
                </td>
                <td>
                    <div style="display:flex; gap:5px;">
                        <button class="btn-small glass" onclick="closePosition('${symbol}')" style="color:#ef4444; border-color:rgba(239,68,68,0.3);">Kapat</button>
                        <button class="btn-small glass" onclick="closeAndManage('${symbol}')" style="color:var(--primary); border-color:rgba(59,130,246,0.3);">Kapat ve Sen Yönet</button>
                    </div>
                </td>
            </tr>
        `;
        if (tableBody) tableBody.innerHTML += row;
        if (dashBody) dashBody.innerHTML += row;
    }
}

async function closePosition(symbol) {
    if (!confirm(`${symbol} pozisyonunu mevcut fiyattan kapatmak istediğinize emin misiniz?`)) return;

    try {
        const res = await fetch(`${API_BASE}/close_position`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol })
        });

        const data = await res.json();
        if (data.status === 'success') {
            showNotification('Başarılı', `${symbol} pozisyonu kapatıldı. K/Z: $${data.pnl.toFixed(2)}`);
            fetchData(); // Refresh UI
        } else {
            alert('Hata: ' + data.message);
        }
    } catch (e) {
        console.error("Close Position Error:", e);
        alert('İşlem başarısız oldu.');
    }
}

// Portfolio Form Handler
const tradeForm = document.getElementById('tradeForm');
if (tradeForm) {
    tradeForm.addEventListener('submit', async (e) => {
        e.preventDefault();

        const payload = {
            symbol: document.getElementById('t-symbol').value,
            type: document.getElementById('t-type').value,
            amount: document.getElementById('t-amount').value,
            price: document.getElementById('t-price').value
        };

        try {
            const res = await fetch(`${API_BASE}/trade`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            if (res.ok) {
                tradeForm.reset();
                fetchData();
                alert('İşlem Başarıyla Kaydedildi! ✅');
            } else {
                alert('Hata oluştu!');
            }
        } catch (err) {
            console.error(err);
            alert('Sunucu hatası!');
        }
    });
}

async function updatePrices() {
    try {
        const res = await fetch(`${API_BASE}/prices`);
        if (!res.ok) throw new Error("Price fetch failed");
        const data = await res.json();

        // Compare with old prices for flash effect
        if (window.lastPrices) {
            if (data.BTCUSDT && data.BTCUSDT.price !== window.lastPrices.BTCUSDT?.price) {
                flashElement('stat-equity', data.BTCUSDT.price > window.lastPrices.BTCUSDT.price ? 'up' : 'down');
            }
        }
        window.lastPrices = data;

        const coinsArray = [];
        for (const [symbol, info] of Object.entries(data)) {
            if (!info || typeof info.price !== 'number') continue;
            coinsArray.push({
                symbol: symbol,
                change: info.change || 0,
                price: info.price
            });
        }

        // Render Treemap
        renderTreemap(coinsArray);
    } catch (e) {
        console.error("Update Prices error:", e);
    }
}

async function updateNews() {
    try {
        console.log("Fetching news...");
        const res = await fetch(`${API_BASE}/news`);
        const data = await res.json();
        console.log("News data:", data);

        const list = document.getElementById('news-list');
        const fullList = document.getElementById('full-news-list');

        let htmlContent = '';

        if (!data.items || data.items.length === 0) {
            htmlContent = '<div class="empty-state">Henüz yeni haber yok.</div>';
        } else {
            htmlContent = data.items.map(n => `
                <div class="news-item" onclick="alert('${n.msg.replace(/'/g, "\\'").replace(/\n/g, '\\n')}')">
                    <div class="news-content">
                        <div class="news-meta">
                            <span class="news-source-tag">${n.source}</span>
                            <span class="time">${(n.published_at || '').split('T')[1]?.slice(0, 5) || n.published_at?.slice(11, 16) || ''}</span>
                        </div>
                        <h4>${n.title}</h4>
                        <div class="news-meta">
                            <span class="sentiment ${n.sentiment}"></span> ${(n.sentiment || '').toUpperCase()}
                            <span style="margin-left:auto">Etki: ${n.impact}/10</span>
                        </div>
                    </div>
                </div>
                `).join('');
        }

        if (list) list.innerHTML = htmlContent;
        if (fullList) fullList.innerHTML = htmlContent;

    } catch (e) {
        console.error("News Update Error:", e);
    }
}

function updateStatus(isOnline) {
    const dot = document.querySelector('.status-indicator .dot');
    const text = document.querySelector('.status-indicator span');

    if (isOnline) {
        if (dot) {
            dot.classList.add('online');
            dot.style.color = '#10b981';
        }
        if (text) text.innerText = "Sistem Çevrimiçi";
    } else {
        if (dot) {
            dot.classList.remove('online');
            dot.style.color = '#ef4444';
        }
        if (text) text.innerText = "Bağlantı Koptu";
    }
}

function setupSSE() {
    const evtSource = new EventSource('/stream');
    evtSource.onmessage = function (event) { };
}

function getCoinSlug(symbol) {
    return 'bitcoin'; // Simplified
}

/* AI CHAT & WIDGETS RESTORED */
function initAIChat() {
    const input = document.getElementById('ai-command-input');
    const window = document.getElementById('ai-chat-window');

    if (!input) return;

    input.addEventListener('keypress', async (e) => {
        if (e.key === 'Enter') {
            submitCommand(input.value);
            input.value = '';
        }
    });
}

async function submitCommand(cmd) {
    if (!cmd) return;
    const window = document.getElementById('ai-chat-window');

    addChatMsg(cmd, 'user');

    try {
        addChatMsg('İşlem yapılıyor...', 'bot', true);
        const r = await fetch(`${API_BASE}/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: cmd })
        });
        const d = await r.json();

        const loading = document.querySelector('.loading-msg');
        if (loading) loading.remove();

        if (d.status === 'success') {
            addChatMsg(d.response, 'bot');
        } else {
            addChatMsg('Hata: ' + d.response, 'error');
        }
    } catch (e) {
        const loading = document.querySelector('.loading-msg');
        if (loading) loading.remove();
        addChatMsg('Bağlantı hatası.', 'error');
    }
}

function addChatMsg(text, type, isLoading = false) {
    const win = document.getElementById('ai-chat-window');
    if (!win) return;
    const div = document.createElement('div');
    div.className = `chat-msg ${type} ${isLoading ? 'loading-msg' : ''}`;

    let prefix = 'YOU >';
    if (type === 'bot') prefix = 'ULGEN_AI >';
    if (type === 'error') prefix = 'SYSTEM >';

    div.innerHTML = `<span class="prefix">${prefix}</span> ${text}`;
    win.appendChild(div);
    win.scrollTop = win.scrollHeight;
}

async function updateWidgets() {
    // Calendar
    try {
        const r = await fetch('/api/calendar');
        const d = await r.json();
        const calDiv = document.getElementById('calendar-widget');
        if (calDiv) {
            if (d.length === 0) calDiv.innerHTML = '<div class="empty-state">Yakın tarihli olay yok.</div>';
            else {
                calDiv.innerHTML = d.map(e => `
                    <div class="cal-item">
                        <div class="cal-date">${e.date.slice(5, 10)}</div>
                        <div class="cal-event">${e.event}</div>
                        <div class="cal-days">${e.days_left} Gün</div>
                    </div>
                `).join('');
            }
        }
    } catch (e) { }

    // Whales
    try {
        const r = await fetch(`${API_BASE}/whales`);
        if (!r.ok) throw new Error("Fetch failed");
        const d = await r.json();
        const wDiv = document.getElementById('whale-feed');
        if (wDiv) {
            const whales = d.whales || [];
            if (whales.length === 0) {
                wDiv.innerHTML = '<div class="empty-state" style="text-align:center; padding:1.5rem; color:var(--text-muted); font-size:0.8rem;">Okyanus durgun, büyük bir hareket bekleniyor... 🌊</div>';
            } else {
                wDiv.innerHTML = whales.map(w => `
                    <div class="whale-item" style="display:flex; justify-content:space-between; padding:8px; border-bottom:1px solid rgba(255,255,255,0.05); font-size:0.82rem; animation: slideIn 0.3s ease-out;">
                        <span style="color:${w.side === 'BUY' ? '#10b981' : '#ef4444'}; font-weight:bold; width:45px;">${w.side}</span>
                        <span style="font-weight:600; flex:1; margin-left:8px;">${w.symbol}</span>
                        <span style="color:var(--primary); font-family:monospace; font-weight:bold;">$${(w.value / 1000000).toFixed(2)}M</span>
                    </div>
                `).join('');
            }
        }
    } catch (e) {
        console.warn("Whale Radar Error:", e);
        const wDiv = document.getElementById('whale-feed');
        if (wDiv) wDiv.innerHTML = '<div style="text-align:center; color:#ef4444; padding:1rem; font-size:0.75rem;">Bağlantı Hatası</div>';
    }
}

setInterval(updateWidgets, 30000);
setTimeout(updateWidgets, 1000);
initAIChat();

/* Strategy Heatmap logic */
// Duplicate initHeatmap removed.
// The primary definition is now at the top of the file.

/* Price Flash Animation */
function flashElement(id, type) {
    const el = document.getElementById(id);
    if (!el) return;
    const color = type === 'up' ? 'rgba(16, 185, 129, 0.4)' : 'rgba(239, 68, 68, 0.4)';
    el.style.backgroundColor = color;
    el.style.transition = 'background-color 0.5s ease';
    setTimeout(() => { el.style.backgroundColor = 'transparent'; }, 500);
}

/* TradingView Integration */
function initTradingViewEvents() {
    try {
        const btnEv = document.getElementById('btn-equity');
        const btnTv = document.getElementById('btn-tradingview');
        const eqChart = document.getElementById('equityChart');
        const tvChart = document.getElementById('tv-chart-container');

        if (btnTv && btnEv) {
            console.log("TradingView buttons bound.");
            btnTv.addEventListener('click', () => {
                console.log("TV Clicked");
                btnEv.classList.remove('active');
                btnTv.classList.add('active');
                if (eqChart) eqChart.style.display = 'none';
                if (tvChart) tvChart.style.display = 'block';
                loadTradingView('BTCUSDT');
            });

            btnEv.addEventListener('click', () => {
                console.log("Equity Clicked");
                btnTv.classList.remove('active');
                btnEv.classList.add('active');
                if (tvChart) tvChart.style.display = 'none';
                if (eqChart) eqChart.style.display = 'block';
            });
        }
    } catch (e) {
        console.error("TradingView Context Error:", e);
    }
}

function loadTradingView(symbol) {
    new TradingView.widget({
        "autosize": true,
        "symbol": `BINANCE:${symbol}`,
        "interval": "15",
        "timezone": "Etc/UTC",
        "theme": "dark",
        "style": "1",
        "locale": "tr",
        "toolbar_bg": "#f1f3f6",
        "enable_publishing": false,
        "hide_side_toolbar": false,
        "allow_symbol_change": true,
        "container_id": "tv-chart-container"
    });
}

/* AI Sentiment Gauge (Global Metrics) */
async function updateSentiment() {
    try {
        const res = await fetch(`${API_BASE}/global-metrics`);
        const data = await res.json();

        const gauge = document.getElementById('sentiment-gauge');
        const label = document.getElementById('sentiment-label');
        const btcDomEl = document.getElementById('ulgen-btc-dom');
        const pulseEl = document.getElementById('market-pulse');
        const socialEl = document.getElementById('social-score');

        if (!gauge) return;

        // 1. Update Gauge
        const score = data.fear_greed || 50;
        gauge.style.setProperty('--sentiment-left', `${score}%`);

        const style = document.createElement('style');
        style.innerHTML = `#sentiment-gauge::after { left: ${score}% !important; }`;
        document.head.appendChild(style);

        // 2. Update Label
        let sentimentText = data.fear_greed_label || "NÖTR";
        if (score <= 25) sentimentText = "AŞIRI KORKU 😨";
        else if (score < 45) sentimentText = "KORKU 📉";
        else if (score > 75) sentimentText = "AŞIRI AÇGÖZLÜLÜK 🚀";
        else if (score > 55) sentimentText = "AÇGÖZLÜLÜK 📈";
        else sentimentText = "NÖTR ⚖️";

        if (label) {
            label.innerText = `${score} - ${sentimentText}`;
            label.style.color = score > 50 ? '#10b981' : (score < 40 ? '#ef4444' : '#f59e0b');
        }

        // 3. Update Social / Dominance
        let domValue = parseFloat(data.btc_dominance) || 54.2;
        if (domValue > 100 || domValue < 30) domValue = 54.2; // Reality check

        if (btcDomEl) btcDomEl.innerText = `${domValue.toFixed(1)}%`;
        if (pulseEl) pulseEl.innerText = data.market_pulse || "Analiz ediliyor...";
        if (socialEl) socialEl.innerText = `${data.social_score || 0}/100`;

        // Elite: BTC.D fix for side display
        const sideBtcD = document.getElementById('btc-dom-value');
        if (sideBtcD) sideBtcD.innerText = `${domValue.toFixed(1)}%`;

    } catch (e) {
        console.warn("Global Metrics Error:", e);
    }
}

/* Performance Metrics */
function updatePerformance(data) {
    if (!data.trade_history) return;

    const total = data.trade_history.length;
    const wins = data.trade_history.filter(t => t.pnl_usd > 0).length;
    const rate = total > 0 ? ((wins / total) * 100).toFixed(1) : 0;
    const best = Math.max(...data.trade_history.map(t => t.pnl_usd || 0));

    if (document.getElementById('stat-win-loss')) {
        document.getElementById('stat-win-loss').innerText = `${wins}/${total - wins}`;
    }
    if (document.getElementById('stat-success-rate')) {
        document.getElementById('stat-success-rate').innerText = `%${rate}`;
    }
    if (document.getElementById('stat-best-trade')) {
        document.getElementById('stat-best-trade').innerText = `$${best.toFixed(2)}`;
    }
}

/* AI Command Shortcuts */
function executeShortcut(cmd) {
    submitCommand(cmd);
}

/* Notifications */
function showNotification(title, msg) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.innerHTML = `<strong>${title}</strong><br>${msg}`;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 5000);
}
/* Chart Timeframe Logic */
let currentData = null;

function initTimeframeEvents() {
    try {
        const buttons = document.querySelectorAll('.tf-btn');
        console.log("Timeframe buttons found:", buttons.length);
        buttons.forEach(btn => {
            btn.addEventListener('click', () => {
                console.log("Timeframe clicked:", btn.dataset.tf);
                buttons.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                updateChartTimeframe(btn.dataset.tf);
            });
        });
    } catch (e) {
        console.error("Timeframe Init Error:", e);
    }
}

/* --- Phase 6: Professional Functions --- */
async function loadBotConfig() {
    try {
        const res = await fetch(`${API_BASE}/config`);
        const cfg = await res.json();

        document.getElementById('cfg-leverage').value = cfg.leverage;
        document.getElementById('cfg-leverage').nextElementSibling.innerText = cfg.leverage + 'x';
        document.getElementById('cfg-risk').value = cfg.risk_percent;
        document.getElementById('cfg-sl').value = cfg.stop_loss_pct;
        document.getElementById('cfg-tp').value = cfg.take_profit_pct;
        document.getElementById('cfg-mode').value = cfg.trader_mode;
        document.getElementById('cfg-trailing').checked = cfg.trailing_stop || false;
    } catch (e) { console.error("Config Load Error:", e); }
}

async function saveBotConfig() {
    const cfg = {
        leverage: parseInt(document.getElementById('cfg-leverage').value),
        risk_percent: parseFloat(document.getElementById('cfg-risk').value),
        stop_loss_pct: parseFloat(document.getElementById('cfg-sl').value),
        take_profit_pct: parseFloat(document.getElementById('cfg-tp').value),
        trader_mode: document.getElementById('cfg-mode').value,
        trailing_stop: document.getElementById('cfg-trailing').checked
    };

    try {
        const res = await fetch(`${API_BASE}/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(cfg)
        });
        showNotification('Tamam!', 'Strateji ayarları güncellendi kanka.');
    } catch (e) { showNotification('Hata!', 'Ayarlar kaydedilemedi.'); }
}

let proCharts = {};

function initProCharts() {
    const commonOptions = {
        chart: {
            type: 'area',
            height: 350,
            animations: { enabled: true, easing: 'linear', dynamicAnimation: { speed: 1000 } },
            toolbar: { show: false },
            zoom: { enabled: false },
            background: 'transparent'
        },
        stroke: { curve: 'smooth', width: 2 },
        fill: {
            type: 'gradient',
            gradient: { shadeIntensity: 1, opacityFrom: 0.45, opacityTo: 0.05, stops: [20, 100] }
        },
        dataLabels: { enabled: false },
        xaxis: {
            type: 'datetime',
            labels: { show: true, style: { colors: '#8a8aa0' } },
            axisBorder: { show: false },
            axisTicks: { show: false }
        },
        yaxis: { labels: { show: true, style: { colors: '#8a8aa0' } } },
        grid: { borderColor: 'rgba(255,255,255,0.05)' },
        theme: { mode: 'dark' },
        tooltip: { theme: 'dark', x: { format: 'dd MMM HH:mm' } }
    };

    const containers = [
        { id: "#cvdFuturesChart", key: "cvd_futures", name: "Futures CVD", color: "#4cc9f0", type: 'line' },
        { id: "#cvdSpotChart", key: "cvd_spot", name: "Spot CVD", color: "#f72585", type: 'line' },
        { id: "#fundingChart", key: "funding", name: "Funding Rate", color: "#4361ee", type: 'bar' },
        { id: "#oiChart", key: "oi", name: "Open Interest", color: "#fee440", type: 'area' },
        { id: "#bidAskChart", key: "bid_ask_futures", name: "Net Bid/Ask Vol", color: "#10b981", type: 'bar' }
    ];

    containers.forEach(box => {
        const el = document.querySelector(box.id);
        if (el) {
            // Clone options to avoid reference issues
            let options = JSON.parse(JSON.stringify(commonOptions));
            options.colors = [box.color];
            options.chart.type = box.type || 'area';

            // Specific overrides
            if (box.key === 'funding') {
                options.stroke.width = 0;
                options.fill.type = 'solid';
            }
            if (box.key === 'bid_ask_futures') {
                options.plotOptions = {
                    bar: { colors: { ranges: [{ from: -1000000000, to: 0, color: '#ef4444' }, { from: 0, to: 1000000000, color: '#10b981' }] } }
                };
            }

            proCharts[box.key] = new ApexCharts(el, options);
            proCharts[box.key].render();
        }
    });
}

async function updateProMetrics(symbol = 'COTI') {
    try {
        const response = await fetch(`${API_BASE}/pro-metrics/${symbol}`);
        const res = await response.json();

        if (res.status === 'success' && res.data) {
            const m = res.data;

            // Page stats update (Headline items)
            if (m.summary) {
                const btcdEl = document.getElementById('coti-btcd');
                const volEl = document.getElementById('coti-volume');
                // For now mapping summary to existing elements
                if (btcdEl) btcdEl.innerText = `OI: $${(m.summary.oi_cur / 1000000).toFixed(2)}M`;
                if (volEl) volEl.innerText = `Fund: ${m.summary.funding_cur.toFixed(4)}%`;
            }

            // Update Charts
            if (proCharts.cvd_futures && m.cvd_futures) {
                proCharts.cvd_futures.updateSeries([{ name: 'Futures CVD', data: m.cvd_futures }]);
            }
            if (proCharts.cvd_spot && m.cvd_spot) {
                proCharts.cvd_spot.updateSeries([{ name: 'Spot CVD', data: m.cvd_spot }]);
            }
            if (proCharts.funding && m.funding_history) {
                proCharts.funding.updateSeries([{ name: 'Funding Rate', data: m.funding_history }]);
            }
            if (proCharts.oi && m.oi_history) {
                proCharts.oi.updateSeries([{ name: 'Open Interest', data: m.oi_history }]);
            }
            if (proCharts.bid_ask_futures && m.net_bid_ask_futures) {
                proCharts.bid_ask_futures.updateSeries([{ name: 'Net Delta', data: m.net_bid_ask_futures }]);
            }
        }
    } catch (e) {
        console.error("Pro Metrics Error:", e);
    }
}

function updateChartTimeframe(tf) {
    if (!currentData || !currentData.equity_history) return;

    let seriesData = currentData.equity_history.map(item => [(item.time || item.timestamp) * 1000, item.equity]);
    const now = Date.now();
    let filterMs = 0;

    switch (tf) {
        case '1h': filterMs = 60 * 60 * 1000; break;
        case '4h': filterMs = 4 * 60 * 60 * 1000; break;
        case '1d': filterMs = 24 * 60 * 60 * 1000; break;
        case '1w': filterMs = 7 * 24 * 60 * 60 * 1000; break;
        case '1m': filterMs = 30 * 24 * 60 * 60 * 1000; break;
        case '1y': filterMs = 365 * 24 * 60 * 60 * 1000; break;
    }

    if (filterMs > 0) {
        seriesData = seriesData.filter(d => (now - d[0]) < filterMs);
    }

    if (equityChart) {
        equityChart.updateSeries([{ data: seriesData }]);
    }
}

/* Sentiment Logic */
async function updateSentiment() {
    try {
        const res = await fetch(`${API_BASE}/sentiment`);
        const json = await res.json();

        if (json.status === 'success') {
            const fg = json.fear_greed;
            const soc = json.social;

            // Update Fear & Greed Label
            const sentLabel = document.getElementById('sentiment-label');
            if (sentLabel) {
                sentLabel.innerText = `${fg.value} - ${fg.label}`;
                sentLabel.style.color = fg.value > 50 ? '#10b981' : '#ef4444';
            }

            // Update BTC Dom
            const domEl = document.getElementById('btc-dom');
            if (domEl && json.btc_dominance) {
                domEl.innerText = `${json.btc_dominance}%`;
            }

            // Update Pulse
            const pulseEl = document.getElementById('market-pulse');
            if (pulseEl && json.market_pulse) {
                pulseEl.innerText = json.market_pulse;
                // Color Logic for Pulse
                if (json.market_pulse.includes('AYI') || json.market_pulse.includes('PANİK')) pulseEl.style.color = '#ef4444';
                else if (json.market_pulse.includes('RALLİ') || json.market_pulse.includes('HYPE')) pulseEl.style.color = '#10b981';
                else pulseEl.style.color = '#f59e0b';
            }

            // Update Social Score

            // Update Social Score
            const socEl = document.getElementById('social-score');
            if (socEl) {
                socEl.innerText = `${soc.score}/100`;
                socEl.onclick = () => alert(`Sosyal Analiz: ${soc.label}\nPlatform: ${soc.platform}`);
                socEl.style.cursor = 'pointer';
            }

            // Update Gauge (Simple text fallback or visual update if chart exists)
            // Assuming no gauge chart instance for now or if exists update it
        }
    } catch (e) {
        console.error("Sentiment Error:", e);
    }
}

/* Backtest Logic */
let backtestChart = null;

async function runBacktest() {
    const coin = document.getElementById('bt-coin').value;
    const tf = document.getElementById('bt-timeframe').value;
    const strat = document.getElementById('bt-strategy').value;
    const bal = document.getElementById('bt-balance').value;

    // UI Loading State
    const btn = document.querySelector('#test-page button');
    const originalText = btn.innerHTML;
    btn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Simülasyon Çalışıyor...';
    btn.disabled = true;

    try {
        const res = await fetch(`${API_BASE}/backtest`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ coin, timeframe: tf, strategy: strat, balance: bal })
        });

        const json = await res.json();

        if (json.status === 'success') {
            // Update Stats
            document.getElementById('bt-profit').innerText = `$${json.metrics.profit}`;
            document.getElementById('bt-profit').style.color = json.metrics.profit >= 0 ? '#10b981' : '#ef4444';
            document.getElementById('bt-winrate').innerText = `%${json.metrics.win_rate}`;
            document.getElementById('bt-trades').innerText = json.metrics.trades;
            document.getElementById('bt-drawdown').innerText = `%${json.metrics.drawdown}`;

            // Update Log
            const logBody = document.getElementById('bt-trade-log');
            logBody.innerHTML = json.log.map(t => `
                <tr>
                    <td>${t.date}</td>
                    <td><span class="badge ${t.type === 'BUY' ? 'bg-green' : 'bg-red'}">${t.type}</span></td>
                    <td>$${t.price}</td>
                    <td>${t.amount !== '-' ? t.amount : '--'}</td>
                    <td>${t.balance !== '-' ? '$' + t.balance : '--'}</td>
                </tr>
            `).join('');

            // Render Chart
            renderBacktestChart(json.equity_curve);
        } else {
            alert("Simülasyon Hatası: " + json.message);
        }

    } catch (e) {
        console.error("Backtest Error:", e);
        alert("Bağlantı Hatası!");
    } finally {
        btn.innerHTML = originalText;
        btn.disabled = false;
    }
}

function renderBacktestChart(data) {
    const series = [{
        name: 'Bakiye ($)',
        data: data.map(d => [d.time, d.equity])
    }];

    const options = {
        series: series,
        chart: {
            type: 'area',
            height: 350,
            toolbar: { show: false },
            background: 'transparent'
        },
        dataLabels: { enabled: false },
        stroke: { curve: 'smooth', width: 2, colors: ['#3b82f6'] },
        fill: {
            type: 'gradient',
            gradient: {
                shadeIntensity: 1,
                opacityFrom: 0.7,
                opacityTo: 0.1,
                stops: [0, 90, 100],
                colorStops: [{ offset: 0, color: '#3b82f6', opacity: 0.5 }, { offset: 100, color: '#3b82f6', opacity: 0 }]
            }
        },
        xaxis: {
            type: 'datetime',
            tooltip: { enabled: false },
            axisBorder: { show: false },
            axisTicks: { show: false },
            labels: { style: { colors: '#777' } }
        },
        yaxis: {
            labels: { style: { colors: '#777' }, formatter: (v) => '$' + v.toFixed(0) }
        },
        grid: { borderColor: 'rgba(255,255,255,0.05)' },
        theme: { mode: 'dark' }
    };

    if (backtestChart) {
        backtestChart.updateOptions(options);
        backtestChart.updateSeries(series);
    } else {
        const el = document.querySelector("#backtestChart");
        if (el) {
            backtestChart = new ApexCharts(el, options);
            backtestChart.render();
        }
    }
}

/* --- Recovered/Missing Functions --- */
async function initMatrixLog() {
    const term = document.getElementById('matrix-terminal');
    if (!term) return;

    setInterval(async () => {
        try {
            const res = await fetch(`${API_BASE}/logs`);
            const data = await res.json();

            if (data.status === 'success' && data.logs) {
                // Clear and rebuild or append? Rebuild is safer for sync
                // Optimally we'd only append new ones but simple is fine for now
                term.innerHTML = data.logs.map(line => `<div>${line}</div>`).join('');
                term.scrollTop = term.scrollHeight; // Auto scroll
            }
        } catch (e) {
            // console.warn("Log Poll Error", e);
        }
    }, 2000);
}

function initMarketInsights() {
    // Already handled by updatePrices and updateNews partially
    console.log("Market Insights initialized.");
}

function simulateAIBoot() {
    const term = document.getElementById('ai-chat-window');
    if (term) {
        term.innerHTML += '<div class="chat-msg system">Sistem Başlatılıyor...</div>';
        setTimeout(() => term.innerHTML += '<div class="chat-msg system">Çekirdek Modüller Yüklendi.</div>', 800);
        setTimeout(() => term.innerHTML += '<div class="chat-msg system">Yapay Zeka Hazır.</div>', 1600);
    }
}

function initWhaleRadar() {
    const list = document.getElementById('whale-list');
    if (!list) return;

    setInterval(async () => {
        try {
            const res = await fetch(`${API_BASE}/whales`);
            const data = await res.json();

            if (data.status === 'success' && data.whales.length > 0) {
                list.innerHTML = data.whales.map(w => {
                    const color = w.side === 'BUY' ? '#10b981' : '#ef4444';
                    const icon = w.side === 'BUY' ? 'fa-arrow-up' : 'fa-arrow-down';
                    return `
                        <div class="whale-item" style="display:flex; justify-content:space-between; align-items:center; padding:0.8rem; margin-bottom:0.5rem; background:rgba(255,255,255,0.03); border-radius:8px; border-left:3px solid ${color};">
                            <div style="display:flex; flex-direction:column;">
                                <span style="font-weight:bold; color:#fff;">${w.symbol} <span style="color:${color}">${w.side}</span></span>
                                <span style="font-size:0.75rem; color:var(--text-muted);">${w.time}</span>
                            </div>
                            <div style="text-align:right;">
                                <div style="font-weight:bold; color:${color};">$${Math.floor(w.value).toLocaleString()}</div>
                                <span style="font-size:0.75rem; color:var(--text-muted);">@ $${w.price.toFixed(2)}</span>
                            </div>
                        </div>
                    `;
                }).join('');
            } else {
                list.innerHTML = '<div style="text-align:center; padding:2rem; color:var(--text-muted);"><i class="fa-solid fa-water"></i> Henüz balina hareketi yok...</div>';
            }
        } catch (e) { }
    }, 3000);
}

/* Scanner Logic */
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

            // Render Advanced Heatmap (New)
            renderHeatmap(data.data);

            // Find BTC Price for Liquidation Map (New)
            const btcData = data.data.find(c => c.symbol === 'BTCUSDT');
            if (btcData) {
                renderLiquidationMap(btcData.price);
            }

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
        // if (tableBody) tableBody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:red;">Veri alınamadı.</td></tr>';
    }
}

/* War Room Logic */
let wrInitialized = false;

function initWarRoom() {
    if (wrInitialized) return;
    setWarRoom('MAJOR');
    wrInitialized = true;
}

function setWarRoom(type) {
    const sets = {
        'MAJOR': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT'],
        'AI': ['TAOUSDT', 'FETUSDT', 'RENDERUSDT', 'GRTUSDT'],
        'MEME': ['DOGEUSDT', 'PEPEUSDT', 'SHIBUSDT', 'WIFUSDT']
    };

    const symbols = sets[type] || sets['MAJOR'];

    // Load Charts
    loadTvWidget('wr-chart-1', symbols[0]);
    loadTvWidget('wr-chart-2', symbols[1]);
    loadTvWidget('wr-chart-3', symbols[2]);
    loadTvWidget('wr-chart-4', symbols[3]);
}

function loadTvWidget(containerId, symbol) {
    if (!symbol) return;
    new TradingView.widget({
        'autosize': true,
        'symbol': `BINANCE:${symbol}`,
        'interval': '15',
        'timezone': 'Etc/UTC',
        'theme': 'dark',
        'style': '1',
        'locale': 'tr',
        'toolbar_bg': '#000000',
        'enable_publishing': false,
        'hide_top_toolbar': true,
        'hide_side_toolbar': true,
        'allow_symbol_change': true,
        'container_id': containerId
    });
}


/* Risk Matrix Logic */
let riskChart = null;

async function updateRiskMatrix() {
    try {
        const res = await fetch(`${API_BASE}/risk-matrix`);
        const json = await res.json();

        if (json.status === 'success') {
            renderHeatmap(json.correlation);
            renderRiskMetrics(json.risk_metrics);
        }
    } catch (e) {
        console.error("Risk Matrix Error:", e);
    }
}

function renderHeatmap(seriesData) {
    const options = {
        series: seriesData,
        chart: {
            height: 400,
            type: 'heatmap',
            toolbar: { show: false },
            background: 'transparent',
            events: {
                dataPointSelection: function (event, chartContext, config) {
                    // Interaction: When a heatmap block is clicked, show details or open a chart
                    // config.w.config.series[config.seriesIndex].name (Y-axis Coin)
                    // config.w.config.series[config.seriesIndex].data[config.dataPointIndex].x (X-axis Coin)
                    const coinY = config.w.config.series[config.seriesIndex].name;
                    const coinX = config.w.config.series[config.seriesIndex].data[config.dataPointIndex].x;
                    const val = config.w.config.series[config.seriesIndex].data[config.dataPointIndex].y;

                    alert(`Korelasyon Analizi:\n${coinY} vs ${coinX}\nOran: ${val}\n\n${val > 0.7 ? 'Yüksek korelasyon! Birlikte hareket ederler.' : 'Düşük korelasyon. Çeşitlendirme için iyi.'}`);
                }
            }
        },
        dataLabels: { enabled: true, style: { colors: ['#fff'] } },
        stroke: { show: true, width: 1, colors: ['#1e1e2d'] },
        colors: ["#008FFB"],
        title: { text: '' },
        theme: { mode: 'dark' },
        plotOptions: {
            heatmap: {
                shadeIntensity: 0.5,
                radius: 6,
                useFillColorAsStroke: false,
                colorScale: {
                    ranges: [
                        { from: -1, to: 0.2, name: 'Düşük (Güvenli)', color: '#00A100' },
                        { from: 0.21, to: 0.6, name: 'Orta', color: '#128FD9' },
                        { from: 0.61, to: 1, name: 'Yüksek (Riskli)', color: '#FF0000' }
                    ]
                }
            }
        },
        xaxis: { labels: { style: { colors: '#a0a0a0' } } },
        yaxis: { labels: { style: { colors: '#a0a0a0' } } }
    };

    if (riskChart) {
        riskChart.updateOptions(options);
    } else {
        const el = document.querySelector("#correlationChart");
        if (el) {
            riskChart = new ApexCharts(el, options);
            riskChart.render();
        }
    }
}

async function closeAndManage(symbol) {
    if (!confirm(`${symbol} pozisyonunu kapatıp yönetimi AI Bot'a devretmek istediğinize emin misiniz? Bot sizin yerinize yeni bir işlem açacaktır.`)) return;

    try {
        const res = await fetch(`${API_BASE}/close_position`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol })
        });
        const data = await res.json();
        if (data.status === 'success') {
            showNotification('Pozisyon Kapatıldı', `Yönetim AI'ya devrediliyor...`);
            const aiRes = await fetch(`${API_BASE}/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: `/trade_manage ${symbol}` })
            });
            const aiData = await aiRes.json();
            showNotification('AI Devraldı', aiData.response || "Bot analize başladı.");
            fetchData();
        } else {
            alert('Hata: ' + data.message);
        }
    } catch (e) {
        console.error("Close and Manage Error:", e);
        alert('İşlem başarısız oldu.');
    }
}

function renderRiskMetrics(m) {
    if (!m) return;

    // Level Color
    let color = '#10b981'; // Green
    if (m.level === 'ORTA') color = '#f59e0b';
    if (m.level === 'YÜKSEK') color = '#ef4444';

    const levelEl = document.getElementById('risk-level');
    if (levelEl) {
        levelEl.innerText = m.level;
        levelEl.style.color = color;
    }

    const volEl = document.getElementById('risk-vol');
    if (volEl) volEl.innerText = `${m.volatility}%`;

    const betaEl = document.getElementById('risk-beta');
    if (betaEl) betaEl.innerText = m.beta;
}

/* AI Signal Dashboard & Liquidation Radar Logic */
async function updateSignalDashboard() {
    const symbolEl = document.getElementById('signal-symbol');
    const symbol = symbolEl?.value || 'BTC';
    try {
        const res = await fetch(`${API_BASE}/signals/${symbol}`);
        const data = await res.json();

        const rsiEl = document.getElementById('signal-rsi');
        const macdEl = document.getElementById('signal-macd');
        const decEl = document.getElementById('signal-decision');

        if (data.status === 'success' && data.indicators) {
            if (rsiEl) rsiEl.innerText = data.indicators.rsi;
            if (macdEl) {
                macdEl.innerText = data.indicators.macd;
                macdEl.style.color = data.indicators.macd.includes('BOĞA') ? '#10b981' : '#ef4444';
            }

            if (decEl) {
                decEl.innerText = data.ai_decision;
                decEl.style.color = data.ai_score > 60 ? '#10b981' : (data.ai_score < 40 ? '#ef4444' : '#f59e0b');
                decEl.classList.add('pulse-anim');
            }
        } else {
            if (decEl) decEl.innerText = "Yükleniyor...";
        }
    } catch (e) {
        console.warn("Signal Dashboard Error:", e);
        const decEl = document.getElementById('signal-decision');
        if (decEl) decEl.innerText = "Bağlantı Yok";
    }
}

function initLiqsChart() {
    const container = document.querySelector("#liq-radar-chart");
    if (!container) return;

    const options = {
        series: [{ name: 'Liq Value', data: [] }],
        chart: { type: 'bar', height: 250, toolbar: { show: false }, background: 'transparent' },
        plotOptions: { bar: { borderRadius: 4, horizontal: true, distributed: true } },
        dataLabels: { enabled: false },
        colors: ['#ef4444'],
        xaxis: { categories: [], labels: { style: { colors: '#8a8aa0' } } },
        yaxis: { labels: { style: { colors: '#8a8aa0' } } },
        grid: { borderColor: 'rgba(255,255,255,0.05)' },
        theme: { mode: 'dark' },
        tooltip: { theme: 'dark', y: { formatter: (v) => `$${(v / 1000).toFixed(1)}k` } }
    };

    liqsChart = new ApexCharts(container, options);
    liqsChart.render();
}

async function updateLiquidationRadar() {
    if (!liqsChart) return;
    try {
        const res = await fetch(`${API_BASE}/liquidations`);
        const result = await res.json();
        if (result.status === 'success') {
            const btcData = result.data.BTCUSDT.walls;
            const seriesData = btcData.map(w => w.value);
            const categories = btcData.map(w => `$${w.price.toLocaleString()}`);

            liqsChart.updateOptions({
                xaxis: { categories: categories },
                series: [{ data: seriesData }]
            });
        }
    } catch (e) { console.warn("Liq Radar Error:", e); }
}
