/* Native focus containment for every modal, including nested dialogs. */
(() => {
  const dialogs = [...document.querySelectorAll('.modal-backdrop')];
  const stack = [];
  const openers = new WeakMap();
  const previousInert = new Map();
  let trigger = document.activeElement;
  document.addEventListener('click', event => { trigger = event.target.closest('button, a, input, select') || document.activeElement; }, true);
  const focusables = modal => [...modal.querySelectorAll('button, input, select, textarea, a[href], [tabindex]')]
    .filter(el => !el.disabled && el.tabIndex >= 0 && !el.hidden && el.getClientRects().length);
  const top = () => stack[stack.length - 1];
  const focus = modal => {
    if (modal && !modal.contains(document.activeElement)) {
      modal.tabIndex = -1;
      (focusables(modal)[0] || modal).focus();
    }
  };
  const sync = () => {
    let restore;
    for (const modal of dialogs) {
      const index = stack.indexOf(modal);
      if (modal.classList.contains('open') && index < 0) {
        openers.set(modal, modal.contains(document.activeElement) ? trigger : document.activeElement);
        stack.push(modal);
      } else if (!modal.classList.contains('open') && index >= 0) {
        stack.splice(index, 1);
        restore = openers.get(modal);
      }
    }
    for (const [el, value] of previousInert) el.inert = value;
    previousInert.clear();
    const modal = top();
    if (modal) {
      for (let branch = modal; branch.parentElement && branch !== document.body; branch = branch.parentElement) {
        for (const sibling of branch.parentElement.children) {
          if (sibling !== branch) { previousInert.set(sibling, sibling.inert); sibling.inert = true; }
        }
      }
      if (restore && modal.contains(restore)) restore.focus();
      else focus(modal);
    } else if (restore?.isConnected) restore.focus();
  };
  const observer = new MutationObserver(sync);
  dialogs.forEach(modal => observer.observe(modal, {attributes:true, attributeFilter:['class']}));
  document.addEventListener('keydown', event => {
    const modal = top();
    if (!modal) return;
    if (event.key === 'Escape') {
      event.preventDefault(); event.stopImmediatePropagation(); modal.classList.remove('open');
    } else if (event.key === 'Tab') {
      const nodes = focusables(modal), first = nodes[0], last = nodes[nodes.length - 1];
      if (!first || !modal.contains(document.activeElement) || (event.shiftKey && document.activeElement === first) || (!event.shiftKey && document.activeElement === last)) {
        event.preventDefault(); (event.shiftKey ? last : first)?.focus();
      }
    }
  }, true);
  document.addEventListener('focusin', () => focus(top()));
})();
