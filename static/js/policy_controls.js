/* Policy precedence is entered by HR; the assistant never infers company authority. */
function policyControls(doc) {
  const id = `policy-${doc.id}`;
  return `<details><summary>Policy precedence</summary><form data-policy-document="${doc.id}">
    <label for="${id}-key">Approved policy key</label><input class="field" id="${id}-key" name="policy_key" maxlength="100" value="${esc(doc.policy_key || '')}">
    <label for="${id}-priority">Priority</label><input class="field" id="${id}-priority" name="priority" type="number" min="-100" max="100" required value="${doc.priority}">
    <label for="${id}-from">Effective from</label><input class="field" id="${id}-from" name="effective_from" type="date" value="${esc(doc.effective_from || '')}">
    <label for="${id}-until">Effective until</label><input class="field" id="${id}-until" name="effective_until" type="date" value="${esc(doc.effective_until || '')}">
    <label><input name="known_conflict" type="checkbox" ${doc.known_conflict ? 'checked' : ''}> Known source conflict</label>
    <p>Changes require a new review and approval. Equal policy precedence causes fallback; flagged approved sources are withheld.</p>
    <button class="small-btn">Save as draft</button></form></details>`;
}
function wirePolicyControls(container, documents) {
  container.querySelectorAll('[data-policy-document]').forEach(form => form.onsubmit = async event => {
    event.preventDefault(); const button = form.querySelector('button'); button.disabled = true;
    try {
      const doc = documents.find(d => d.id === Number(form.dataset.policyDocument));
      const fields = form.elements;
      await api(`/admin/knowledge/documents/${doc.id}`,{method:'PATCH',body:JSON.stringify({
        expected_revision:doc.revision, policy_key:fields.policy_key.value.trim() || null,
        priority:Number(fields.priority.value), effective_from:fields.effective_from.value || null,
        effective_until:fields.effective_until.value || null, known_conflict:fields.known_conflict.checked,
      })});
      await loadAdminPage();
    } catch(error) { toast(error.message); }
    finally { button.disabled = false; }
  });
}
