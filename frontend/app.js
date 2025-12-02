(function () {
  const body = document.body;
  const defaultEndpoint = body.dataset.endpoint?.trim();
  const params = new URLSearchParams(window.location.search);
  const userEndpoint = params.get('source')?.trim();
  const endpoint = userEndpoint || defaultEndpoint;

  // UI Elements
  const statusBanner = document.getElementById('statusBanner');
  const statusMessage = document.getElementById('statusMessage');
  const refreshButton = document.getElementById('refreshButton');
  const historySelect = document.getElementById('historySelect');

  // Data Elements
  const generatedAtEl = document.getElementById('generatedAt');
  const runTimestampEl = document.getElementById('runTimestamp');
  const totalPostsEl = document.getElementById('totalPosts');
  const topSymbolsEl = document.getElementById('topSymbols');
  const marketStatusEl = document.getElementById('marketStatus');
  const collectionBreakdownEl = document.getElementById('collectionBreakdown');
  const credibilityBreakdownEl = document.getElementById('credibilityBreakdown');

  // Analysis Elements
  const marketAnalysisEl = document.getElementById('marketAnalysis');
  const riskAssessmentEl = document.getElementById('riskAssessment');
  const symbolAnalysesEl = document.getElementById('symbolAnalyses');
  const topInsightsEl = document.getElementById('topInsights');

  function setStatus(message, type = 'info') {
    if (!message) {
      statusBanner.hidden = true;
      return;
    }
    statusBanner.hidden = false;
    statusBanner.className = `status-indicator ${type}`;
    statusMessage.textContent = message;

    // Auto-hide after 5 seconds if it's just info
    if (type === 'info') {
      setTimeout(() => {
        statusBanner.hidden = true;
      }, 5000);
    }
  }

  function formatDate(value) {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return value;

    return new Intl.DateTimeFormat('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: 'numeric',
      hour12: true
    }).format(date);
  }

  function formatNumber(num) {
    return new Intl.NumberFormat('en-US').format(num);
  }

  function renderSummary(summary = {}) {
    generatedAtEl.textContent = formatDate(summary.generated_at || Date.now());
    runTimestampEl.textContent = formatDate(summary.collection_timestamp || summary.timestamp);
    totalPostsEl.textContent = formatNumber(summary.total_posts_collected || 0);

    // Top Symbols
    if (Array.isArray(summary.top_symbols) && summary.top_symbols.length) {
      topSymbolsEl.textContent = summary.top_symbols
        .slice(0, 3)
        .map(([symbol]) => symbol)
        .join(', ');
    } else {
      topSymbolsEl.textContent = '—';
    }

    // Market Status
    if (summary.market_status) {
      const isOpen = summary.market_status.isTheStockMarketOpen;
      marketStatusEl.textContent = isOpen ? 'Open' : 'Closed';
      marketStatusEl.className = `stat-value ${isOpen ? 'status-open' : 'status-closed'}`;
    } else {
      marketStatusEl.textContent = '—';
    }

    // Breakdowns
    renderList(collectionBreakdownEl, summary.by_type, (key, val) =>
      `${key.replace(/_/g, ' ')}: ${val}`
    );

    renderList(credibilityBreakdownEl, summary.average_credibility_scores, (key, val) =>
      `${key}: ${Number(val).toFixed(1)}/10`
    );
  }

  function renderList(container, data, formatter) {
    container.innerHTML = '';
    if (!data) return;

    Object.entries(data).forEach(([key, value]) => {
      const li = document.createElement('li');
      li.textContent = formatter(key, value);
      container.appendChild(li);
    });
  }

  function renderAnalyses(data) {
    // Market Analysis
    if (data.deepseek_market_analysis) {
      marketAnalysisEl.innerHTML = data.deepseek_market_analysis;
    } else {
      marketAnalysisEl.innerHTML = '<div class="loading-state">No market analysis available.</div>';
    }

    // Risk Assessment
    if (data.deepseek_risk_assessment) {
      riskAssessmentEl.innerHTML = data.deepseek_risk_assessment;
    } else {
      riskAssessmentEl.innerHTML = '<div class="loading-state">No risk assessment available.</div>';
    }

    // Symbol Analysis
    symbolAnalysesEl.innerHTML = '';
    const analyses = data.deepseek_symbol_analyses || {};

    if (Object.keys(analyses).length) {
      Object.entries(analyses).forEach(([symbol, analysis]) => {
        const card = document.createElement('article');
        card.className = 'symbol-card';
        card.innerHTML = `
          <h3>${symbol}</h3>
          <p>${analysis}</p>
        `;
        symbolAnalysesEl.appendChild(card);
      });
    } else {
      symbolAnalysesEl.innerHTML = '<div class="loading-state full-width">No symbol-specific analyses.</div>';
    }
  }

  function renderInsights(insights = []) {
    topInsightsEl.innerHTML = '';

    if (!Array.isArray(insights) || !insights.length) {
      topInsightsEl.innerHTML = '<div class="loading-state full-width">No insights collected.</div>';
      return;
    }

    insights.slice(0, 12).forEach((insight) => {
      const card = document.createElement('div');
      card.className = 'insight-card';

      const metaHtml = [
        insight.symbol ? `<span class="meta-tag">${insight.symbol}</span>` : '',
        insight.source ? `<span class="meta-tag">${insight.source}</span>` : '',
        insight.credibility_score ? `<span class="meta-tag">Cred: ${Number(insight.credibility_score).toFixed(1)}</span>` : ''
      ].join('');

      card.innerHTML = `
        <div class="insight-header">
          <h3>${insight.title || 'Untitled Insight'}</h3>
        </div>
        <div class="insight-meta">${metaHtml}</div>
        <p class="insight-content">${insight.content || 'No content provided.'}</p>
        ${insight.url ? `
          <a href="${insight.url}" target="_blank" rel="noopener" class="insight-link">
            Open Discussion
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
          </a>
        ` : ''}
      `;

      topInsightsEl.appendChild(card);
    });
  }

  async function fetchData(url) {
    if (!url) {
      // Try to load latest.json by default if no URL provided
      url = 'latest.json';
    }

    setStatus('Updating data...', 'info');
    refreshButton?.classList.add('spinning');

    try {
      const antiCacheUrl = `${url}?ts=${Date.now()}`;
      const response = await fetch(antiCacheUrl, { cache: 'no-store' });

      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const payload = await response.json();
      const { summary = {} } = payload;

      renderSummary({
        ...summary,
        generated_at: payload.generated_at || summary.generated_at,
        timestamp: payload.timestamp,
      });

      renderAnalyses(payload);
      renderInsights(payload.top_insights);

      setStatus(`Updated: ${formatDate(new Date())}`, 'info');

    } catch (error) {
      console.error('Load failed:', error);
      setStatus(`Failed to load data: ${error.message}`, 'error');
    } finally {
      refreshButton?.classList.remove('spinning');
    }
  }

  async function loadHistory() {
    try {
      const response = await fetch('history.json', { cache: 'no-store' });
      if (!response.ok) return;

      const history = await response.json();

      // Reset options
      historySelect.innerHTML = '<option value="latest.json">Latest Run</option>';

      history.forEach(entry => {
        const option = document.createElement('option');
        option.value = `history/${entry.filename}`;
        option.textContent = formatDate(entry.timestamp);
        historySelect.appendChild(option);
      });

    } catch (e) {
      console.warn('History load failed:', e);
    }
  }

  // Event Listeners
  historySelect?.addEventListener('change', (e) => fetchData(e.target.value));
  refreshButton?.addEventListener('click', () => fetchData(historySelect.value));

  // Init
  document.addEventListener('DOMContentLoaded', () => {
    loadHistory();
    fetchData(endpoint);
  });

})();
