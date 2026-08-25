(function(){
'use strict';

const TROPHY_PLACES_V39=4;

function samePointsV39(a,b){return Math.abs(Number(a)-Number(b))<1e-9}
function rawMainStandingsV39(){
 const map=new Map(S.racers.map(r=>[r.id,{id:r.id,name:r.name,number:r.number,points:0,races:0,wins:0}]));
 S.heats.forEach(h=>(h.results||[]).forEach(x=>{const s=map.get(x.racerId);if(s){s.points+=Number(x.points)||0;s.races++;if(x.position===1)s.wins++}}));
 return Array.from(map.values()).sort((a,b)=>a.points-b.points||a.number-b.number);
}
function tieKeyV39(group){
 const ids=group.map(r=>String(r.id)).sort().join(',');
 const pts=group.length?Number(group[0].points).toFixed(6):'0';
 return `${ids}@${pts}`;
}
function mainTieGroupsV39(){
 const a=rawMainStandingsV39(),groups=[];
 for(let i=0;i<a.length;){
  let j=i+1;while(j<a.length&&samePointsV39(a[j].points,a[i].points))j++;
  if(j-i>1&&i<TROPHY_PLACES_V39){const racers=a.slice(i,j);groups.push({start:i,end:j-1,racers,key:tieKeyV39(racers)});}
  i=j;
 }
 return groups;
}
function resolvedTieV39(group){
 const t=S.tieBreaks&&S.tieBreaks[group.key];
 if(!t||!Array.isArray(t.order)||t.order.length!==group.racers.length)return null;
 const need=new Set(group.racers.map(r=>String(r.id))),got=new Set(t.order.map(String));
 if(need.size!==got.size||[...need].some(x=>!got.has(x)))return null;
 return t;
}
function finalStandingsV39(){
 const a=rawMainStandingsV39();
 for(let i=0;i<a.length;){
  let j=i+1;while(j<a.length&&samePointsV39(a[j].points,a[i].points))j++;
  if(j-i>1){const group={racers:a.slice(i,j),key:tieKeyV39(a.slice(i,j))},t=resolvedTieV39(group);if(t){const pos=new Map(t.order.map((id,k)=>[String(id),k]));a.splice(i,j-i,...a.slice(i,j).sort((x,y)=>pos.get(String(x.id))-pos.get(String(y.id))));}}
  i=j;
 }
 return a;
}
function pendingTrophyTieV39(){return mainTieGroupsV39().find(g=>!resolvedTieV39(g))||null}
function mainFinishedV39(){return S.heats.length>0&&S.heats.every(h=>Array.isArray(h.results)&&h.results.length===h.lanes.filter(Boolean).length)}
function placeRangeV39(g){const a=g.start+1,b=g.end+1;return a===b?ordinal(a):`${ordinal(a)}–${ordinal(b)}`}
function runoffRacersV39(ro){return (ro?.racerIds||[]).map(id=>racerById(id)).filter(Boolean)}
function runoffStandingsV39(ro){
 const map=new Map((ro.racerIds||[]).map(id=>[id,{id,points:0,races:0,wins:0}]));
 (ro.heats||[]).forEach(h=>(h.results||[]).forEach(x=>{const s=map.get(x.racerId);if(s){s.points+=Number(x.points)||0;s.races++;if(x.position===1)s.wins++}}));
 return [...map.values()].sort((a,b)=>a.points-b.points||(racerById(a.id)?.number||0)-(racerById(b.id)?.number||0));
}
function runoffHasTieV39(a){for(let i=1;i<a.length;i++)if(samePointsV39(a[i-1].points,a[i].points))return true;return false}
function verifyRunoffScheduleV39(ro){
 if(!ro||!Array.isArray(ro.heats))return {ok:false,errors:['Runoff schedule is missing.']};
 return window.mnltVerifyScheduleV38?window.mnltVerifyScheduleV38(ro.heats,ro.racerIds):{ok:false,errors:['Runoff verifier is unavailable.']};
}
function startRunoffV39(group,attempt){
 const ids=group.racers.map(r=>r.id),heats=buildFairSchedule(ids),check=window.mnltVerifyScheduleV38(heats,ids);
 if(!check.ok){toast('Runoff schedule failed verification. Race Control remains locked.');return;}
 mutate(()=>{S.runoff={active:true,key:group.key,racerIds:ids,placeStart:group.start+1,placeEnd:group.end+1,attempt:Number(attempt)||1,current:0,heats,completed:false,createdAt:new Date().toISOString()};});
 finishPicks=[];
 show('controlPage');
 toast(`Trophy runoff set ${Number(attempt)||1} ready.`);
}
function restartRunoffV39(){
 const ro=S.runoff;if(!ro)return;
 const heats=buildFairSchedule(ro.racerIds),check=window.mnltVerifyScheduleV38(heats,ro.racerIds);
 if(!check.ok){toast('Runoff schedule failed verification.');return;}
 mutate(()=>{ro.attempt=(Number(ro.attempt)||1)+1;ro.current=0;ro.heats=heats;ro.completed=false;ro.createdAt=new Date().toISOString();});
 finishPicks=[];
 toast(`Runoff set ${ro.attempt} ready.`);
}
function finishRunoffIfCompleteV39(){
 const ro=S.runoff;if(!ro||!ro.heats?.length)return {done:false};
 const complete=ro.heats.every(h=>Array.isArray(h.results)&&h.results.length===h.lanes.filter(Boolean).length);
 if(!complete)return {done:false};
 const a=runoffStandingsV39(ro),tied=runoffHasTieV39(a);
 if(tied){ro.completed=true;return {done:true,tied:true,standings:a};}
 if(!S.tieBreaks||typeof S.tieBreaks!=='object')S.tieBreaks={};
 S.tieBreaks[ro.key]={order:a.map(x=>x.id),attempts:Number(ro.attempt)||1,resolvedAt:new Date().toISOString()};
 S.runoff=null;
 return {done:true,tied:false,standings:a};
}

function renderRunoffControlV39(){
 const ro=S.runoff,host=document.getElementById('controlBody');
 if(!ro||!ro.active){host.innerHTML='<div class="panel"><h2>Runoff unavailable</h2></div>';return;}
 const check=verifyRunoffScheduleV39(ro);
 if(!check.ok){host.innerHTML=`<div class="panel"><h2 class="red">RUNOFF CONTROL LOCKED</h2><p>The runoff schedule failed verification.</p><ul>${(check.errors||[]).map(e=>`<li>${esc(e)}</li>`).join('')}</ul></div>`;return;}
 const racers=runoffRacersV39(ro);
 if(ro.completed){
  const a=runoffStandingsV39(ro);
  host.innerHTML=`<div class="panel"><div class="controlTitle">TROPHY RUNOFF • ${ordinal(ro.placeStart)}${ro.placeEnd!==ro.placeStart?'–'+ordinal(ro.placeEnd):''}</div><div style="background:#29171b;border:2px solid #8d4a54;border-radius:10px;padding:14px"><h2 class="red" style="margin-bottom:5px">STILL TIED AFTER RUNOFF SET ${ro.attempt}</h2><p>No hidden tiebreaker will be used. These racers will race another verified set.</p>${a.map((x,i)=>`<div class="rowCard"><b>${i+1}.</b> ${esc(racerById(x.id)?.name||'')} • ${x.points.toFixed(2)} points</div>`).join('')}<div class="actions"><button class="btn primary" id="anotherRunoffV39">START ANOTHER RUNOFF SET</button><button class="btn" id="runoffResultsV39">Back to Results</button></div></div></div>`;
  document.getElementById('anotherRunoffV39').onclick=restartRunoffV39;
  document.getElementById('runoffResultsV39').onclick=()=>show('resultsPage');
  return;
 }
 ro.current=Math.max(0,Math.min(Number(ro.current)||0,ro.heats.length-1));
 const h=ro.heats[ro.current],active=h.lanes.filter(Boolean),saved=Array.isArray(h.results)&&h.results.length>0;
 if(saved)finishPicks=h.results.slice().sort((a,b)=>a.position-b.position).map(x=>x.racerId);else finishPicks=finishPicks.filter(id=>active.includes(id));
 host.innerHTML=`<div class="panel"><div class="controlTitle">TROPHY RUNOFF • Set ${ro.attempt} • Heat ${h.id} of ${ro.heats.length}</div><div style="background:#10271d;border:2px solid #4e9b67;border-radius:10px;padding:10px 12px;margin-bottom:12px"><b class="green">✓ RUNOFF SCHEDULE VERIFIED</b><div class="muted" style="margin-top:4px">${racers.length} tied racers • every racer gets 4 runs and every lane once${racers.length>=4?' • no empty lanes':' • empty lanes unavoidable with fewer than 4 racers'}</div></div><div class="controlGrid"><div id="runoffFinishListV39"></div><div class="panel"><h3>${saved?'Saved Results':'Finish Order'}</h3><div id="runoffPickListV39"></div><div class="actions"><button class="btn" id="runoffUndoV39">Undo Pick</button><button class="btn good" id="runoffSaveV39" ${finishPicks.length===active.length&&active.length?'':'disabled'}>SAVE RUNOFF RESULTS</button></div></div></div><div class="actions"><button class="btn" id="runoffPrevV39" ${ro.current===0?'disabled':''}>← Previous</button><button class="btn" id="runoffNextV39" ${ro.current>=ro.heats.length-1?'disabled':''}>Next →</button><button class="btn" id="runoffProjV39">Projector</button><button class="btn" id="runoffBackResultsV39">Results</button></div></div>`;
 const list=document.getElementById('runoffFinishListV39');
 h.lanes.forEach((id,l)=>{if(!id)return;const r=racerById(id),pos=finishPicks.indexOf(id),b=document.createElement('button');b.className='finishBtn'+(pos>=0?' picked':'');b.innerHTML=`<span class="finishPos">${pos>=0?ordinal(pos+1):''}</span> Lane ${l+1} — ${esc(r?.name||'')}`;b.onclick=()=>{if(saved)return;const i=finishPicks.indexOf(id);if(i>=0)finishPicks.splice(i,1);else if(finishPicks.length<active.length)finishPicks.push(id);renderControl()};list.appendChild(b)});
 document.getElementById('runoffPickListV39').innerHTML=finishPicks.length?finishPicks.map((id,i)=>`<div class="rowCard"><b>${ordinal(i+1)}</b> — ${esc(racerById(id)?.name||'')}</div>`).join(''):'<p class="muted">Tap racers in finish order.</p>';
 document.getElementById('runoffUndoV39').onclick=()=>{if(!saved){finishPicks.pop();renderControl()}};
 document.getElementById('runoffSaveV39').onclick=()=>{
  let outcome={done:false};
  mutate(()=>{const count=active.length;h.results=finishPicks.map((id,i)=>({racerId:id,position:i+1,points:heatPoints(i,count)}));if(ro.current<ro.heats.length-1)ro.current++;outcome=finishRunoffIfCompleteV39();});
  finishPicks=[];
  if(outcome.done&&!outcome.tied){toast('Trophy tie settled on the track.');show('resultsPage');}
  else if(outcome.done&&outcome.tied){toast('Runoff is still tied. Another set is required.');renderControl();}
  else{toast('Runoff heat saved.');renderControl();}
 };
 document.getElementById('runoffPrevV39').onclick=()=>{ro.current--;finishPicks=[];persist();renderControl()};
 document.getElementById('runoffNextV39').onclick=()=>{ro.current++;finishPicks=[];persist();renderControl()};
 document.getElementById('runoffProjV39').onclick=openProjector;
 document.getElementById('runoffBackResultsV39').onclick=()=>show('resultsPage');
}

const baseRenderControlV39=renderControl;
renderControl=function(){if(S.runoff&&S.runoff.active){renderRunoffControlV39();return;}baseRenderControlV39();};

function renderFinalResultsV39(){
 const host=document.getElementById('resultsBody'),finished=S.heats.filter(h=>h.results?.length).length;
 if(!S.heats.length){host.innerHTML='<p class="muted">No race results yet.</p>';return;}
 const sched=window.mnltVerifyScheduleV38(S.heats,S.racers.map(r=>r.id));
 if(!sched.ok){host.innerHTML='<div class="panel"><h2 class="red">Results unavailable</h2><p>The race schedule failed verification.</p></div>';return;}
 if(!mainFinishedV39()){
  const a=rawMainStandingsV39();
  host.innerHTML=`<div class="panel" style="border-color:#d8a63d"><b class="gold">PROVISIONAL RESULTS</b><div class="muted" style="margin-top:5px">${finished} of ${S.heats.length} heats are saved. Trophy places are not official yet.</div></div>${a.length?`<table><thead><tr><th>Place</th><th>Racer</th><th>Points</th><th>Races</th><th>Wins</th></tr></thead><tbody>${a.map((r,i)=>`<tr><td>${i+1}</td><td>${esc(r.name)}</td><td>${r.races?r.points.toFixed(2):'—'}</td><td>${r.races}</td><td>${r.wins}</td></tr>`).join('')}</tbody></table>`:''}`;
  return;
 }
 const a=finalStandingsV39(),pending=pendingTrophyTieV39(),active=S.runoff&&S.runoff.active;
 let top='';
 if(active){const ro=S.runoff;top=`<div class="panel" style="border-color:#d8a63d"><h2 class="gold" style="margin-bottom:6px">TROPHY RUNOFF IN PROGRESS</h2><div>${ordinal(ro.placeStart)}${ro.placeEnd!==ro.placeStart?'–'+ordinal(ro.placeEnd):''} place tie • Set ${ro.attempt}</div><div class="actions"><button class="btn primary" id="goRunoffV39">GO TO RUNOFF RACE CONTROL</button></div></div>`;}
 else if(pending){top=`<div class="panel" style="border:2px solid #d8a63d"><h2 class="gold" style="margin-bottom:6px">TROPHY TIE — RUNOFF REQUIRED</h2><div><b>${placeRangeV39(pending)} place</b> is tied.</div><div class="pills" style="margin-top:10px">${pending.racers.map(r=>`<span class="pill">${esc(r.name)}</span>`).join('')}</div><p class="muted">The tie will be settled on the track. No race number, wins count, random choice, or hidden software tiebreaker will decide it.</p><div class="actions"><button class="btn primary" id="startRunoffV39">START TROPHY RUNOFF</button></div></div>`;}
 else{top='<div class="panel" style="border:2px solid #4e9b67;background:#10271d"><h2 class="green" style="margin-bottom:4px">✓ TROPHY PLACES FINAL</h2><div class="muted">All heats are complete and every trophy tie has been settled on the track.</div></div>';}
 host.innerHTML=`${top}<div class="pills"><span class="pill">${finished} / ${S.heats.length} Heats Saved</span><span class="pill green">Verified race schedule</span></div><table><thead><tr><th>Place</th><th>Racer</th><th>Main Race Points</th><th>Races</th><th>Wins</th></tr></thead><tbody>${a.map((r,i)=>`<tr><td>${i+1}</td><td>${esc(r.name)}</td><td>${r.points.toFixed(2)}</td><td>${r.races}</td><td>${r.wins}</td></tr>`).join('')}</tbody></table>`;
 if(active)document.getElementById('goRunoffV39').onclick=()=>show('controlPage');
 if(pending)document.getElementById('startRunoffV39').onclick=()=>startRunoffV39(pending,1);
}

renderResults=renderFinalResultsV39;
window.mnltV39={rawMainStandings:rawMainStandingsV39,finalStandings:finalStandingsV39,pendingTrophyTie:pendingTrophyTieV39,mainTieGroups:mainTieGroupsV39,runoffStandings:runoffStandingsV39,runoffHasTie:runoffHasTieV39};

})();