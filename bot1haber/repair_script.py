
import os
import re

path = 'd:/Projelerim/bot1haber yeni/bot1haber/src/static/script.js'

# Read file
with open(path, 'r', encoding='utf-8', errors='ignore') as f:
    content = f.read()

# Fix 1: Clean up any corrupted text at the end caused by previous partial writes
# We will identify the last known good function (renderRiskMetrics) and truncate overlapping garbage
marker = "/* Risk Matrix Logic */"
idx = content.find(marker)

if idx != -1:
    # Get content up to the marker
    base_content = content[:idx]
    
    # Define the correct clean Risk Matrix Logic block
    risk_logic = """/* Risk Matrix Logic */
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
                dataPointSelection: function(event, chartContext, config) {
                    // Interaction: When a heatmap block is clicked, show details or open a chart
                    // config.w.config.series[config.seriesIndex].name (Y-axis Coin)
                    // config.w.config.series[config.seriesIndex].data[config.dataPointIndex].x (X-axis Coin)
                    const coinY = config.w.config.series[config.seriesIndex].name;
                    const coinX = config.w.config.series[config.seriesIndex].data[config.dataPointIndex].x;
                    const val = config.w.config.series[config.seriesIndex].data[config.dataPointIndex].y;
                    
                    alert(`Korelasyon Analizi:\\n${coinY} vs ${coinX}\\nOran: ${val}\\n\\n${val > 0.7 ? 'Yüksek korelasyon! Birlikte hareket ederler.' : 'Düşük korelasyon. Çeşitlendirme için iyi.'}`);
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
"""
    # Write the clean content
    with open(path, 'w', encoding='utf-8') as f:
        f.write(base_content + risk_logic)
    
    print("Successfully repaired script.js and added heatmap interaction.")

else:
    print("Could not find the Risk Logic marker to replace.")
