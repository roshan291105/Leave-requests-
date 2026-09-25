(() => {
  const panel = document.querySelector('[data-focus-timer]');
  if (!panel) return;
  const duration = panel.querySelector('#focus-duration');
  const clock = panel.querySelector('.focus-clock');
  const toggle = panel.querySelector('[data-focus-toggle]');
  const reset = panel.querySelector('[data-focus-reset]');
  const message = panel.querySelector('.focus-message');
  const key = `dayora-focus-${panel.dataset.employee}`;
  let state = {minutes: 25, remaining: 1500000, end: null};
  let storageAvailable = true;
  try {
    const saved = JSON.parse(sessionStorage.getItem(key));
    if (saved && [5, 25, 50].includes(saved.minutes)
        && Number.isFinite(saved.remaining) && saved.remaining >= 0 && saved.remaining <= saved.minutes * 60000
        && (saved.end === null || (Number.isFinite(saved.end) && saved.end > 0 && saved.end <= Date.now() + saved.minutes * 60000))) {
      state = saved;
    }
  } catch (_) { storageAvailable = false; }

  const save = () => {
    try { sessionStorage.setItem(key, JSON.stringify(state)); }
    catch (_) { storageAvailable = false; }
  };
  const remaining = () => state.end === null ? state.remaining : Math.max(0, state.end - Date.now());
  const render = () => {
    if (state.end !== null && remaining() === 0) {
      state.end = null;
      state.remaining = 0;
      save();
    }
    const seconds = Math.ceil(remaining() / 1000);
    clock.textContent = `${String(Math.floor(seconds / 60)).padStart(2, '0')}:${String(seconds % 60).padStart(2, '0')}`;
    duration.value = String(state.minutes);
    duration.disabled = state.end !== null || (state.remaining > 0 && state.remaining < state.minutes * 60000);
    toggle.textContent = state.end !== null ? 'Pause' : state.remaining === 0 ? 'Start again' : state.remaining < state.minutes * 60000 ? 'Resume' : state.minutes === 5 ? 'Start break' : 'Start focus';
    const status = state.remaining === 0 ? (state.minutes === 5 ? 'Break complete. Ready for your next step?' : 'Session complete. Take a breath and enjoy a short break.')
      : state.end !== null ? (state.minutes === 5 ? 'A little time to recharge.' : 'One task. A little steady progress.')
      : state.remaining < state.minutes * 60000 ? 'Paused. Continue when you are ready.' : 'Ready when you are.';
    const text = status + (storageAvailable ? '' : ' This browser cannot save your timer; keep this page open.');
    if (message.textContent !== text) message.textContent = text;
  };
  toggle.addEventListener('click', () => {
    if (state.end !== null) {
      state.remaining = remaining();
      state.end = null;
    } else {
      if (state.remaining === 0) state.remaining = state.minutes * 60000;
      state.end = Date.now() + state.remaining;
    }
    save(); render();
  });
  reset.addEventListener('click', () => {
    state.remaining = state.minutes * 60000;
    state.end = null;
    save(); render();
  });
  duration.addEventListener('change', () => {
    const minutes = Number(duration.value);
    if (![5, 25, 50].includes(minutes)) return;
    state = {minutes, remaining: minutes * 60000, end: null};
    save(); render();
  });
  document.addEventListener('visibilitychange', render);
  window.addEventListener('pageshow', render);
  setInterval(render, 500);
  render();
})();
