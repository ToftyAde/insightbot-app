/* InsightBot - UI helpers (theme toggle, minor UX) */
(() => {
  const STORAGE_KEY = 'ib-theme';         // 'auto' | 'dim' | 'dark'
  const BTN_ID = 'themeToggle';

  const $html = document.documentElement;
  const $btn  = document.getElementById(BTN_ID);

  /** Apply a theme mode to <html> and update button label */
  function applyTheme(mode) {
    if (mode === 'auto') {
      // Auto: let CSS @media (prefers-color-scheme) decide
      $html.removeAttribute('data-theme');
    } else {
      // Explicit overrides via data-theme
      $html.setAttribute('data-theme', mode);
    }
    if ($btn) {
      const label = mode === 'auto' ? 'Auto' : (mode[0].toUpperCase() + mode.slice(1));
      $btn.textContent = `Theme: ${label}`;
      $btn.setAttribute('aria-pressed', mode !== 'auto'); // pressed when not auto
      $btn.title = 'Click to change theme (Auto → Dim → Dark). Shortcut: T';
    }
  }

  /** Determine next mode in cycle */
  function nextMode(mode) {
    return ({ auto: 'dim', dim: 'dark', dark: 'auto' })[mode] || 'auto';
  }

  /** Init: read stored mode or default to 'auto' */
  let mode = localStorage.getItem(STORAGE_KEY) || 'auto';
  applyTheme(mode);

  // Click to toggle
  if ($btn) {
    $btn.addEventListener('click', () => {
      mode = nextMode(mode);
      localStorage.setItem(STORAGE_KEY, mode);
      applyTheme(mode);
    });
  }

  // Keyboard shortcut: press "t" to toggle theme
  window.addEventListener('keydown', (e) => {
    // ignore if typing in an input/textarea/select or with modifiers
    const tag = (e.target && e.target.tagName) ? e.target.tagName.toLowerCase() : '';
    if (e.ctrlKey || e.metaKey || e.altKey || e.shiftKey) return;
    if (tag === 'input' || tag === 'textarea' || tag === 'select' || e.isComposing) return;
    if (e.key.toLowerCase() === 't') {
      mode = nextMode(mode);
      localStorage.setItem(STORAGE_KEY, mode);
      applyTheme(mode);
    }
  });

  // If in 'auto', reflect system changes live (label stays "Auto")
  const mql = window.matchMedia('(prefers-color-scheme: dark)');
  if (mql && mql.addEventListener) {
    mql.addEventListener('change', () => {
      if ((localStorage.getItem(STORAGE_KEY) || 'auto') === 'auto') {
        applyTheme('auto'); // no attribute; CSS handles the switch
      }
    });
  }
})();
