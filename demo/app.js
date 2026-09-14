const byId=id=>document.getElementById(id);
const element=(tag,value)=>{const el=document.createElement(tag);el.textContent=value;return el;};
function details(title,data){const box=document.createElement('details');box.append(element('summary',title),element('pre',JSON.stringify(data,null,2)));return box;}
let records;
function show(){const item=records.cases[Number(byId('case').value)];const r=item.result;const d=r.diagnosis;
  byId('kind').textContent=item.kind;byId('report').replaceChildren();
  byId('report').append(element('p',d.conclusion));
  for(const [label,values] of [['建议',d.recommendations],['复测步骤',d.verification]]){byId('report').append(element('h3',label));const list=document.createElement('ul');values.forEach(v=>list.append(element('li',v)));byId('report').append(list);}
  byId('report').append(element('p','不确定性：'+d.uncertainty));
  const audit=(r.events||[]).filter(e=>e.action==='grounding_audit').at(-1);
  if(audit){
    byId('report').append(element('h3','逐条证据核对'),element('p','模型辅助判断，不是正确性证明；未完成核对的片段须人工检查。'));
    const table=document.createElement('table');const head=document.createElement('tr');
    ['报告片段','核对标签','证据 / 理由'].forEach(v=>head.append(element('th',v)));table.append(head);
    (audit.fragments||[]).forEach(f=>{const j=(audit.judgments||[]).find(j=>j.id===f.id);const row=document.createElement('tr');
      [f.text,j?({supported:'有直接支持',hypothesis:'假设 / 待验证',unsupported:'支持不足'}[j.verdict]):'未完成核对',j?(j.evidence_ids.join(', ')+' '+j.reason):'需人工核对'].forEach(v=>row.append(element('td',v)));table.append(row);
    });byId('report').append(table);
  }
  byId('trace').replaceChildren();(r.events||[]).forEach(e=>byId('trace').append(details(e.role+' / '+e.action+(e.tool?' · '+e.tool:''),{tool:e.tool,arguments:e.arguments,duration_ms:e.duration_ms,issues:e.issues,judgments:e.judgments,output:e.action==='model'?'模型消息见仓库中的完整记录':e.output})));
  byId('evidence').replaceChildren();Object.entries(r.evidence||{}).forEach(([id,e])=>byId('evidence').append(details(id,e)));
}
fetch('records.json').then(r=>{if(!r.ok)throw Error('结果加载失败');return r.json();}).then(data=>{
  records=data;data.cases.forEach((c,i)=>{const o=element('option',c.title);o.value=i;byId('case').append(o);});
  byId('case').onchange=show;byId('retest').append(details('实验条件、响应码与限制',data.retest));
  const summary=data.synthetic.manifest.summary;
  byId('synthetic').append(element('p',`8类抽样：类别命中 ${summary.category_hits}/${summary.cases}，通过证据门禁 ${summary.completed}/${summary.cases}，估算费用 ${summary.estimated_cny} 元。`));
  const table=document.createElement('table'),head=document.createElement('tr');
  ['场景','期望类别','输出类别','类别','门禁'].forEach(v=>head.append(element('th',v)));table.append(head);
  data.synthetic.rows.forEach(item=>{const row=document.createElement('tr');
    [item.scenario,item.expected_category,item.predicted_category,item.category_hit==='True'?'命中':'未命中',item.completed==='True'?'通过':'需关注'].forEach(v=>row.append(element('td',v)));table.append(row);
  });byId('synthetic').append(table);show();
}).catch(e=>byId('report').textContent=e.message);
