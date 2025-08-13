(async function () {
  try {
    const res = await fetch('/health');
    const data = await res.json();
    document.getElementById('health').textContent = data.status || 'unknown';
  } catch (err) {
    document.getElementById('health').textContent = 'error';
  }
  // Populate files
  try {
    const r = await fetch('/api/files');
    const j = await r.json();
    const ul = document.getElementById('files');
    ul.innerHTML = '';
    (j.files || []).forEach(f => {
      const li = document.createElement('li');
      const btn = document.createElement('button');
      btn.textContent = `Play ${f.name}`;
      btn.onclick = async () => {
        await fetch('/api/playback/start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ file: f.name })
        });
      };
      li.appendChild(btn);
      ul.appendChild(li);
    });
  } catch {}

  // Populate builtin animations
  try {
    const r = await fetch('/api/anims');
    const j = await r.json();
    const sel = document.getElementById('anim-select');
    sel.innerHTML = '';
    (j.anims || []).forEach(([value, label]) => {
      const o = document.createElement('option');
      o.value = value; o.textContent = label; sel.appendChild(o);
    });
  } catch {}

  // Brightness
  const b = document.getElementById('brightness');
  if (b) {
    b.addEventListener('change', async () => {
      await fetch('/api/brightness', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ value01: parseFloat(b.value) })
      });
    });
  }

  // Start builtin
  const btnAnim = document.getElementById('btn-anim');
  const selAnim = document.getElementById('anim-select');
  if (btnAnim && selAnim) {
    btnAnim.onclick = async () => {
      const name = selAnim.value;
      await fetch('/api/playback/start_builtin', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
      });
    };
  }

  // Stop
  const btnStop = document.getElementById('btn-stop');
  if (btnStop) {
    btnStop.onclick = async () => {
      await fetch('/api/playback/stop', { method: 'POST' });
    };
  }

  // Auto-refresh preview
  const img = document.getElementById('preview');
  if (img) {
    setInterval(() => {
      const ts = Date.now();
      img.src = `/api/preview.png?ts=${ts}`;
    }, 1000);
  }
})();


