// static/js/charts.js
(() => {
  'use strict';

  // ------- tiny DOM helpers -------
  const $ = (sel) => document.querySelector(sel);
  const ctx2d = (sel) => {
    const el = $(sel);
    return el && el.getContext ? el.getContext('2d') : null;
  };

  // ------- API endpoints -------
  const api = {
    volume:   (date)       => `/api/metrics/volume${date ? `?date=${encodeURIComponent(date)}` : ""}`,
    languages:(date)       => `/api/metrics/languages${date ? `?date=${encodeURIComponent(date)}` : ""}`,
    sources:  (date, top=6)=> `/api/metrics/sources?top=${top}${date ? `&date=${encodeURIComponent(date)}` : ""}`
  };

  // ------- Fetch helper with graceful fallback -------
  async function fetchJSON(url, fallback = []) {
    try {
      const r = await fetch(url, { headers: { 'Accept': 'application/json' } });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      return await r.json();
    } catch (err) {
      console.warn(`[charts] Failed to fetch ${url}:`, err);
      return fallback;
    }
  }

  // ------- Register datalabels if present -------
  if (window.ChartDataLabels && window.Chart?.register) {
    try { Chart.register(ChartDataLabels); } catch {}
  }

  // ------- Chart instances -------
  let pieLang, barSrc, barWeek;

  function destroyAll() {
    try { pieLang?.destroy(); } catch {}
    try { barSrc?.destroy(); }  catch {}
    try { barWeek?.destroy(); } catch {}
    pieLang = barSrc = barWeek = null;
  }

  // ------- Builders -------
  function buildLangPie(rows) {
    const ctx = ctx2d('#chart-lang');
    if (!ctx) return;

    // rows: [{label:'English', count:12}, ...]
    const total = rows.reduce((s, r) => s + (r.count || 0), 0) || 1;
    const labels = rows.map(r => r.label);
    const data   = rows.map(r => r.count || 0);

    pieLang?.destroy();
    pieLang = new Chart(ctx, {
      type: 'doughnut', // doughnut looks cleaner than pie, easier to read %s
      data: {
        labels,
        datasets: [{ data }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false, // match fixed container height
        cutout: '60%',
        plugins: {
          legend: { position: 'bottom' },
          datalabels: window.ChartDataLabels ? {
            formatter: (v) => `${Math.round((v / total) * 100)}%`,
            color: '#374151',
            font: { weight: '600' },
            anchor: 'center',
            align: 'center'
          } : undefined,
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const val = ctx.parsed;
                const pct = Math.round((val / total) * 100);
                return `${ctx.label}: ${val} (${pct}%)`;
              }
            }
          }
        }
      }
    });
  }

  function buildSrcBars(rows) {
    const ctx = ctx2d('#chart-src');
    if (!ctx) return;

    // rows: [{label:'BBC', count:8}, ...]
    const labels = rows.map(r => r.label);
    const data   = rows.map(r => r.count || 0);

    barSrc?.destroy();
    barSrc = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [{ label: 'Articles', data }]
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          x: { beginAtZero: true, ticks: { precision: 0 } }
        },
        plugins: { legend: { display: false } }
      }
    });
  }

  // Convert /api/metrics/volume daily points → weekday aggregation
  const weekdayName = (i) => ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'][i];

  function buildWeekBars(rows) {
    const ctx = ctx2d('#chart-week');
    if (!ctx) return;

    // rows: [{date:'YYYY-MM-DD', count:N}]
    const agg = {0:0,1:0,2:0,3:0,4:0,5:0,6:0};
    rows.forEach(r => {
      if (!r?.date) return;
      const dt = new Date(`${r.date}T00:00:00`);
      if (isNaN(+dt)) return;
      const wd = dt.getDay(); // 0=Sun
      agg[wd] = (agg[wd] || 0) + (r.count || 0);
    });

    const order = [1,2,3,4,5,6,0]; // Mon..Sun
    const labels = order.map(weekdayName);
    const data   = order.map(i => agg[i] || 0);

    barWeek?.destroy();
    barWeek = new Chart(ctx, {
      type: 'bar',
      data: { labels, datasets: [{ label: 'Articles', data }] },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { beginAtZero: true, ticks: { precision: 0 } }
        },
        plugins: { legend: { display: true, position: 'bottom' } }
      }
    });
  }

  // ------- Load all charts -------
  async function loadAll() {
    const dateSel = $('#flt-date');
    const dateVal = dateSel ? dateSel.value : '';

    const btn = $('#btn-refresh');
    if (btn) { btn.disabled = true; btn.textContent = 'Loading…'; }

    // Provide small demo fallbacks so UI still renders if API empty
    const [langs, srcs, vol] = await Promise.all([
      fetchJSON(api.languages(dateVal), [{label:'English',count:12},{label:'Arabic',count:8},{label:'Russian',count:6}]),
      fetchJSON(api.sources(dateVal, 6), [{label:'BBC',count:8},{label:'Reuters',count:7},{label:'CNN',count:6},{label:'Guardian',count:5},{label:'Al Jazeera',count:4},{label:'FT',count:3}]),
      fetchJSON(api.volume(dateVal), [
        {date:'2025-09-08',count:10},{date:'2025-09-09',count:12},{date:'2025-09-10',count:9},
        {date:'2025-09-11',count:14},{date:'2025-09-12',count:11},{date:'2025-09-13',count:8},{date:'2025-09-14',count:13}
      ])
    ]);

    destroyAll();
    buildLangPie(langs);
    buildSrcBars(srcs);
    buildWeekBars(vol);

    if (btn) { btn.disabled = false; btn.textContent = 'Refresh'; }
  }

  // ------- Wire controls and init -------
  document.addEventListener('DOMContentLoaded', () => {
    $('#btn-refresh')?.addEventListener('click', loadAll);
    $('#flt-date')?.addEventListener('change', loadAll);
    loadAll();
  });
})();
