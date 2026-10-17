/* Explicit HR decisions; the server authorizes and audits every action. */
function renderIntegrationRecovery(queue, reviews, members) {
  const queueEl = document.getElementById('adminIntegrationQueue');
  queueEl.innerHTML = queue.length ? queue.map(q => `<p><code>${esc(q.request_code)}</code> · ${esc(q.status)} · <code>${esc(q.error_code)}</code> ${q.can_retry ? `<button class="small-btn" data-retry="${q.id}">Review recovery</button>` : '<span>Operator correction required</span>'}</p>`).join('') : '<p>No failed deliveries.</p>';
  const reviewEl = document.getElementById('adminIntegrationReviews');
  reviewEl.innerHTML = reviews.length ? reviews.map((r,i) => `<p><code>${esc(r.employee_code)}</code> · <code>${esc(r.reason)}</code> <button class="small-btn" data-resolve="${i}">Resolve mapping</button></p>`).join('') : '<p>No mapping issues.</p>';
  function open(command) {
    const form = document.getElementById('recoveryForm'); form.reset();
    const mapping = !!command.review;
    document.getElementById('recoveryTitle').textContent = mapping ? 'Resolve mapping' : 'Review recovery';
    document.getElementById('recoveryTarget').textContent = mapping ? command.review.employee_code : command.task.request_code;
    document.getElementById('recoveryWarning').textContent = mapping ? 'Verify the employee code and account. This changes the existing profile code; no account or role is created.' : 'The gateway is reconciled first. The original document key is preserved; validation failures and missing accepted jobs require investigation.';
    const select = document.getElementById('recoveryEmployee');
    select.innerHTML = '<option value="">Recheck current mapping</option>' + members.map(m => `<option value="${m.user_id}">${esc(m.full_name || m.name)} · ${esc(m.employee_code)}</option>`).join('');
    document.getElementById('recoveryEmployeeGroup').hidden = !mapping;
    form.onsubmit = async event => {
      event.preventDefault(); const button = document.getElementById('submitRecovery'); button.disabled = true;
      try {
        const reason = document.getElementById('recoveryReason').value.trim();
        const path = mapping ? `/admin/integrations/reviews/${encodeURIComponent(command.review.employee_code)}/resolve` : `/admin/integrations/queue/${command.task.id}/retry`;
        const body = mapping ? {reason, observed_at:command.review.observed_at, user_id:select.value ? Number(select.value) : null} : {reason, expected_retry_count:command.task.retry_count};
        await api(path,{method:'POST',body:JSON.stringify(body)});
        document.getElementById('recoveryModal').classList.remove('open');
        toast('Recovery action saved.'); await loadAdminPage();
      } catch (error) { toast(error.message); }
      finally { button.disabled = false; }
    };
    document.getElementById('recoveryModal').classList.add('open');
  }
  queueEl.querySelectorAll('[data-retry]').forEach(button => button.onclick = () => open({task:queue.find(q => q.id === Number(button.dataset.retry))}));
  reviewEl.querySelectorAll('[data-resolve]').forEach(button => button.onclick = () => open({review:reviews[Number(button.dataset.resolve)]}));
}
