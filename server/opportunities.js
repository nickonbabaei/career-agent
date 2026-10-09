function renderOpportunities(r, edits, root, runId) {
  const head=el('section',undefined,root);
  el('h2','Your opportunities',head);
  el('p',r.phase+' · '+r.status.replaceAll('_',' '),head);
  el('p',`${r.found??0} found · ${r.assessed??0} assessed · ${r.unassessed??0} unassessed. Ranking covers assessed matches. Research runs in batches of three. Nothing sent.`,head);
  const ranked=new Map((r.ranking||[]).map((x,i)=>[x.id,i+1]));
  const jobs=[...(r.jobs||[])].sort((a,b)=>(ranked.get(a.id)||999)-(ranked.get(b.id)||999));
  const groups={'Best matches · contact found':[], 'Best matches · apply directly':[], 'More matching jobs · not researched':[], 'Needs attention':[], 'Flagged opportunities':[], 'Other assessed or pending jobs':[]};
  for(const j of jobs){const o=j.outreach;let group;
    if(o?.verification?.concern==='flagged')group='Flagged opportunities';
    else if(o && ['failed','quota_limited'].includes(o.status))group='Needs attention';
    else if(o?.research?.contact)group='Best matches · contact found';
    else if(o)group='Best matches · apply directly';
    else if(j.decision?.is_relevant)group='More matching jobs · not researched';
    else group='Other assessed or pending jobs';
    groups[group].push(j);
  }
  if((r.ranking||[]).some(x=>!jobs.find(j=>j.id===x.id)?.outreach)){
    const next=el('button','Research the next three',head);next.disabled=active||r.status==='running';next.onclick=()=>start('next_batch');
  }
  const manual=el('button','Open search results / manual controls',head);manual.className='secondary';manual.onclick=()=>{chosen=r.source_results.split('/').slice(-2,-1)[0];show().catch(e=>notify(e.message,true))};
  for(const [name,items] of Object.entries(groups)){
    if(!items.length)continue;
    const section=el('details',undefined,root);section.open=!name.startsWith('Other');
    el('summary',`${name} (${items.length})`,section);
    for(const j of items){const o=j.outreach;const card=el('section',undefined,section);
      el('h3',`${ranked.has(j.id)?'#'+ranked.get(j.id)+' · ':''}${j.job.title} · ${j.job.company}`,card);
      el('p',j.job.location,card);el('p',j.decision?.reason||'Not assessed yet.',card);
      if(o?.verification?.concern==='flagged'){el('p',o.verification.reason,card).className='error';link(o.verification.concern_url,card);continue;}
      link(j.job.source_url,card);
      const contact=o?.research?.contact;
      if(contact){el('h3',contact.name+' · '+contact.title,card);el('p',contact.reason,card);const evidence=el('details',undefined,card);el('summary','Contact sources & uncertainties',evidence);for(const e of contact.evidence||[]){link(e.url,evidence);el('blockquote',e.excerpt,evidence)}for(const u of contact.uncertainties||[])el('p',u,evidence);}
      else el('p',o?(['failed','quota_limited'].includes(o.status)?'Research interrupted. Use manual controls to retry this job.':'No supported contact found in this search. You can still apply directly.'):'Contact research has not run for this job.',card);
      for(const e of o?.errors||[])el('p',e.message||JSON.stringify(e),card).className='error';
      if(o?.draft){const value=edits[String(j.id)]||o.draft;const sl=el('label','Subject',card);const subject=el('input',undefined,sl);subject.value=value.subject;const bl=el('label','Message — review before using',card);const body=el('textarea',undefined,bl);body.rows=10;body.value=value.body;
        const save=el('button','Save edits',card);save.onclick=async()=>{try{await api('edit',{run:runId,rank:j.id,subject:subject.value,body:body.value});notify('Edits saved. Nothing sent.')}catch(e){notify(e.message,true)}};
        const copy=el('button','Copy message',card);copy.onclick=async()=>{try{await navigator.clipboard.writeText(body.value);notify('Copied. Nothing sent.')}catch(e){notify('Select the message and copy manually.',true)}};
      }
    }
  }
  for(const e of r.errors||[])el('p',e.message,head).className='error';
}
