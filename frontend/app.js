const $ = id => document.getElementById(id);
let caseRows=[], active=null, timer=null, snapshot=null;
const sessionId=sessionStorage.getItem('diagnosis-session')||crypto.randomUUID();
sessionStorage.setItem('diagnosis-session',sessionId);
async function api(path, options={}){
  const response=await fetch('/api/'+path,{...options,headers:{'Content-Type':'application/json','x-api-key':$('key').value,...options.headers}});
  const body=await response.json();
  if(!response.ok) throw new Error(body.detail||body.error||response.status);
  return body;
}
function text(tag,value,cls){const el=document.createElement(tag);el.textContent=value;if(cls)el.className=cls;return el;}
function details(title,value){const box=document.createElement('details');box.append(text('summary',title),text('pre',JSON.stringify(value,null,2)));return box;}
async function loadCases(){
  caseRows=await api('cases');$('case').replaceChildren();
  caseRows.forEach(c=>{const o=document.createElement('option');o.value=c.id;o.textContent=c.id+' · '+c.description;$('case').append(o);});
  choose();
}
function choose(){const c=caseRows.find(c=>c.id===$('case').value);if(c){$('question').value=c.description;$('caseNote').textContent=c.synthetic?'合成演示数据 · 不代表真实硬件测量':'导入数据 · 请核对测量条件';}}
$('case').onchange=choose;
async function history(){
  const rows=(await api('tasks')).filter(r=>r.payload.case_id);$('history').replaceChildren();
  if(!rows.length)$('history').append(text('p','暂无任务','muted'));
  rows.forEach(r=>{const b=text('button',r.payload.question.slice(0,28)+' · '+r.status);b.onclick=()=>watch(r.id);$('history').append(b);});
}
async function watch(id){
  active=id;clearTimeout(timer);
  try{
    const r=await api('tasks/'+id);if(active!==id)return;snapshot=r;
    $('taskId').textContent='任务 '+id;$('status').textContent=r.status;
    $('trace').replaceChildren();
    (r.events||[]).forEach(e=>$('trace').append(details(e.role+' / '+e.action+(e.tool?' · '+e.tool:''),e)));
    const result=r.result||{};const d=result.diagnosis;
    $('report').replaceChildren();
    if(d){
      (result.quality_issues||[]).forEach(issue=>$('report').append(text('p','需人工核对：'+issue.message+(issue.quote?' 原句：'+issue.quote:''),'issue')));
      $('report').append(text('p',d.conclusion,'reportText'));
      [['建议',d.recommendations],['验证步骤',d.verification]].forEach(([title,items])=>{ $('report').append(text('h3',title));const ul=document.createElement('ul');(items||[]).forEach(i=>ul.append(text('li',i)));$('report').append(ul);});
      $('report').append(text('p',d.uncertainty,'issue'));
      const audit=(r.events||[]).filter(e=>e.action==='grounding_audit').at(-1);
      if(audit){
        $('report').append(text('h3','逐条证据核对'),text('p','模型辅助判断，不代表结论已被证明；无结果的片段需要人工核对。','muted'));
        const table=document.createElement('table');const head=document.createElement('tr');
        ['报告片段','核对结果','证据 / 原因'].forEach(v=>head.append(text('th',v)));table.append(head);
        (audit.fragments||[]).forEach(fragment=>{
          const judgment=(audit.judgments||[]).find(j=>j.id===fragment.id);const row=document.createElement('tr');
          const label=judgment?({supported:'有直接支持',hypothesis:'假设 / 待验证',unsupported:'支持不足'}[judgment.verdict]):'未完成核对';
          [fragment.text,label,judgment?(judgment.evidence_ids.join(', ')+' '+judgment.reason):'需人工核对'].forEach(v=>row.append(text('td',v)));table.append(row);
        });$('report').append(table);
      }
      const usage=result.usage||[];const cost=usage.reduce((s,u)=>s+u.estimated_cny,0);
      $('report').append(text('span','耗时 '+(result.duration_ms/1000).toFixed(1)+' 秒','stat'),text('span','模型估算费用 ¥'+cost.toFixed(4),'stat'));
    }else $('report').append(text('p',result.error||'正在分析，已收集证据会保留。','muted'));
    $('resume').hidden=r.status!=='needs_attention';$('download').hidden=!d;
    $('evidence').replaceChildren();
    const evidence={...(result.evidence||{})};
    (r.events||[]).forEach(e=>Object.assign(evidence,e.evidence||{}));
    const metric=Object.values(evidence).find(e=>e.baseline&&e.current);
    if(metric){const table=document.createElement('table');const head=document.createElement('tr');['指标（原单位）','基线','当前'].forEach(v=>head.append(text('th',v)));table.append(head);
      Object.entries(metric.baseline.metrics).forEach(([key,value])=>{const row=document.createElement('tr');[key,value??'未测量',metric.current.metrics[key]??'未测量'].forEach(v=>row.append(text('td',v)));table.append(row);});$('evidence').append(table);}
    Object.entries(evidence).forEach(([key,value])=>$('evidence').append(details(key,value)));
    if(['pending','running'].includes(r.status))timer=setTimeout(()=>watch(id),1500);
    else await history();
  }catch(e){$('notice').textContent=e.message;}
}
$('submit').onclick=async()=>{
  $('submit').disabled=true;$('notice').textContent='';
  try{
    const r=await api('tasks',{method:'POST',headers:{'idempotency-key':crypto.randomUUID()},body:JSON.stringify({
      question:$('question').value,case_id:$('case').value,session_id:sessionId,mode:$('mode').value,rag:$('rag').checked,reviewer:$('reviewer').checked})});
    await history();await watch(r.id);
  }catch(e){$('notice').textContent=e.message;}finally{$('submit').disabled=false;}
};
$('resume').onclick=async()=>{try{await api('tasks/'+active+'/resume',{method:'POST'});await watch(active);}catch(e){$('notice').textContent=e.message;}};
$('download').onclick=()=>{const a=document.createElement('a');const url=URL.createObjectURL(new Blob([JSON.stringify(snapshot.result,null,2)],{type:'application/json'}));a.href=url;a.download='diagnosis-'+active+'.json';a.click();URL.revokeObjectURL(url);};
$('import').onclick=async()=>{try{const file=$('upload').files[0];if(!file)throw new Error('请选择 JSON 文件');if(file.size>1000000)throw new Error('文件超过 1 MB');await api('cases',{method:'POST',body:await file.text()});await loadCases();$('notice').textContent='案例已导入';}catch(e){$('notice').textContent=e.message;}};
$('refresh').onclick=()=>history().catch(e=>$('notice').textContent=e.message);
$('key').onchange=()=>init();
async function init(){try{await loadCases();await history();const rows=await api('evaluation');$('evaluation').replaceChildren();rows.forEach(r=>$('evaluation').append(details(r.run,r.summary||r.manifest)));}catch(e){$('notice').textContent=e.message;}}
init();
