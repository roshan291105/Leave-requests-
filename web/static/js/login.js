(() => {
  const form = document.querySelector('.signin-form');
  const password = form.querySelector('[name=password]');
  const toggle = form.querySelector('[data-login-password]');
  const submit = form.querySelector('[type=submit]');
  const label = submit.querySelector('[data-submit-label]');
  toggle.addEventListener('click', () => {
    const reveal = password.type === 'password';
    password.type = reveal ? 'text' : 'password';
    toggle.textContent = reveal ? 'Hide' : 'Show';
    toggle.setAttribute('aria-label', reveal ? 'Hide password' : 'Show password');
    toggle.setAttribute('aria-pressed', String(reveal));
  });
  document.querySelectorAll('[data-demo-username]').forEach(button => {
    button.addEventListener('click', () => {
      form.querySelector('[name=username]').value = button.dataset.demoUsername;
      password.value = button.dataset.demoPassword;
      document.querySelector('[data-demo-status]').textContent = `${button.dataset.demoRole} demo details filled. Select Sign in to continue.`;
      submit.focus();
    });
  });
  form.addEventListener('submit', event => {
    if (submit.disabled) { event.preventDefault(); return; }
    if (!form.checkValidity()) return;
    submit.disabled = true;
    label.textContent = 'Signing in...';
    form.setAttribute('aria-busy', 'true');
  });
  window.addEventListener('pageshow', () => {
    submit.disabled = false;
    label.textContent = 'Sign in';
    form.removeAttribute('aria-busy');
  });
})();
