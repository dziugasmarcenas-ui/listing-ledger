(() => {
  const $ = (id) => document.getElementById(id);
  const ui = {
    newDemo: $('new-demo'), loading: $('loading'), notice: $('notice'), empty: $('empty-state'),
    timeline: $('timeline'), replay: $('replay'), range: $('step-range'), stepOutput: $('step-output'),
    previous: $('previous'), next: $('next'), caption: $('stream-caption'), count: $('attempt-count'),
    lastStep: $('last-step-label'), state: $('projection-state'), title: $('listing-title'),
    currentAsk: $('current-ask'), lastAsk: $('last-ask'), asOf: $('as-of'),
    eventCaption: $('event-caption'), eventMeta: $('event-meta'), json: $('event-json'),
    copy: $('copy-event'), copyFeedback: $('copy-feedback')
  };

  let session = null;
  let loadRequestId = 0;
  let projectionRequestId = 0;
  let selectedIndex = 0;

  function setBusy(busy) {
    ui.loading.hidden = !busy;
    ui.newDemo.disabled = busy;
    document.querySelectorAll('[data-new-demo]').forEach((button) => { button.disabled = busy; });
  }

  function showNotice(message, retryAction = null) {
    ui.notice.replaceChildren(document.createTextNode(message));
    if (retryAction) {
      const button = document.createElement('button');
      button.className = 'notice-retry';
      button.type = 'button';
      button.textContent = 'Try again';
      button.addEventListener('click', retryAction, { once: true });
      ui.notice.append(document.createTextNode(' '), button);
    }
    ui.notice.hidden = false;
  }

  function clearNotice() {
    ui.notice.hidden = true;
    ui.notice.replaceChildren();
  }

  async function loadDemo() {
    const version = ++loadRequestId;
    projectionRequestId += 1;
    setBusy(true);
    clearNotice();
    session = null;
    ui.timeline.replaceChildren();
    ui.replay.hidden = true;
    ui.empty.hidden = true;
    resetInspector();
    try {
      const response = await fetch('/api/demo', { method: 'POST', headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error(`The demo could not be loaded (HTTP ${response.status}).`);
      const data = await response.json();
      if (version !== loadRequestId) return;
      if (!data.stream_id || !Array.isArray(data.attempts) || !Array.isArray(data.events)) {
        throw new Error('The demo response did not match the expected format.');
      }
      session = data;
      selectedIndex = 0;
      renderTimeline();
      ui.empty.hidden = true;
      ui.replay.hidden = false;
      ui.caption.textContent = `Stream ${data.stream_id}`;
      ui.count.textContent = `${data.attempts.length} ${data.attempts.length === 1 ? 'attempt' : 'attempts'}`;
      ui.range.min = '0';
      ui.range.max = String(data.attempts.length);
      ui.range.value = '0';
      ui.lastStep.textContent = `${data.attempts.length} ${data.attempts.length === 1 ? 'attempt' : 'attempts'}`;
      await selectStep(0);
    } catch (error) {
      if (version !== loadRequestId) return;
      session = null;
      ui.empty.hidden = false;
      ui.replay.hidden = true;
      showNotice(error instanceof Error ? error.message : 'The demo could not be loaded.', () => loadDemo());
      resetInspector();
    } finally {
      if (version === loadRequestId) setBusy(false);
    }
  }

  function renderTimeline() {
    ui.timeline.replaceChildren();
    session.attempts.forEach((attempt, index) => {
      const item = document.createElement('li');
      item.className = 'timeline-item';
      const button = document.createElement('button');
      button.className = 'timeline-entry';
      button.type = 'button';
      button.dataset.index = String(index + 1);
      button.setAttribute('aria-label', `${attempt.label}, receipt sequence ${attempt.sequence}${attempt.duplicate ? ', exact retry, no new record' : ''}`);
      button.addEventListener('click', () => selectStep(index + 1));

      const marker = document.createElement('span');
      marker.className = `timeline-marker${attempt.duplicate ? ' marker-duplicate' : ''}`;
      marker.setAttribute('aria-hidden', 'true');
      const content = document.createElement('span');
      content.className = 'timeline-content';
      const top = document.createElement('span');
      top.className = 'timeline-topline';
      const label = document.createElement('strong');
      label.textContent = attempt.label;
      const seq = document.createElement('span');
      seq.className = 'sequence';
      seq.textContent = `#${attempt.sequence}`;
      top.append(label, seq);

      const detail = document.createElement('span');
      detail.className = 'timeline-detail';
      const event = attempt.event || {};
      const status = event.status ? event.status[0].toUpperCase() + event.status.slice(1) : 'Event';
      const eventTime = event.observed_at ? formatDate(event.observed_at, { dateStyle: 'medium', timeStyle: 'short' }) : 'Time not supplied';
      detail.textContent = `${status} · observed UTC ${eventTime}`;
      content.append(top, detail);

      if (attempt.duplicate) {
        const badge = document.createElement('span');
        badge.className = 'duplicate-badge';
        badge.textContent = 'Exact retry · same receipt';
        content.append(badge);
      }
      button.append(marker, content);
      item.append(button);
      ui.timeline.append(item);
    });
  }

  async function selectStep(index) {
    if (!session) return;
    const bounded = Math.max(0, Math.min(session.attempts.length, Number(index)));
    selectedIndex = bounded;
    ui.range.value = String(bounded);
    ui.stepOutput.textContent = `${bounded} of ${session.attempts.length}`;
    ui.previous.disabled = bounded === 0;
    ui.next.disabled = bounded === session.attempts.length;
    ui.timeline.querySelectorAll('.timeline-entry').forEach((button) => {
      const selected = Number(button.dataset.index) === bounded;
      button.classList.toggle('is-selected', selected);
      button.setAttribute('aria-current', selected ? 'step' : 'false');
    });
    ui.copyFeedback.textContent = '';

    if (bounded > 0) {
      const attempt = session.attempts[bounded - 1];
      ui.eventCaption.textContent = attempt.duplicate ? 'Retry attempt · no additional event was stored.' : `Receipt sequence ${attempt.sequence}`;
      ui.eventMeta.hidden = false;
      ui.eventMeta.textContent = `${attempt.label} · receipt #${attempt.sequence}${attempt.duplicate ? ' · duplicate attempt' : ''}`;
      ui.json.querySelector('code').textContent = JSON.stringify(attempt.event, null, 2);
      ui.copy.disabled = false;
    } else {
      ui.eventCaption.textContent = 'No event has arrived at this step.';
      ui.eventMeta.hidden = true;
      ui.json.querySelector('code').textContent = '{\n  "event": "No receipt yet"\n}';
      ui.copy.disabled = true;
    }

    const version = ++projectionRequestId;
    setProjectionPending();
    const through = session.attempts.slice(0, bounded).reduce((max, attempt) => Math.max(max, attempt.sequence), 0);
    const stream = encodeURIComponent(session.stream_id);
    const listing = encodeURIComponent(session.listing_id);
    try {
      const response = await fetch(`/api/streams/${stream}/listings/${listing}?through_sequence=${through}`, { headers: { Accept: 'application/json' } });
      if (!response.ok) throw new Error(`Listing state could not be loaded (HTTP ${response.status}).`);
      const projection = await response.json();
      if (version !== projectionRequestId || selectedIndex !== bounded) return;
      renderProjection(projection);
      clearNotice();
    } catch (error) {
      if (version !== projectionRequestId || selectedIndex !== bounded) return;
      showProjectionError();
      showNotice(error instanceof Error ? error.message : 'Listing state could not be loaded.', () => selectStep(selectedIndex));
    }
  }

  function setProjectionPending() {
    ui.state.textContent = 'Loading';
    ui.state.dataset.status = 'unknown';
    ui.title.textContent = 'Loading reconstructed state';
    ui.currentAsk.textContent = 'Loading…';
    ui.lastAsk.textContent = 'Loading…';
    ui.asOf.textContent = 'Loading…';
  }

  function showProjectionError() {
    ui.state.textContent = 'Unavailable';
    ui.state.dataset.status = 'unknown';
    ui.title.textContent = 'Projection unavailable';
    ui.currentAsk.textContent = 'Unknown · projection failed';
    ui.lastAsk.textContent = 'Unknown · projection failed';
    ui.asOf.textContent = 'Not available';
  }

  function renderProjection(projection) {
    ui.title.textContent = projection.title || 'Listing title unknown';
    ui.state.textContent = projection.status ? capitalize(projection.status) : 'Unknown';
    ui.state.dataset.status = projection.status || 'unknown';
    ui.currentAsk.textContent = projection.price_minor === null || projection.price_minor === undefined
      ? 'No ask recorded at this step'
      : formatMoney(projection.price_minor, projection.currency);
    ui.lastAsk.textContent = projection.last_known_price_minor === null || projection.last_known_price_minor === undefined
      ? 'No known ask'
      : formatMoney(projection.last_known_price_minor, projection.last_known_price_currency);
    ui.asOf.textContent = `Receipt #${projection.as_of_sequence}`;
  }

  function resetInspector() {
    ui.state.textContent = 'No data';
    ui.state.dataset.status = 'unknown';
    ui.title.textContent = 'Waiting for demo';
    ui.currentAsk.textContent = '—';
    ui.lastAsk.textContent = '—';
    ui.asOf.textContent = '—';
    ui.eventCaption.textContent = 'Choose a timeline entry to inspect its payload.';
    ui.eventMeta.hidden = true;
    ui.json.querySelector('code').textContent = '{\n  "event": "Choose an attempt"\n}';
    ui.copy.disabled = true;
  }

  function formatMoney(minor, currency) {
    const digits = currency === 'JPY' ? 0 : 2;
    const amount = Number(minor) / (10 ** digits);
    try {
      return new Intl.NumberFormat(undefined, { style: 'currency', currency, maximumFractionDigits: digits }).format(amount);
    } catch {
      return `${currency || 'Unknown currency'} ${amount.toFixed(digits)}`;
    }
  }

  function formatDate(value, options) {
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? 'Time not supplied' : new Intl.DateTimeFormat(undefined, { ...options, timeZone: 'UTC' }).format(date);
  }

  function capitalize(value) {
    return value ? value.charAt(0).toUpperCase() + value.slice(1) : 'Unknown';
  }

  ui.newDemo.addEventListener('click', loadDemo);
  document.querySelectorAll('[data-new-demo]').forEach((button) => button.addEventListener('click', loadDemo));
  ui.range.addEventListener('input', (event) => selectStep(event.currentTarget.value));
  ui.previous.addEventListener('click', () => selectStep(selectedIndex - 1));
  ui.next.addEventListener('click', () => selectStep(selectedIndex + 1));
  ui.copy.addEventListener('click', async () => {
    if (!session || selectedIndex === 0) return;
    const event = session.attempts[selectedIndex - 1].event;
    try {
      await navigator.clipboard.writeText(JSON.stringify(event, null, 2));
      ui.copyFeedback.textContent = 'Event JSON copied.';
    } catch {
      ui.copyFeedback.textContent = 'Clipboard access failed. Select and copy the JSON above.';
      ui.json.focus();
    }
  });
  document.addEventListener('keydown', (event) => {
    if (!session || event.altKey || event.ctrlKey || event.metaKey) return;
    const target = event.target;
    if (target instanceof HTMLElement && (target.isContentEditable || ['INPUT', 'TEXTAREA', 'SELECT', 'BUTTON', 'A'].includes(target.tagName))) return;
    if (event.key === 'ArrowLeft') { event.preventDefault(); selectStep(selectedIndex - 1); }
    if (event.key === 'ArrowRight') { event.preventDefault(); selectStep(selectedIndex + 1); }
  });

  loadDemo();
})();
