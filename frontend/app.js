(function () {
  const body = document.body;
  const defaultEndpoint = body.dataset.endpoint?.trim();
  const params = new URLSearchParams(window.location.search);
  const userEndpoint = params.get('source')?.trim();
  const endpoint = userEndpoint || defaultEndpoint;

  const statusBanner = document.getElementById('statusBanner');
  const statusMessage = document.getElementById('statusMessage');
  const refreshButton = document.getElementById('refreshButton');

  const generatedAtEl = document.getElementById('generatedAt');
  const runTimestampEl = document.getElementById('runTimestamp');
  const totalPostsEl = document.getElementById('totalPosts');
  const topSymbolsEl = document.getElementById('topSymbols');
  const collectionBreakdownEl = document.getElementById('collectionBreakdown');
  const credibilityBreakdownEl = document.getElementById('credibilityBreakdown');
  const marketAnalysisEl = document.getElementById('marketAnalysis');
  const riskAssessmentEl = document.getElementById('riskAssessment');
  const symbolAnalysesEl = document.getElementById('symbolAnalyses');
  const topInsightsEl = document.getElementById('topInsights');

  function setStatus(message, type) {
    if (!message) {
      statusBanner.hidden = true;
      statusBanner.className = 'status-banner';
      statusMessage.textContent = '';
      return;
    }

    statusBanner.hidden = false;
    statusBanner.className = `status-banner ${type}`.trim();
    statusMessage.textContent = message;
  }

  function formatDate(value) {
    if (!value) return '—';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
      return value;
    }
    return date.toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  }

  function textFallback(value, fallback = '—') {
    if (value === null || value === undefined) return fallback;
    if (typeof value === 'string' && value.trim() === '') return fallback;
    return value;
  }

  function renderSummary(summary = {}, totalPostsFallback = '—') {
    generatedAtEl.textContent = formatDate(summary.generated_at);
    runTimestampEl.textContent = summary.collection_timestamp
      ? formatDate(summary.collection_timestamp)
      : textFallback(summary.timestamp);

    totalPostsEl.textContent = summary.total_posts_collected ?? totalPostsFallback;

    if (Array.isArray(summary.top_symbols) && summary.top_symbols.length) {
      topSymbolsEl.textContent = summary.top_symbols
        .map(([symbol, count]) => `${symbol} (${count})`)
        .join(', ');
    } else {
      topSymbolsEl.textContent = '—';
    }

    const marketStatusEl = document.getElementById('marketStatus');
    if (marketStatusEl) {
        if (summary.market_status) {
            const isOpen = summary.market_status.isTheStockMarketOpen;
            marketStatusEl.textContent = isOpen ? 'Open' : 'Closed';
            marketStatusEl.className = `summary-value ${isOpen ? 'status-open' : 'status-closed'}`;
        } else {
            marketStatusEl.textContent = '—';
        }
    }

    collectionBreakdownEl.innerHTML = '';
    Object.entries(summary.by_type || {}).forEach(([key, value]) => {
      const li = document.createElement('li');
      li.textContent = `${key.replace('_', ' ')}: ${value}`;
      collectionBreakdownEl.appendChild(li);
    });

    credibilityBreakdownEl.innerHTML = '';
    Object.entries(summary.average_credibility_scores || {}).forEach(([key, value]) => {
      const li = document.createElement('li');
      li.textContent = `${key.replace('_', ' ')}: ${Number(value).toFixed(2)}`;
      credibilityBreakdownEl.appendChild(li);
    });
  }

  function renderAnalyses(data) {
    marketAnalysisEl.textContent = textFallback(data.deepseek_market_analysis, 'No market analysis available.');
    riskAssessmentEl.textContent = textFallback(data.deepseek_risk_assessment, 'No risk assessment available.');

    symbolAnalysesEl.innerHTML = '';
    const analyses = data.deepseek_symbol_analyses || {};
    if (analyses && Object.keys(analyses).length) {
      Object.entries(analyses).forEach(([symbol, analysis]) => {
        const card = document.createElement('article');
        card.className = 'symbol-card';
        const title = document.createElement('h3');
        title.textContent = symbol;
        const body = document.createElement('p');
        body.textContent = analysis;
        card.appendChild(title);
        card.appendChild(body);
        symbolAnalysesEl.appendChild(card);
      });
    } else {
      const empty = document.createElement('p');
      empty.className = 'empty-state';
      empty.textContent = 'No symbol-specific analyses available for this run.';
      symbolAnalysesEl.appendChild(empty);
    }
  }

  function renderInsights(insights = []) {
    topInsightsEl.innerHTML = '';
    if (!Array.isArray(insights) || !insights.length) {
      const empty = document.createElement('p');
      empty.className = 'empty-state';
      empty.textContent = 'No Reddit insights collected for this run.';
      const wrapper = document.createElement('li');
      wrapper.appendChild(empty);
      topInsightsEl.appendChild(wrapper);
      return;
    }

    insights.slice(0, 12).forEach((insight) => {
      const li = document.createElement('li');
      const card = document.createElement('div');
      card.className = 'insight-card';

      const header = document.createElement('header');
      const title = document.createElement('h3');
      title.textContent = insight.title || 'Untitled insight';
      header.appendChild(title);

      if (insight.symbol) {
        const badge = document.createElement('span');
        badge.className = 'badge';
        badge.textContent = insight.symbol;
        header.appendChild(badge);
      }

      if (insight.source) {
        const badge = document.createElement('span');
        badge.className = 'badge source';
        badge.textContent = insight.source;
        header.appendChild(badge);
      }

      const meta = document.createElement('div');
      meta.className = 'insight-meta';
      if (insight.created_time) meta.appendChild(createMetaChip('Captured', insight.created_time));
      if (typeof insight.credibility_score === 'number') meta.appendChild(createMetaChip('Credibility', Number(insight.credibility_score).toFixed(2)));
      if (typeof insight.composite_score === 'number') meta.appendChild(createMetaChip('Composite', Number(insight.composite_score).toFixed(2)));
      if (insight.type) meta.appendChild(createMetaChip('Type', insight.type.replace('_', ' ')));

      const body = document.createElement('p');
      body.textContent = insight.content || 'No content provided.';

      card.appendChild(header);
      card.appendChild(meta);
      card.appendChild(body);

      if (insight.url) {
        const link = document.createElement('a');
        link.href = insight.url;
        link.target = '_blank';
        link.rel = 'noopener noreferrer';
        link.textContent = 'Open original discussion →';
        card.appendChild(link);
      }

      li.appendChild(card);
      topInsightsEl.appendChild(li);
    });
  }

  function createMetaChip(label, value) {
    const span = document.createElement('span');
    span.textContent = `${label}: ${value}`;
    return span;
  }

  async function fetchLatest() {
    if (!endpoint) {
      setStatus('No data source configured. Provide a bucket JSON URL via ?source=…', 'error');
      return;
    }

    setStatus('Fetching latest DeepSeek analysis…', 'info');

    try {
      const antiCacheEndpoint = `${endpoint}${endpoint.includes('?') ? '&' : '?'}ts=${Date.now()}`;
      const response = await fetch(antiCacheEndpoint, { cache: 'no-store' });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const payload = await response.json();
      const { summary = {} } = payload;

      renderSummary({
        ...summary,
        generated_at: payload.generated_at || payload.generatedAt || summary.generated_at,
        timestamp: payload.timestamp,
      }, payload.total_posts_collected);
      renderAnalyses(payload);
      renderInsights(payload.top_insights);

      const updatedText = `Last updated ${formatDate(payload.generated_at || payload.generatedAt || Date.now())}`;
      setStatus(updatedText, 'info');
    } catch (error) {
      console.error('Failed to load DeepSeek analysis', error);
      setStatus(`Failed to load DeepSeek analysis: ${error.message}`, 'error');
    }
  }

  refreshButton?.addEventListener('click', fetchLatest);

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', fetchLatest);
  } else {
    fetchLatest();
  }
})();
