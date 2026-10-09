function renderContacts(report, saved, root, runId) {
  recipientChoices = saved;
  const head = el('section', undefined, root);
  el('div', 'STEP 3 · REVIEW CONTACTS', head).className = 'eyebrow';
  el('h2', 'Who would you like to reach out to?', head);
  el('p', 'Review sources, choose a recipient for each opportunity, or skip it. No drafts are created until you continue.', head);
  el('small', 'Research status: ' + report.status.replaceAll('_', ' '), head);
  const next = el('button', 'Create drafts for chosen recipients', head);
  next.disabled = active || report.status === 'running';
  next.onclick = () => start('draft');
  const back = el('button', 'Back to job selection', head);
  back.className = 'secondary';
  back.onclick = () => {
    const source = (report.source_results || '').split('/').slice(-2, -1)[0];
    if (source) { chosen = source; $('runs').value = source; show().catch(e => notify(e.message, true)); }
  };
  function persist() {
    const snapshot = JSON.parse(JSON.stringify(recipientChoices));
    selectionQueue = selectionQueue.catch(() => {}).then(() => api('recipients', {run:runId, choices:snapshot}));
    selectionQueue.catch(e => notify('Could not save recipient choices: ' + e.message, true));
  }
  for (const entry of report.jobs || []) {
    const card = el('section', undefined, root);
    el('h3', entry.title + ' · ' + entry.company, card);
    const check = entry.verification;
    const flagged = check?.concern === 'flagged';
    if (flagged) {
      const panel = el('section', undefined, card);
      el('h3', 'Company or listing concern — outreach stopped', panel).className = 'error';
      el('p', check.reason, panel);
      link(check.concern_url, panel);
      el('blockquote', check.concern_quote, panel);
      el('p', 'Contact lookup and drafting are disabled for this opportunity.', panel);
      recipientChoices[String(entry.rank)] = {mode:'skip'};
      continue;
    }
    const application = check?.listing === 'confirmed' ? check.listing_url : entry.job?.source_url;
    if (application) {
      const applicationBox = el('p', undefined, card);
      link(application, applicationBox);
      const anchor = applicationBox.querySelector('a');
      if (anchor) anchor.textContent = check?.listing === 'confirmed' ? 'Open listing / apply ↗' : 'Open listing / apply ↗';
    }
    const contact = entry.research?.contact;
    if (contact) {
      el('h3', contact.name, card);
      el('p', contact.title + ' · ' + contact.organization, card);
      el('p', contact.reason, card);
      link(contact.public_url, card);
      const sources = el('details', undefined, card);
      el('summary', 'Review evidence & uncertainties', sources);
      for (const item of contact.evidence || []) { link(item.url, sources); el('blockquote', item.excerpt, sources); }
      for (const item of contact.uncertainties || []) el('p', item, sources);
    } else {
      el('p', entry.status === 'failed' || entry.status === 'quota_limited' ? 'Research could not complete. Open the application link, supply your own contact, or skip outreach.' : 'This search did not find a supported contact; that does not mean none exists. You can apply directly or supply a contact yourself.', card);
    }
    for (const error of entry.errors || []) el('p', error.message || JSON.stringify(error), card).className = 'error';
    const key = String(entry.rank);
    const choice = recipientChoices[key] || {mode:'', contact:{}, confirmed:false};
    if (choice.mode === 'generic') choice.mode = '';
    recipientChoices[key] = choice;
    const label = el('label', 'Recipient for this job', card);
    const select = el('select', undefined, label);
    for (const [value, text] of [['','Choose an option…'],['researched','Use researched contact'],['manual','Supply my own contact'],['skip','Skip outreach / apply directly']]) {
      const option = el('option', text, select); option.value = value;
      if (value === 'researched' && !contact) option.disabled = true;
    }
    select.value = choice.mode;
    select.disabled = active || report.status === 'running';
    const manual = el('div', undefined, card);
    manual.hidden = choice.mode !== 'manual';
    el('p', 'These details will be labelled user supplied, not independently verified.', manual);
    for (const [field, title] of [['name','Full name'],['title','Job title'],['organization','Organization']]) {
      const wrapper = el('label', title, manual);
      const input = el('input', undefined, wrapper);
      input.value = choice.contact?.[field] || '';
      input.maxLength = 200;
      input.onchange = () => { choice.contact ||= {}; choice.contact[field] = input.value; choice.confirmed = false; confirm.checked = false; persist(); };
    }
    const relationLabel = el('label', 'Relationship to the role', manual);
    const relationship = el('select', undefined, relationLabel);
    for (const [value,text] of [['','Choose…'],['employee','Employee'],['recruiter','Recruiter']]) { const option=el('option',text,relationship);option.value=value; }
    relationship.value = choice.contact?.relationship || '';
    relationship.onchange = () => { choice.contact ||= {}; choice.contact.relationship=relationship.value; choice.confirmed=false; confirm.checked=false; persist(); };
    const confirmation = el('label', undefined, manual);
    const confirm = el('input', undefined, confirmation); confirm.type='checkbox';confirm.style.width='auto';confirm.checked=choice.confirmed===true;
    confirmation.append(document.createTextNode(' I confirm these contact details.'));
    confirm.onchange=()=>{choice.confirmed=confirm.checked;persist();};
    select.onchange=()=>{choice.mode=select.value;manual.hidden=choice.mode!=='manual';persist();};
  }
}
