(() => {
  const workspace = document.querySelector('[data-workspace-view]');
  if (!workspace) return;

  const home = document.querySelector('[data-home-view]');
  const homeHeading = document.querySelector('[data-home-heading]');
  const workspaceHeading = document.querySelector('[data-workspace-heading]');
  const back = document.querySelector('[data-back-button]');

  const updateView = () => {
    const inWorkspace = window.location.hash === '#workspace';
    document.body.classList.toggle('workspace-open', inWorkspace);
    home.hidden = inWorkspace;
    homeHeading.hidden = inWorkspace;
    workspaceHeading.hidden = !inWorkspace;
    back.disabled = !inWorkspace;
    back.title = inWorkspace ? 'Back to Home' : 'You are on the home page';
    back.setAttribute('aria-label', inWorkspace ? 'Back to Home' : 'Home');
    document.title = inWorkspace ? 'Workspace · Dayora' : 'Home · Dayora';
    document.querySelectorAll('nav [data-workspace-link], nav [data-home-link]').forEach((link) => {
      const active = link.hasAttribute('data-workspace-link') ? inWorkspace : !inWorkspace;
      link.classList.toggle('active', active);
      if (active) link.setAttribute('aria-current', 'page');
      else link.removeAttribute('aria-current');
    });
    if (!inWorkspace) workspace.querySelectorAll('dialog[open]').forEach((dialog) => dialog.close());
  };

  back.addEventListener('click', (event) => {
    if (window.location.hash !== '#workspace') return;
    event.stopImmediatePropagation();
    window.location.hash = '';
  }, true);

  // Fragments stay in the browser; existing POST routes and redirects are unchanged.
  workspace.addEventListener('submit', (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement) || form.method.toLowerCase() !== 'post') return;
    const destination = new URL(form.action, window.location.href);
    if (destination.origin !== window.location.origin) return;
    destination.hash = 'workspace';
    form.action = destination.href;
  }, true);

  document.querySelectorAll('[data-home-date]').forEach((element) => {
    element.textContent = new Intl.DateTimeFormat(undefined, {weekday: 'short', month: 'short', day: 'numeric'}).format(new Date());
  });
  window.addEventListener('hashchange', () => {
    updateView();
    window.scrollTo({top: 0, behavior: 'auto'});
    const heading = document.querySelector('.topbar h1');
    heading.setAttribute('tabindex', '-1');
    heading.focus({preventScroll: true});
  });
  window.addEventListener('pageshow', updateView);
  updateView();
})();
