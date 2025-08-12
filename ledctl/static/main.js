(async function () {
  try {
    const res = await fetch('/health');
    const data = await res.json();
    document.getElementById('health').textContent = data.status || 'unknown';
  } catch (err) {
    document.getElementById('health').textContent = 'error';
  }
  try {
    const r2 = await fetch('/metrics');
    const m = await r2.json();
    const el = document.createElement('pre');
    el.textContent = `uptime_s: ${m.uptime_s}\nrequests_total: ${m.requests_total}\nlast_request_ms: ${m.last_request_ms}`;
    document.body.appendChild(el);
  } catch (err) {
    // ignore
  }
})();


