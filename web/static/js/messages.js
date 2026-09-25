(() => {
  const body = document.querySelector('[data-message-body]');
  const count = document.querySelector('[data-message-count]');
  if (body && count) {
    const updateCount = () => { count.textContent = `${body.value.length.toLocaleString()} / 2,000 characters`; };
    body.addEventListener('input', updateCount);
    updateCount();
  }
  const suggestions = {
    'Task clarification': 'A question about my assigned task',
    'Leave & schedule': 'A question about my work schedule',
    'Share an idea': 'An idea for our team'
  };
  document.querySelectorAll('[data-message-starter]').forEach(button => {
    button.addEventListener('click', () => {
      document.querySelector('#message-topic').value = button.dataset.messageStarter;
      const subject = document.querySelector('#message-subject');
      if (!subject.value || Object.values(suggestions).includes(subject.value)) {
        subject.value = suggestions[button.dataset.messageStarter];
      }
      body.focus();
    });
  });
  document.querySelectorAll('[data-message-time]').forEach(element => {
    const date = new Date(element.dateTime);
    if (!Number.isNaN(date.getTime())) {
      element.textContent = new Intl.DateTimeFormat(undefined, {dateStyle: 'medium', timeStyle: 'short'}).format(date);
    }
  });
})();
