(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  const root = '/assets/data/';
  let config, snapshot, busy = false, fallback = false, lastError = false, selectedPipeline = '';
  function el(tag, cls, text) { const n=document.createElement(tag); if(cls)n.className=cls; if(text!==undefined)n.textContent=text; return n; }
  const label = s => ({running:'Running',complete:'Complete',queued:'Queued',failed:'Failed',interrupted:'Interrupted',unknown:'Unknown'}[s] || 'Unknown');
  function badge(s) { return el('span','ml-badge '+s,label(s)); }
  function freshness() {
    if(!snapshot)return;
    const age=(Date.now()-Date.parse(snapshot.generated_at))/1000;
    const stale=!Number.isFinite(age)||age>Math.max(600,3*snapshot.refresh_seconds);
    $('ml-updated').textContent='Updated '+new Date(snapshot.generated_at).toLocaleString();
    $('ml-connection').textContent=lastError?'Connection interrupted':fallback?'Saved snapshot':stale?'Updates delayed':'● Feed connected';
    const note=fallback?'Showing the snapshot shipped with this page. The live feed is unavailable.':lastError?'Could not refresh. Keeping the last received snapshot.':stale?'The publisher has not reported recently. Running states below may be out of date.':'';
    $('ml-notice').hidden=!note; $('ml-notice').textContent=note;
  }
  function render() {
    const focused = document.activeElement?.closest('#ml-pipeline-list button')?.dataset.pipeline;
    if(!snapshot.pipelines.some(p=>p.id===selectedPipeline))selectedPipeline='';
    const list=$('ml-pipeline-list');list.replaceChildren();
    $('ml-pipeline-count').textContent=snapshot.pipelines.length;
    const choices=[{id:'',label:'All pipelines',runs:snapshot.pipelines.flatMap(p=>p.runs)},...snapshot.pipelines];
    for(const choice of choices){
      const button=el('button','ml-pipeline-option');button.type='button';button.dataset.pipeline=choice.id;
      button.setAttribute('aria-pressed',String(choice.id===selectedPipeline));
      const name=el('span','ml-pipeline-name',choice.label);
      const meta=el('span','ml-pipeline-meta',choice.id ? `${label(choice.status)} · ${choice.runs.length} runs` : `${snapshot.pipelines.length} pipelines · ${choice.runs.length} runs`);
      button.append(name,meta);list.append(button);
      if(focused===choice.id)button.focus({preventScroll:true});
    }
    const pipelines=snapshot.pipelines.filter(p=>!selectedPipeline||p.id===selectedPipeline);
    const runs=pipelines.flatMap(p=>p.runs), stats=el('div','ml-stats');
    for(const [value,name] of [[pipelines.length,'Tracked pipelines'],[runs.filter(r=>r.status==='running').length,'Runs in progress'],[`${runs.filter(r=>r.status==='complete').length} / ${runs.length}`,'Runs complete']]){
      const stat=el('div','ml-stat');stat.append(el('strong','',value),el('span','',name));stats.append(stat);
    }
    $('ml-summary').replaceChildren(stats);$('ml-pipelines').replaceChildren();
    if(!pipelines.length)$('ml-pipelines').append(el('p','ml-empty','No pipelines configured yet.'));
    for(const p of pipelines){
      const panel=el('article','ml-panel'),head=el('div','ml-panel-head'),title=el('div');
      title.append(el('h2','',p.label),el('p','',p.description));head.append(title,badge(p.status));panel.append(head);
      for(const r of p.runs){
        const row=el('div','ml-run'),identity=el('div');identity.append(el('div','ml-run-title',r.label),badge(r.status));
        const middle=el('div');middle.append(el('div','ml-run-stage',r.stage));
        const progress=el('progress');progress.max=Math.max(1,r.total);progress.value=r.completed;progress.setAttribute('aria-label',`${r.label}: ${r.completed} of ${r.total} ${r.unit}`);middle.append(progress);
        const metrics=el('div','ml-metrics');
        for(const [name,value] of Object.entries(r.metrics||{})){const metric=el('span','ml-metric',name);metric.append(el('strong','',Number(value).toFixed(2)));metrics.append(metric);}
        middle.append(metrics);
        const count=el('div','ml-count',`${r.completed} / ${r.total}`);count.append(el('small','',r.unit));row.append(identity,middle,count);panel.append(row);
      }
      $('ml-pipelines').append(panel);
    }
    freshness();
  }
  async function json(url) { const response=await fetch(url,{cache:'no-store',signal:AbortSignal.timeout(15000)});if(!response.ok)throw Error(response.status);return response.json(); }
  async function refresh() {
    if(busy)return;busy=true;$('ml-refresh').disabled=true;
    try{
      config=config||await json(root+'ml-tracking-config.json');
      let data;
      try {data=await json(config.feed_url+'?t='+Math.floor(Date.now()/60000));fallback=false;}
      catch(e){if(snapshot)throw e;data=await json(root+'ml-status.json');fallback=true;}
      if(data.schema_version!==1||!Array.isArray(data.pipelines))throw Error('Unsupported feed');
      snapshot=data;lastError=false;render();
    }catch(e){lastError=true;if(snapshot)freshness();else{$('ml-connection').textContent='Feed unavailable';$('ml-pipelines').replaceChildren(el('p','ml-empty','Unable to load progress. Try refreshing shortly.'));}}
    finally{busy=false;$('ml-refresh').disabled=false;}
  }
  const mobile=window.matchMedia('(max-width: 640px)');
  let menuOpen=false;
  function setMenu(open,restoreFocus=true){
    menuOpen=open&&mobile.matches;
    $('main').classList.toggle('ml-menu-is-open',menuOpen);
    $('ml-menu-open').setAttribute('aria-expanded',String(menuOpen));
    document.body.classList.toggle('ml-drawer-open',menuOpen);
    document.querySelector('.ml-content').inert=menuOpen;
    document.querySelectorAll('.masthead,.page__footer').forEach(node=>{node.inert=menuOpen;});
    if(menuOpen)$('ml-menu-close').focus();
    else if(restoreFocus&&mobile.matches)$('ml-menu-open').focus();
  }
  $('ml-menu-open').addEventListener('click',()=>setMenu(true));
  $('ml-menu-close').addEventListener('click',()=>setMenu(false));
  $('ml-menu-backdrop').addEventListener('click',()=>setMenu(false));
  mobile.addEventListener('change',()=>setMenu(false,false));
  document.addEventListener('keydown',event=>{
    if(!menuOpen)return;
    if(event.key==='Escape'){event.preventDefault();setMenu(false);}
    if(event.key==='Tab'){
      const buttons=[...$('ml-sidebar').querySelectorAll('button')];
      const first=buttons[0],last=buttons[buttons.length-1];
      if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus();}
      else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}
    }
  });
  $('ml-refresh').addEventListener('click',refresh);
  $('ml-pipeline-list').addEventListener('click',event=>{
    const button=event.target.closest('button[data-pipeline]');
    if(button&&snapshot){selectedPipeline=button.dataset.pipeline;render();if(menuOpen)setMenu(false);}
  });
  refresh();setInterval(refresh,120000);setInterval(freshness,30000);
})();
