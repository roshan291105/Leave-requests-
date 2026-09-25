document.querySelectorAll('.toast button').forEach((button) => {
  button.addEventListener('click', () => button.parentElement.remove());
});
setTimeout(() => document.querySelectorAll('.toast').forEach((item) => item.remove()), 4500);

const leaveModal = document.querySelector('#leave-modal');
document.querySelectorAll('[data-open-modal]').forEach((button) => {
  button.addEventListener('click', () => leaveModal?.showModal());
});

document.querySelectorAll('.modal-close').forEach((button) => {
  button.addEventListener('click', () => button.closest('dialog').close());
});
document.querySelectorAll('dialog').forEach((dialog) => {
  dialog.addEventListener('click', (event) => {
    if (event.target === dialog) dialog.close();
  });
});

document.querySelectorAll('[data-confirm]').forEach((button) => {
  button.addEventListener('click', (event) => {
    if (!window.confirm(button.dataset.confirm)) event.preventDefault();
  });
});

document.querySelector('[data-toggle-password]')?.addEventListener('click', (event) => {
  const input = document.querySelector('#password');
  input.type = input.type === 'password' ? 'text' : 'password';
  event.target.textContent = input.type === 'password' ? 'Show' : 'Hide';
});

const reviewModal = document.querySelector('#review-modal');
document.querySelectorAll('[data-review]').forEach((button) => {
  button.addEventListener('click', () => {
    const [id, name, type, days] = button.dataset.review.split('|');
    document.querySelector('#review-form').action = `/admin/leave/${id}/decide`;
    document.querySelector('#review-title').textContent = `${name}'s request`;
    document.querySelector('#review-detail').textContent = `${type} leave · ${days} day${days === '1' ? '' : 's'}`;
    reviewModal?.showModal();
  });
});

const start = document.querySelector('[name=start_date]');
const end = document.querySelector('[name=end_date]');
if (start && end) {
  const today = new Date().toISOString().split('T')[0];
  start.min = today;
  end.min = today;
  start.addEventListener('change', () => {
    end.min = start.value;
    if (end.value < start.value) end.value = start.value;
  });
}

document.querySelectorAll('form').forEach((form) => {
  form.addEventListener('submit', (event) => {
    if (event.defaultPrevented) return;
    if (form.dataset.submitting === 'true') {
      event.preventDefault();
      return;
    }
    if (!form.checkValidity()) return;
    form.dataset.submitting = 'true';
    form.classList.add('is-submitting');
    const submitter = event.submitter;
    if (submitter && !submitter.name) submitter.textContent = 'Working…';
  });
});

async function refreshNotificationBadge() {
  const badge = document.querySelector('#notification-badge');
  if (!badge) return;
  try {
    const response = await fetch('/api/notifications/unread', {headers: {'Accept': 'application/json'}});
    if (!response.ok) return;
    const data = await response.json();
    badge.textContent = data.count;
    badge.classList.toggle('badge-hidden', data.count === 0);
  } catch (_) {
    // A temporary network interruption should not affect the rest of the UI.
  }
}

refreshNotificationBadge();
setInterval(refreshNotificationBadge, 15000);
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) refreshNotificationBadge();
});

document.querySelectorAll('[data-reveal-password]').forEach((button) => {
  button.addEventListener('click', () => {
    const value = button.closest('.credential-box').querySelector('.password-value');
    const hidden = value.textContent.includes('•');
    value.textContent = hidden ? value.dataset.password : '•••••••••••';
    button.textContent = hidden ? 'Hide' : 'Show';
  });
});

document.querySelectorAll('[data-copy-credentials]').forEach((button) => {
  button.addEventListener('click', async () => {
    const credentials = `Login ID: ${button.dataset.username}\nPassword: ${button.dataset.password}`;
    try {
      await navigator.clipboard.writeText(credentials);
      const oldLabel = button.textContent;
      button.textContent = 'Copied!';
      setTimeout(() => { button.textContent = oldLabel; }, 1600);
    } catch (_) {
      window.prompt('Copy these credentials:', credentials);
    }
  });
});

const liveClock = document.querySelector('#live-clock');
if (liveClock) {
  const updateClock = () => {
    liveClock.textContent = new Intl.DateTimeFormat(undefined, {
      weekday: 'long', hour: 'numeric', minute: '2-digit', second: '2-digit'
    }).format(new Date());
  };
  updateClock();
  setInterval(updateClock, 1000);
}

