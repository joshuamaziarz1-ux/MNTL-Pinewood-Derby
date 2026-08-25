(function(){
'use strict';

const MOD_SAFETY_V40=[
 ['trackSafe','Will not damage the track'],
 ['noBurning','No burning, flame, or track-damaging effect'],
 ['secure','Parts, weights, batteries, and attachments are secure']
];
const MOD_COMPAT_V40=[
 ['fitsLane','Fits and clears one lane safely'],
 ['adjacentClear','Will not interfere with cars in adjacent lanes'],
 ['startApproved','Works safely with the starting gate / approved start method'],
 ['finishClear','Clears the finish area / timer safely']
];
const TROPHY_PLACES_MOD_V40=4;
let modRegenArmedV40=false;

function ensureModifiedStateV40(){
 if(!S.modified||typeof S.modified!=='object')S.modified={};
 if(!Array.isArray(S.modified.racers))S.modified.racers=[];
 if(!Array.isArray(S.modified.heats))S.modified.heats=[];
 if(!Number.isFinite(Number(S.modified.current)))S.modified.current=0;
 if(!S.modified.tieBreaks||typeof S.modified.tieBreaks!=='object')S.modified.tieBreaks={};
 if(!('runoff' in S.modified))S.modified.runoff=null;
 if(!S.modified.exhibition||typeof S.modified.exhibition!=='object')S.modified.exhibition={active:false};
}
ensureModifiedStateV40();

function modInspectionRawV40(r){
 const x=r.modInspection||{};
 return {items:x.items||{},approved:!!x.approved,approvedAt:x.approvedAt||'',photoSaved:!!x.photoSaved,savedAt:x.savedAt||'',raceClass:x.raceClass||''};
}
function modSafetyAnsweredV40(x){return MOD_SAFETY_V40.every(([k])=>x.items[k]==='pass'||x.items[k]==='fail')}
function modCompatAnsweredV40(x){return MOD_COMPAT_V40.every(([k])=>x.items[k]==='pass'||x.items[k]==='fail')}
function modSafetyPassV40(x){return MOD_SAFETY_V40.every(([k])=>x.items[k]==='pass')}
function modCompatPassV40(x){return MOD_COMPAT_V40.every(([k])=>x.items[k]==='pass')}
function modOfficialRegsV40(){return divRegs('mod').filter(r=>r.modCheckIn==='checked'&&modInspectionRawV40(r).approved&&modInspectionRawV40(r).raceClass==='official')}
function modExhibitionRegsV40(){return divRegs('mod').filter(r=>r.modCheckIn==='checked'&&modInspectionRawV40(r).approved&&modInspectionRawV40(r).raceClass==='exhibition')}
function modRacerByIdV40(id){return (S.modified.racers||[]).find(r=>r.id===id)||null}
function sameSetV40(a,b){if(a.length!==b.length)return false;const x=new Set(a.map(String));return b.every(v=>x.has(String(v)))}
function clearModifiedRaceV40(){
 ensureModifiedStateV40();
 S.modified.heats=[];S.modified.current=0;S.modified.tieBreaks={};S.modified.runoff=null;finishPicks=[];
}
function clearModRaceIfNeededV40(){if(S.modified.heats.length||S.modified.runoff)clearModifiedRaceV40()}

/* Modified check-in changes invalidate a generated Modified race. */
const baseSetCheckV40=setCheck;
setCheck=function(type,id,value){
 if(type!=='mod')return baseSetCheckV40(type,id,value);
 const r=S.registrations.find(x=>x.id===id);if(!r)return;
 mutate(()=>{r.modCheckIn=value;clearModRaceIfNeededV40()});
 toast('Modified check-in updated. Race schedule cleared if needed.');
};

function setModInspectItemV40(id,key,value){
 const r=S.registrations.find(x=>x.id===id);if(!r)return;
 mutate(()=>{const x=ensureInspection(r,'mod');x.items[key]=value;x.approved=false;x.approvedAt='';x.raceClass='';clearModRaceIfNeededV40()},false);
 renderInspection();
}
function saveModInspectionV40(id){
 const r=S.registrations.find(x=>x.id===id);if(!r)return;
 const x=ensureInspection(r,'mod'),view=modInspectionRawV40(r);
 if(!modSafetyAnsweredV40(view)||!modCompatAnsweredV40(view)){toast('Finish every Modified inspection check first.');return;}
 const safe=modSafetyPassV40(view),compat=modCompatPassV40(view);
 let raceClass=document.getElementById('modRaceClassV40')?.value||'';
 if(!safe)raceClass='blocked';
 if(safe&&raceClass==='official'&&!compat){toast('This car cannot be Official because one or more race-compatibility checks failed. Choose Exhibition Only.');return;}
 if(safe&&!['official','exhibition'].includes(raceClass)){toast('Choose Official Race or Exhibition Only.');return;}
 const now=new Date().toISOString();inspectSelected.mod=null;
 mutate(()=>{x.approved=safe;x.approvedAt=safe?now:'';x.savedAt=now;x.raceClass=raceClass;clearModRaceIfNeededV40()});
 toast(!safe?'Inspection saved — NOT CLEARED TO RUN.':raceClass==='official'?'Modified car approved for the Official Race.':'Modified car approved for Exhibition Only.');
}

const baseRenderInspectionV40=renderInspection;
renderInspection=function(){
 if(currentDivision!=='mod')return baseRenderInspectionV40();
 const arr=inspectRegs('mod'),passed=arr.filter(r=>modInspectionRawV40(r).approved),blocked=arr.filter(r=>modInspectionRawV40(r).savedAt&&!modInspectionRawV40(r).approved),pending=arr.filter(r=>!modInspectionRawV40(r).savedAt),selected=arr.find(r=>r.id===inspectSelected.mod)||null;
 const official=passed.filter(r=>modInspectionRawV40(r).raceClass==='official').length,exhibition=passed.filter(r=>modInspectionRawV40(r).raceClass==='exhibition').length;
 $('inspectBody').innerHTML=`<div class="inspectTop"><div><label>Racer</label><select id="inspectSelect"><option value="">Select racer...</option>${arr.map(r=>{const x=modInspectionRawV40(r),tag=x.raceClass==='official'?' — OFFICIAL':x.raceClass==='exhibition'?' — EXHIBITION':x.savedAt&&!x.approved?' — NOT CLEARED':'';return `<option value="${r.id}" ${selected?.id===r.id?'selected':''}>${numLabel(r,'mod')} ${esc(r.name)}${tag}</option>`}).join('')}</select></div><div class="pills"><span class="pill">${pending.length} Waiting</span><span class="pill green">${official} Official</span><span class="pill gold">${exhibition} Exhibition</span><span class="pill red">${blocked.length} Not Cleared</span></div></div><div id="inspectFormHost"></div><div class="bucketGrid"><div class="bucket"><h3>Cleared to Run</h3><div id="passedCars"></div></div><div class="bucket"><h3>Not Cleared</h3><div id="badCars"></div></div></div>`;
 $('inspectSelect').onchange=e=>{inspectSelected.mod=e.target.value?Number(e.target.value):null;renderInspection()};
 if(selected){
  const x=modInspectionRawV40(selected),answered=[...MOD_SAFETY_V40,...MOD_COMPAT_V40].filter(([k])=>['pass','fail'].includes(x.items[k])).length,safe=modSafetyPassV40(x),compat=modCompatPassV40(x),allAnswered=modSafetyAnsweredV40(x)&&modCompatAnsweredV40(x);
  const defaultClass=x.raceClass==='official'||x.raceClass==='exhibition'?x.raceClass:(allAnswered&&safe&&compat?'official':allAnswered&&safe?'exhibition':'');
  $('inspectFormHost').innerHTML=`<div class="inspectForm"><div class="inspectHead"><div><div class="inspectName">${numLabel(selected,'mod')} ${esc(selected.name)}</div><div class="rowMeta">${esc(carName(selected,'mod'))}</div></div><b class="gold">${answered} / ${MOD_SAFETY_V40.length+MOD_COMPAT_V40.length}</b></div><h3 style="margin:14px 0 4px">Safety — required for any run</h3>${MOD_SAFETY_V40.map(([k,label])=>`<div class="checkItem"><div>${esc(label)}</div><div class="checkBtns"><button class="btn ${x.items[k]==='pass'?'passSel':''}" data-mod-ik="${k}" data-mod-iv="pass">PASS</button><button class="btn ${x.items[k]==='fail'?'failSel':''}" data-mod-ik="${k}" data-mod-iv="fail">FAIL</button></div></div>`).join('')}<h3 style="margin:16px 0 4px">Head-to-head race compatibility</h3>${MOD_COMPAT_V40.map(([k,label])=>`<div class="checkItem"><div>${esc(label)}</div><div class="checkBtns"><button class="btn ${x.items[k]==='pass'?'passSel':''}" data-mod-ik="${k}" data-mod-iv="pass">PASS</button><button class="btn ${x.items[k]==='fail'?'failSel':''}" data-mod-ik="${k}" data-mod-iv="fail">FAIL</button></div></div>`).join('')}<div style="margin-top:14px;background:#13243a;border-radius:10px;padding:12px"><label>Run Classification</label><select id="modRaceClassV40" ${allAnswered&&safe?'':'disabled'}><option value="">Choose...</option><option value="official" ${defaultClass==='official'?'selected':''} ${compat?'':'disabled'}>Official Modified Race</option><option value="exhibition" ${defaultClass==='exhibition'?'selected':''}>Exhibition Only</option></select><div class="muted" style="margin-top:4px">Official requires every safety and compatibility check to pass. Exhibition still requires every safety check to pass.</div></div><div class="actions"><button class="btn primary" id="saveModInspectionV40" ${allAnswered?'':'disabled'}>SAVE MODIFIED INSPECTION</button></div></div>`;
  document.querySelectorAll('[data-mod-ik]').forEach(b=>b.onclick=()=>setModInspectItemV40(selected.id,b.dataset.modIk,b.dataset.modIv));
  $('saveModInspectionV40').onclick=()=>saveModInspectionV40(selected.id);
 }
 const p=$('passedCars');p.innerHTML=passed.length?'':'<p class="muted">None yet.</p>';
 passed.forEach(r=>{const x=modInspectionRawV40(r),d=document.createElement('div');d.className='rowCard';d.innerHTML=`<div class="rowName">${numLabel(r,'mod')} ${esc(r.name)}</div><div class="rowMeta">${esc(carName(r,'mod'))}</div><div class="pills"><span class="pill ${x.raceClass==='official'?'green':'gold'}">${x.raceClass==='official'?'OFFICIAL RACE':'EXHIBITION ONLY'}</span><span class="pill">${x.photoSaved?'Photo saved':'Photo needed'}</span></div><div class="actions"><button class="btn good photoBtn">${x.photoSaved?'RETAKE PHOTO':'TAKE PHOTO'}</button><input class="file photoInput" type="file" accept="image/*" capture="environment"><button class="btn reinspect">Reinspect</button></div><div class="photoHost"></div>`;d.querySelector('.photoBtn').onclick=()=>d.querySelector('.photoInput').click();d.querySelector('.photoInput').onchange=e=>takePhoto('mod',r.id,e.target);d.querySelector('.reinspect').onclick=()=>loadInspection('mod',r.id);p.appendChild(d);if(x.photoSaved)appendPhoto('mod',r.id,d.querySelector('.photoHost'))});
 const b=$('badCars');b.innerHTML=blocked.length?'':'<p class="muted">None.</p>';
 blocked.forEach(r=>{const d=document.createElement('div');d.className='rowCard';d.innerHTML=`<div class="rowName">${numLabel(r,'mod')} ${esc(r.name)}</div><div class="rowMeta red">NOT CLEARED TO RUN</div><div class="actions"><button class="btn load">LOAD</button></div>`;d.querySelector('.load').onclick=()=>loadInspection('mod',r.id);b.appendChild(d)});
};

function modBuildRacersV40(regs){
 return regs.map((reg,i)=>{if(!reg.modRacerId)reg.modRacerId=Date.now()+i+1;return{id:reg.modRacerId,registrationId:reg.id,name:reg.name,car:reg.modCar||'',division:'Modified',number:reg.modNo||i+1}});
}
function modCurrentOfficialIdsV40(){return modOfficialRegsV40().map(r=>r.modRacerId).filter(Boolean)}
function verifyModifiedScheduleV40(){
 ensureModifiedStateV40();
 const ids=(S.modified.racers||[]).map(r=>r.id),v=window.mnltVerifyScheduleV38?window.mnltVerifyScheduleV38(S.modified.heats,ids):{ok:false,errors:['Race verifier unavailable.'],stats:{}};
 const live=modCurrentOfficialIdsV40();
 if(!sameSetV40(ids,live)){v.ok=false;v.errors=(v.errors||[]).concat('The Official Modified racer list changed after this schedule was generated. Regenerate the race.');}
 return v;
}
function generateModifiedRaceV40(){
 const official=modOfficialRegsV40();if(official.length<2)return;
 const hasResults=S.modified.heats.some(h=>Array.isArray(h.results)&&h.results.length);
 if(hasResults&&!modRegenArmedV40){modRegenArmedV40=true;toast('Results already exist. Click REGENERATE again to erase the Modified race results.');renderGenerate();setTimeout(()=>{modRegenArmedV40=false;if(currentDivision==='mod'&&$('generatePage').classList.contains('active'))renderGenerate()},4000);return;}
 modRegenArmedV40=false;
 mutate(()=>{S.modified.racers=modBuildRacersV40(official);S.modified.heats=buildFairSchedule(S.modified.racers.map(r=>r.id));S.modified.current=0;S.modified.tieBreaks={};S.modified.runoff=null;S.modified.exhibition={active:false};S.raceType='Modified'});
 const v=verifyModifiedScheduleV40();toast(v.ok?'Modified race generated and verified.':'Modified schedule failed verification.');renderGenerate();
}
function startExhibitionV40(regId,lane){
 const r=S.registrations.find(x=>x.id===regId);if(!r)return;
 mutate(()=>{ensureModifiedStateV40();S.raceType='Modified';S.modified.exhibition={active:true,registrationId:r.id,lane:Number(lane)||2,startedAt:new Date().toISOString()}} ,false);
 window.open('v40-projector.html?v=40-modified','mnltProjector','width=1500,height=900');
}
function clearExhibitionV40(){mutate(()=>{S.modified.exhibition={active:false}},false);toast('Exhibition display cleared.')}
function renderModifiedGenerateV40(){
 ensureModifiedStateV40();
 const official=modOfficialRegsV40(),exhibition=modExhibitionRegsV40(),all=divRegs('mod'),classified=new Set([...official,...exhibition].map(r=>r.id)),notReady=all.filter(r=>!classified.has(r.id));
 $('generateBody').innerHTML=`<div class="summary4"><div class="stat"><b>${official.length}</b><span>Official</span></div><div class="stat"><b>${exhibition.length}</b><span>Exhibition</span></div><div class="stat"><b>${notReady.length}</b><span>Not Ready</span></div><div class="stat"><b>${S.modified.heats.length}</b><span>Heats</span></div></div><div class="panel" style="background:#0e1c2c"><h3>Official Modified Race</h3><div class="muted">Uses the same verified 4-lane race engine as Traditional: 4 actual races per racer, every lane once, and no empty lanes when 4 or more Official racers are entered.</div><div class="actions"><button class="btn primary" id="genModRaceV40" ${official.length>=2?'':'disabled'}>${S.modified.heats.length?(modRegenArmedV40?'CLICK AGAIN TO REGENERATE':'REGENERATE MODIFIED RACE'):'GENERATE MODIFIED RACE'}</button></div><div id="modGenStatusV40" style="margin-top:10px"></div><div id="modScheduleV40"></div></div><div class="panel"><h3>Exhibition Only</h3><div class="muted">Exhibition runs do not receive points and never affect Official Modified standings.</div><div id="modExhibitionListV40"></div></div>`;
 $('genModRaceV40').onclick=generateModifiedRaceV40;
 if(S.modified.heats.length){const v=verifyModifiedScheduleV40(),st=$('modGenStatusV40');st.innerHTML=v.ok?`<div style="background:#10271d;border:2px solid #4e9b67;border-radius:10px;padding:12px"><div style="font-size:20px;font-weight:1000;color:#9ee7af">✓ MODIFIED RACE SCHEDULE VERIFIED</div><div class="muted" style="margin-top:5px">${v.stats.heats} heats • 4 races per racer • every lane once • ${v.stats.emptySlots} empty lane slots</div></div>`:`<div style="background:#29171b;border:2px solid #8d4a54;border-radius:10px;padding:12px"><div style="font-size:20px;font-weight:1000;color:#ff9da7">MODIFIED SCHEDULE FAILED VERIFICATION</div><ul>${(v.errors||[]).map(e=>`<li>${esc(e)}</li>`).join('')}</ul></div>`;
  $('modScheduleV40').innerHTML=S.modified.heats.map((h,i)=>`<div class="scheduleHeat"><div class="heatTitle">Heat ${i+1} of ${S.modified.heats.length}</div>${h.lanes.map((id,l)=>{const r=id?modRacerByIdV40(id):null;return `<div class="laneLine"><b>Lane ${l+1}</b><span>${r?'M'+(r.number||''):'—'}</span><span>${r?esc(r.name):'Empty'}</span></div>`}).join('')}</div>`).join('');
 }else if(official.length<2)$('modGenStatusV40').innerHTML='<span class="gold">At least 2 checked-in, inspected, Official Modified racers are required.</span>';
 const ex=$('modExhibitionListV40');ex.innerHTML=exhibition.length?'':'<p class="muted">No Exhibition Only cars.</p>';
 exhibition.forEach(r=>{const d=document.createElement('div');d.className='rowCard';d.innerHTML=`<div class="rowName">${esc(r.name)}</div><div class="rowMeta">${esc(carName(r,'mod'))}</div><div class="actions"><select class="exLaneV40" style="width:auto;margin:0"><option value="1">Lane 1</option><option value="2" selected>Lane 2</option><option value="3">Lane 3</option><option value="4">Lane 4</option></select><button class="btn primary exShowV40">SHOW / RUN EXHIBITION</button></div>`;d.querySelector('.exShowV40').onclick=()=>startExhibitionV40(r.id,d.querySelector('.exLaneV40').value);ex.appendChild(d)});
 if(S.modified.exhibition?.active){const d=document.createElement('div');d.className='actions';d.innerHTML='<button class="btn" id="clearExhibitionV40">CLEAR EXHIBITION FROM PROJECTOR</button>';ex.appendChild(d);$('clearExhibitionV40').onclick=clearExhibitionV40;}
}

function modHeatPointsV40(position,count){return heatPoints(position,count)}
function renderModifiedControlV40(){
 ensureModifiedStateV40();
 if(S.modified.runoff&&S.modified.runoff.active){renderModRunoffControlV40();return;}
 if(!S.modified.heats.length){$('controlBody').innerHTML='<div class="panel"><h2>Modified Race Control</h2><p class="gold">Generate the Official Modified race first.</p></div>';return;}
 const v=verifyModifiedScheduleV40();if(!v.ok){$('controlBody').innerHTML=`<div class="panel"><h2 class="red">MODIFIED RACE CONTROL LOCKED</h2><p>The schedule failed the race-day safety check.</p><ul>${(v.errors||[]).map(e=>`<li>${esc(e)}</li>`).join('')}</ul><div class="actions"><button class="btn primary" id="backModGenerateV40">Go to Generate Race</button></div></div>`;$('backModGenerateV40').onclick=()=>show('generatePage');return;}
 S.modified.current=Math.max(0,Math.min(Number(S.modified.current)||0,S.modified.heats.length-1));const h=S.modified.heats[S.modified.current],active=h.lanes.filter(Boolean),saved=Array.isArray(h.results)&&h.results.length>0;if(saved)finishPicks=h.results.slice().sort((a,b)=>a.position-b.position).map(x=>x.racerId);else finishPicks=finishPicks.filter(id=>active.includes(id));
 $('controlBody').innerHTML=`<div class="panel"><div class="controlTitle">MODIFIED • Heat ${h.id} of ${S.modified.heats.length}</div><div style="background:#10271d;border:2px solid #4e9b67;border-radius:10px;padding:10px 12px;margin-bottom:12px"><b class="green">✓ VERIFIED OFFICIAL MODIFIED RACE</b></div><div class="controlGrid"><div id="modFinishListV40"></div><div class="panel"><h3>${saved?'Saved Results':'Finish Order'}</h3><div id="modPickListV40"></div><div class="actions"><button class="btn" id="modUndoV40">Undo Pick</button><button class="btn good" id="modSaveV40" ${finishPicks.length===active.length&&active.length&&!saved?'':'disabled'}>SAVE RESULTS</button></div></div></div><div class="actions"><button class="btn" id="modPrevV40" ${S.modified.current===0?'disabled':''}>← Previous</button><button class="btn" id="modNextV40" ${S.modified.current>=S.modified.heats.length-1||!saved?'disabled':''}>Next →</button><button class="btn" id="modProjV40">Projector</button><button class="btn" id="modResultsV40">Results</button></div></div>`;
 const list=$('modFinishListV40');h.lanes.forEach((id,l)=>{if(!id)return;const r=modRacerByIdV40(id),pos=finishPicks.indexOf(id),b=document.createElement('button');b.className='finishBtn'+(pos>=0?' picked':'');b.innerHTML=`<span class="finishPos">${pos>=0?ordinal(pos+1):''}</span> Lane ${l+1} — ${esc(r?.name||'')}`;b.onclick=()=>{if(saved)return;const i=finishPicks.indexOf(id);if(i>=0)finishPicks.splice(i,1);else if(finishPicks.length<active.length)finishPicks.push(id);renderControl()};list.appendChild(b)});
 $('modPickListV40').innerHTML=finishPicks.length?finishPicks.map((id,i)=>`<div class="rowCard"><b>${ordinal(i+1)}</b> — ${esc(modRacerByIdV40(id)?.name||'')}</div>`).join(''):'<p class="muted">Tap racers in finish order.</p>';
 $('modUndoV40').onclick=()=>{if(!saved){finishPicks.pop();renderControl()}};
 $('modSaveV40').onclick=()=>{mutate(()=>{const count=active.length;h.results=finishPicks.map((id,i)=>({racerId:id,position:i+1,points:modHeatPointsV40(i,count)}));if(S.modified.current<S.modified.heats.length-1)S.modified.current++});finishPicks=[];toast('Modified heat saved.');renderControl()};
 $('modPrevV40').onclick=()=>{S.modified.current--;finishPicks=[];persist();renderControl()};$('modNextV40').onclick=()=>{S.modified.current++;finishPicks=[];persist();renderControl()};$('modProjV40').onclick=openProjector;$('modResultsV40').onclick=()=>show('resultsPage');
}

function modRawStandingsV40(){const map=new Map((S.modified.racers||[]).map(r=>[r.id,{id:r.id,name:r.name,number:r.number,points:0,races:0,wins:0}]));S.modified.heats.forEach(h=>(h.results||[]).forEach(x=>{const s=map.get(x.racerId);if(s){s.points+=Number(x.points)||0;s.races++;if(x.position===1)s.wins++}}));return [...map.values()].sort((a,b)=>a.points-b.points||a.number-b.number)}
function samePtsModV40(a,b){return Math.abs(Number(a)-Number(b))<1e-9}
function modTieKeyV40(racers){return `${racers.map(r=>String(r.id)).sort().join(',')}@${racers.length?Number(racers[0].points).toFixed(6):'0'}`}
function modTieGroupsV40(){const a=modRawStandingsV40(),groups=[];for(let i=0;i<a.length;){let j=i+1;while(j<a.length&&samePtsModV40(a[j].points,a[i].points))j++;if(j-i>1&&i<TROPHY_PLACES_MOD_V40){const racers=a.slice(i,j);groups.push({start:i,end:j-1,racers,key:modTieKeyV40(racers)})}i=j}return groups}
function modResolvedTieV40(g){const t=S.modified.tieBreaks?.[g.key];if(!t||!Array.isArray(t.order)||t.order.length!==g.racers.length)return null;const need=new Set(g.racers.map(r=>String(r.id))),got=new Set(t.order.map(String));return need.size===got.size&&[...need].every(x=>got.has(x))?t:null}
function modFinalStandingsV40(){const a=modRawStandingsV40();for(let i=0;i<a.length;){let j=i+1;while(j<a.length&&samePtsModV40(a[j].points,a[i].points))j++;if(j-i>1){const racers=a.slice(i,j),g={racers,key:modTieKeyV40(racers)},t=modResolvedTieV40(g);if(t){const pos=new Map(t.order.map((id,k)=>[String(id),k]));a.splice(i,j-i,...racers.sort((x,y)=>pos.get(String(x.id))-pos.get(String(y.id))))}}i=j}return a}
function modPendingTieV40(){return modTieGroupsV40().find(g=>!modResolvedTieV40(g))||null}
function modMainFinishedV40(){return S.modified.heats.length>0&&S.modified.heats.every(h=>Array.isArray(h.results)&&h.results.length===h.lanes.filter(Boolean).length)}
function modPlaceRangeV40(g){const a=g.start+1,b=g.end+1;return a===b?ordinal(a):`${ordinal(a)}–${ordinal(b)}`}

function modRunoffIdsV40(ro){return Array.isArray(ro?.currentIds)?ro.currentIds:[]}
function modRunoffStandingsV40(ro){const ids=modRunoffIdsV40(ro),map=new Map(ids.map(id=>[id,{id,points:0,races:0,wins:0}]));(ro.heats||[]).forEach(h=>(h.results||[]).forEach(x=>{const s=map.get(x.racerId);if(s){s.points+=Number(x.points)||0;s.races++;if(x.position===1)s.wins++}}));return [...map.values()].sort((a,b)=>a.points-b.points||(modRacerByIdV40(a.id)?.number||0)-(modRacerByIdV40(b.id)?.number||0))}
function modScoreBlocksV40(a){const out=[];for(let i=0;i<a.length;){let j=i+1;while(j<a.length&&samePtsModV40(a[j].points,a[i].points))j++;out.push(a.slice(i,j).map(x=>x.id));i=j}return out}
function modVerifyRunoffV40(ro){return window.mnltVerifyScheduleV38?window.mnltVerifyScheduleV38(ro.heats,modRunoffIdsV40(ro)):{ok:false,errors:['Runoff verifier unavailable.']}}
function startModRunoffV40(g){const ids=g.racers.map(r=>r.id),heats=buildFairSchedule(ids),v=window.mnltVerifyScheduleV38(heats,ids);if(!v.ok){toast('Modified runoff failed verification.');return}mutate(()=>{S.modified.runoff={active:true,key:g.key,rootIds:ids.slice(),blocks:[ids.slice()],blockIndex:0,currentIds:ids.slice(),placeStart:g.start+1,placeEnd:g.end+1,attempt:1,current:0,heats,completed:false}});finishPicks=[];show('controlPage');toast('Modified trophy runoff set 1 ready.')}
function continueModRunoffV40(){const ro=S.modified.runoff,idx=Number(ro?.nextBlockIndex);if(!ro||!ro.completed||!Number.isInteger(idx)||!Array.isArray(ro.blocks?.[idx])||ro.blocks[idx].length<2)return;const ids=ro.blocks[idx].slice(),heats=buildFairSchedule(ids),v=window.mnltVerifyScheduleV38(heats,ids);if(!v.ok){toast('Modified runoff failed verification.');return}mutate(()=>{ro.blockIndex=idx;ro.currentIds=ids;ro.attempt=(Number(ro.attempt)||1)+1;ro.current=0;ro.heats=heats;ro.completed=false;ro.nextBlockIndex=null});finishPicks=[];toast(`Modified runoff set ${ro.attempt} ready.`)}
function finishModRunoffV40(){const ro=S.modified.runoff;if(!ro||!ro.heats?.length)return{done:false};if(!ro.heats.every(h=>Array.isArray(h.results)&&h.results.length===h.lanes.filter(Boolean).length))return{done:false};const a=modRunoffStandingsV40(ro),replacement=modScoreBlocksV40(a);ro.blocks.splice(ro.blockIndex,1,...replacement);const next=ro.blocks.findIndex(b=>Array.isArray(b)&&b.length>1);if(next>=0){ro.completed=true;ro.nextBlockIndex=next;return{done:true,tied:true}}S.modified.tieBreaks[ro.key]={order:ro.blocks.flat(),attempts:Number(ro.attempt)||1,resolvedAt:new Date().toISOString()};S.modified.runoff=null;return{done:true,tied:false}}
function modRunoffProgressV40(ro){return(ro.blocks||[]).map(b=>`<span class="pill ${b.length>1?'gold':'green'}">${b.map(id=>esc(modRacerByIdV40(id)?.name||'')).join(' / ')}</span>`).join('')}
function renderModRunoffControlV40(){
 const ro=S.modified.runoff,host=$('controlBody'),v=modVerifyRunoffV40(ro);if(!v.ok){host.innerHTML=`<div class="panel"><h2 class="red">MODIFIED RUNOFF CONTROL LOCKED</h2><ul>${(v.errors||[]).map(e=>`<li>${esc(e)}</li>`).join('')}</ul></div>`;return}
 if(ro.completed){const next=ro.blocks?.[ro.nextBlockIndex]||[];host.innerHTML=`<div class="panel"><div class="controlTitle">MODIFIED TROPHY RUNOFF</div><div style="background:#29171b;border:2px solid #8d4a54;border-radius:10px;padding:14px"><h2 class="red">TIE REMAINS AFTER RUNOFF SET ${ro.attempt}</h2><p>Racers already separated keep their order. Only racers still tied race again.</p><div class="pills">${modRunoffProgressV40(ro)}</div><div class="rowCard"><b>Next runoff:</b> ${next.map(id=>esc(modRacerByIdV40(id)?.name||'')).join(' vs. ')}</div><div class="actions"><button class="btn primary" id="nextModRunoffV40">START NEXT RUNOFF SET</button><button class="btn" id="backModResultsV40">Results</button></div></div></div>`;$('nextModRunoffV40').onclick=continueModRunoffV40;$('backModResultsV40').onclick=()=>show('resultsPage');return;}
 ro.current=Math.max(0,Math.min(Number(ro.current)||0,ro.heats.length-1));const h=ro.heats[ro.current],active=h.lanes.filter(Boolean),saved=Array.isArray(h.results)&&h.results.length>0;if(saved)finishPicks=h.results.slice().sort((a,b)=>a.position-b.position).map(x=>x.racerId);else finishPicks=finishPicks.filter(id=>active.includes(id));
 host.innerHTML=`<div class="panel"><div class="controlTitle">MODIFIED TROPHY RUNOFF • Set ${ro.attempt} • Heat ${h.id} of ${ro.heats.length}</div><div style="background:#10271d;border:2px solid #4e9b67;border-radius:10px;padding:10px 12px;margin-bottom:12px"><b class="green">✓ RUNOFF SCHEDULE VERIFIED</b><div class="muted">${ro.currentIds.length} tied racers • 4 runs each • every lane once${ro.currentIds.length>=4?' • no empty lanes':' • empty lanes unavoidable with fewer than 4 racers'}</div></div><div class="controlGrid"><div id="modRunFinishV40"></div><div class="panel"><h3>${saved?'Saved Results':'Finish Order'}</h3><div id="modRunPickV40"></div><div class="actions"><button class="btn" id="modRunUndoV40">Undo Pick</button><button class="btn good" id="modRunSaveV40" ${finishPicks.length===active.length&&active.length&&!saved?'':'disabled'}>SAVE RUNOFF RESULTS</button></div></div></div><div class="actions"><button class="btn" id="modRunPrevV40" ${ro.current===0?'disabled':''}>← Previous</button><button class="btn" id="modRunNextV40" ${ro.current>=ro.heats.length-1||!saved?'disabled':''}>Next →</button><button class="btn" id="modRunProjV40">Projector</button><button class="btn" id="modRunResultsV40">Results</button></div></div>`;
 const list=$('modRunFinishV40');h.lanes.forEach((id,l)=>{if(!id)return;const r=modRacerByIdV40(id),pos=finishPicks.indexOf(id),b=document.createElement('button');b.className='finishBtn'+(pos>=0?' picked':'');b.innerHTML=`<span class="finishPos">${pos>=0?ordinal(pos+1):''}</span> Lane ${l+1} — ${esc(r?.name||'')}`;b.onclick=()=>{if(saved)return;const i=finishPicks.indexOf(id);if(i>=0)finishPicks.splice(i,1);else finishPicks.push(id);renderControl()};list.appendChild(b)});
 $('modRunPickV40').innerHTML=finishPicks.length?finishPicks.map((id,i)=>`<div class="rowCard"><b>${ordinal(i+1)}</b> — ${esc(modRacerByIdV40(id)?.name||'')}</div>`).join(''):'<p class="muted">Tap racers in finish order.</p>';$('modRunUndoV40').onclick=()=>{if(!saved){finishPicks.pop();renderControl()}};$('modRunSaveV40').onclick=()=>{let outcome={done:false};mutate(()=>{const count=active.length;h.results=finishPicks.map((id,i)=>({racerId:id,position:i+1,points:heatPoints(i,count)}));if(ro.current<ro.heats.length-1)ro.current++;outcome=finishModRunoffV40()});finishPicks=[];if(outcome.done&&!outcome.tied){toast('Modified trophy tie settled on the track.');show('resultsPage')}else if(outcome.done){toast('Some Modified racers are still tied. Only those racers run again.');renderControl()}else{toast('Modified runoff heat saved.');renderControl()}};$('modRunPrevV40').onclick=()=>{ro.current--;finishPicks=[];persist();renderControl()};$('modRunNextV40').onclick=()=>{ro.current++;finishPicks=[];persist();renderControl()};$('modRunProjV40').onclick=openProjector;$('modRunResultsV40').onclick=()=>show('resultsPage');
}

function renderModifiedResultsV40(){
 ensureModifiedStateV40();const host=$('resultsBody');if(!S.modified.heats.length){host.innerHTML='<p class="muted">No Official Modified race results yet.</p>';return}const v=verifyModifiedScheduleV40();if(!v.ok){host.innerHTML='<div class="panel"><h2 class="red">Modified results unavailable</h2><p>The schedule failed verification.</p></div>';return}const finished=S.modified.heats.filter(h=>h.results?.length).length;if(!modMainFinishedV40()){const a=modRawStandingsV40();host.innerHTML=`<div class="panel" style="border-color:#d8a63d"><b class="gold">PROVISIONAL MODIFIED RESULTS</b><div class="muted">${finished} of ${S.modified.heats.length} heats saved. Trophy places are not official yet.</div></div><table><thead><tr><th>Place</th><th>Racer</th><th>Points</th><th>Races</th><th>Wins</th></tr></thead><tbody>${a.map((r,i)=>`<tr><td>${i+1}</td><td>${esc(r.name)}</td><td>${r.races?r.points.toFixed(2):'—'}</td><td>${r.races}</td><td>${r.wins}</td></tr>`).join('')}</tbody></table>`;return}
 const a=modFinalStandingsV40(),pending=modPendingTieV40(),active=S.modified.runoff&&S.modified.runoff.active;let top='';if(active){const ro=S.modified.runoff;top=`<div class="panel" style="border-color:#d8a63d"><h2 class="gold">MODIFIED TROPHY RUNOFF IN PROGRESS</h2><div>${ordinal(ro.placeStart)}${ro.placeEnd!==ro.placeStart?'–'+ordinal(ro.placeEnd):''} place tie • Set ${ro.attempt}</div><div class="pills">${modRunoffProgressV40(ro)}</div><div class="actions"><button class="btn primary" id="goModRunoffV40">GO TO RUNOFF RACE CONTROL</button></div></div>`}else if(pending){top=`<div class="panel" style="border:2px solid #d8a63d"><h2 class="gold">MODIFIED TROPHY TIE — RUNOFF REQUIRED</h2><div><b>${modPlaceRangeV40(pending)} place</b> is tied.</div><div class="pills">${pending.racers.map(r=>`<span class="pill">${esc(r.name)}</span>`).join('')}</div><p class="muted">The tie is settled on the track. No hidden tiebreaker is used.</p><div class="actions"><button class="btn primary" id="startModRunoffV40">START MODIFIED TROPHY RUNOFF</button></div></div>`}else{top='<div class="panel" style="border:2px solid #4e9b67;background:#10271d"><h2 class="green">✓ MODIFIED TROPHY PLACES FINAL</h2><div class="muted">All Official Modified heats are complete and trophy ties are settled.</div></div>'}
 host.innerHTML=`${top}<div class="pills"><span class="pill">${finished} / ${S.modified.heats.length} Heats Saved</span><span class="pill green">Verified Modified schedule</span></div><table><thead><tr><th>Place</th><th>Racer</th><th>Main Race Points</th><th>Races</th><th>Wins</th></tr></thead><tbody>${a.map((r,i)=>`<tr><td>${i+1}</td><td>${esc(r.name)}</td><td>${r.points.toFixed(2)}</td><td>${r.races}</td><td>${r.wins}</td></tr>`).join('')}</tbody></table>`;if(active)$('goModRunoffV40').onclick=()=>show('controlPage');if(pending)$('startModRunoffV40').onclick=()=>startModRunoffV40(pending);
}

/* Dispatch shared pages to Traditional v39 or Modified v40. */
const baseRenderGenerateV40=renderGenerate,baseRenderControlV40=renderControl,baseRenderResultsV40=renderResults,baseOpenStepV40=openStep;
renderGenerate=function(){return currentDivision==='mod'?renderModifiedGenerateV40():baseRenderGenerateV40()};
renderControl=function(){return currentDivision==='mod'?renderModifiedControlV40():baseRenderControlV40()};
renderResults=function(){return currentDivision==='mod'?renderModifiedResultsV40():baseRenderResultsV40()};
openStep=function(type,n){
 currentDivision=type;S.raceType=type==='mod'?'Modified':'Traditional';
 if(type==='mod'&&n===5){show('generatePage');renderGenerate();return}
 if(type==='mod'&&n===6){show('controlPage');renderControl();return}
 if(type==='mod'&&n===7){show('resultsPage');renderResults();return}
 return baseOpenStepV40(type,n);
};

renderHubs=function(){
 $('tradStats').innerHTML=statHtml(stats('trad'));
 const modAll=divRegs('mod'),modChecked=modAll.filter(r=>r.modCheckIn==='checked').length,modOfficial=modAll.filter(r=>modInspectionRawV40(r).approved&&modInspectionRawV40(r).raceClass==='official').length,modEx=modAll.filter(r=>modInspectionRawV40(r).approved&&modInspectionRawV40(r).raceClass==='exhibition').length;
 $('modStats').innerHTML=`<div class="stat"><b>${modAll.length}</b><span>Racers</span></div><div class="stat"><b>${modChecked}</b><span>Checked In</span></div><div class="stat"><b>${modOfficial}</b><span>Official</span></div><div class="stat"><b>${modEx}</b><span>Exhibition</span></div>`;
 const steps=['Racers','Check-In','Inspection','Race Cards','Generate Race','Race Control','Results'];
 $('tradSteps').innerHTML=steps.map((t,i)=>`<div class="step" data-step="${i+1}"><div class="stepNum">${i+1}</div><div class="stepTitle">${t}</div></div>`).join('');$('tradSteps').querySelectorAll('.step').forEach(s=>s.onclick=()=>openStep('trad',Number(s.dataset.step)));
 $('modSteps').innerHTML=steps.map((t,i)=>`<div class="step" data-step="${i+1}"><div class="stepNum">${i+1}</div><div class="stepTitle">${t}</div></div>`).join('');$('modSteps').querySelectorAll('.step').forEach(s=>s.onclick=()=>openStep('mod',Number(s.dataset.step)));
};

/* Make the v40 projector division-aware. */
openProjector=function(){
 ensureModifiedStateV40();S.raceType=currentDivision==='mod'?'Modified':'Traditional';if(currentDivision==='mod')S.modified.exhibition={active:false};persist();window.open('v40-projector.html?v=40-modified','mnltProjector','width=1500,height=900');
};
$('liveProjector').onclick=openProjector;

renderVisible();
})();
