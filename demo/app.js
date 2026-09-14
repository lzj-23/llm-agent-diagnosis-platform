const byId=id=>document.getElementById(id);
const element=(tag,value)=>{const el=document.createElement(tag);el.textContent=value;return el;};
function details(title,data){const box=document.createElement('details');box.append(element('summary',title),element('pre',JSON.stringify(data,null,2)));return box;}
let records;
function show(){const item=records.cases[Number(byId('case').value)];const r=item.result;const d=r.diagnosis;
  byId('kind').textContent=item.kind;byId('report').replaceChildren();
  byId('report').append(element('p',d.conclusion));
  for(const [label,values] of [['建议',d.recommendations],['复测步骤',d.verification]]){byId('report').append(element('h3',label));const list=document.createElement('ul');values.forEach(v=>list.append(element('li',v)));byId('report').append(list);}
  byId('report').append(element('p','不确定性：'+d.uncertainty));
  byId('trace').replaceChildren();(r.events||[]).forEach(e=>byId('trace').append(details(e.role+' / '+e.action+(e.tool?' · '+e.tool:''),{tool:e.tool,arguments:e.arguments,duration_ms:e.duration_ms,output:e.action==='model'?'模型消息见仓库中的完整记录':e.output})));
  byId('evidence').replaceChildren();Object.entries(r.evidence||{}).forEach(([id,e])=>byId('evidence').append(details(id,e)));
}
fetch('records.json').then(r=>{if(!r.ok)throw Error('结果加载失败');return r.json();}).then(data=>{records=data;data.cases.forEach((c,i)=>{const o=element('option',c.title);o.value=i;byId('case').append(o);});byId('case').onchange=show;byId('retest').append(details('实验条件、响应码与限制',data.retest));show();}).catch(e=>byId('report').textContent=e.message);