function greetingForHour(hour) {
  if (hour >= 5 && hour < 12) return 'Good morning';
  if (hour >= 12 && hour < 17) return 'Good afternoon';
  if (hour >= 17 && hour < 21) return 'Good evening';
  return 'Good night';
}

function refreshTimeGreetings() {
  const greeting = greetingForHour(new Date().getHours());
  document.querySelectorAll('[data-time-greeting]').forEach((element) => {
    element.textContent = `${greeting}, ${element.dataset.name}.`;
  });
}

refreshTimeGreetings();
setInterval(refreshTimeGreetings, 60000);

const attendanceModal = document.querySelector('#attendance-modal');
const attendanceForm = document.querySelector('#attendance-form');
const attendanceStatus = document.querySelector('#attendance-status');
const attendanceCheckIn = document.querySelector('#attendance-check-in');
const attendanceCheckOut = document.querySelector('#attendance-check-out');

function updateAttendanceTimeFields() {
  if (!attendanceStatus) return;
  const isAbsent = attendanceStatus.value === 'ABSENT';
  attendanceCheckIn.disabled = isAbsent;
  attendanceCheckOut.disabled = isAbsent;
  if (isAbsent) {
    attendanceCheckIn.value = '';
    attendanceCheckOut.value = '';
  }
}

attendanceStatus?.addEventListener('change', updateAttendanceTimeFields);
document.querySelectorAll('[data-mark-attendance]').forEach((button) => {
  button.addEventListener('click', () => {
    attendanceForm.action = `/admin/attendance/${button.dataset.code}/mark`;
    document.querySelector('#attendance-employee').textContent = `${button.dataset.name} · ${button.dataset.code}`;
    attendanceStatus.value = button.dataset.status === 'ABSENT' ? 'ABSENT' : 'PRESENT';
    attendanceCheckIn.value = (button.dataset.checkIn || '').slice(0, 5);
    attendanceCheckOut.value = (button.dataset.checkOut || '').slice(0, 5);
    attendanceForm.dataset.submitting = 'false';
    attendanceForm.classList.remove('is-submitting');
    updateAttendanceTimeFields();
    attendanceModal?.showModal();
  });
});

document.querySelectorAll('[data-back-button]').forEach((button) => {
  button.addEventListener('click', () => {
    const fallback = new URL(button.dataset.fallback || '/dashboard', window.location.origin);
    if (window.location.pathname === fallback.pathname) return;
    let canReturn = false;
    try {
      const previous = new URL(document.referrer);
      canReturn = previous.origin === window.location.origin
        && previous.pathname !== '/'
        && previous.href !== window.location.href;
    } catch (_) {
      canReturn = false;
    }
    if (canReturn) window.history.back();
    else window.location.replace(fallback.href);
  });
});

document.querySelectorAll('[data-task-title-select]').forEach((select) => {
  const customField = select.form.querySelector('[data-task-custom-title]');
  const customInput = customField.querySelector('input');
  const updateTaskTitle = () => {
    const isCustom = select.value === '';
    customField.hidden = !isCustom;
    customInput.disabled = !isCustom;
    customInput.required = isCustom;
  };
  select.addEventListener('change', () => {
    updateTaskTitle();
    if (select.value === '') customInput.focus();
  });
  window.addEventListener('pageshow', updateTaskTitle);
  updateTaskTitle();
});

document.querySelectorAll('.schedule-row .switch input').forEach((checkbox) => {
  const row = checkbox.closest('.schedule-row');
  const label = checkbox.closest('.switch').querySelector('span');
  const timeInputs = row.querySelectorAll('input[type="time"]');
  const refreshScheduleRow = () => {
    label.textContent = checkbox.checked ? 'Working' : 'Day off';
    timeInputs.forEach((input) => { input.disabled = !checkbox.checked; });
  };
  checkbox.addEventListener('change', refreshScheduleRow);
  refreshScheduleRow();
});

document.querySelectorAll('[data-schedule-defaults]').forEach((button) => {
  button.addEventListener('click', () => {
    const form = button.form;
    form.querySelectorAll('[data-default-working]').forEach((row) => {
      const checkbox = row.querySelector('input[type="checkbox"]');
      checkbox.checked = row.dataset.defaultWorking === '1';
      row.querySelector('input[name^="start_"]').value = row.dataset.defaultStart;
      row.querySelector('input[name^="end_"]').value = row.dataset.defaultEnd;
      checkbox.dispatchEvent(new Event('change', { bubbles: true }));
    });
    form.querySelector('[data-schedule-status]').textContent =
      'Default days and times restored. Click Save work schedule to apply them.';
  });
});
