(function(){
'use strict';

function offsetScoreV38(n,a){
  const counts=new Map();
  for(let i=0;i<a.length;i++)for(let j=0;j<a.length;j++)if(i!==j){
    const d=(a[j]-a[i]+n)%n;
    counts.set(d,(counts.get(d)||0)+1);
  }
  const vals=[...counts.values()];
  return {maxRepeat:Math.max(...vals),unique:counts.size,square:vals.reduce((s,v)=>s+v*v,0)};
}
function betterScoreV38(a,b){
  if(!b)return true;
  if(a.maxRepeat!==b.maxRepeat)return a.maxRepeat<b.maxRepeat;
  if(a.unique!==b.unique)return a.unique>b.unique;
  return a.square<b.square;
}
function chooseOffsetsV38(n){
  if(n<4)return null;
  let best=[0,1,2,3],bestScore=offsetScoreV38(n,best);
  for(let a=1;a<n-2;a++)for(let b=a+1;b<n-1;b++)for(let c=b+1;c<n;c++){
    const cur=[0,a,b,c],score=offsetScoreV38(n,cur);
    if(betterScoreV38(score,bestScore)){best=cur;bestScore=score;if(score.maxRepeat===1)return best;}
  }
  return best;
}

buildFairSchedule=function(ids){
  ids=Array.from(ids||[]);
  const n=ids.length,heats=[];
  if(n<2)return heats;
  if(n<4){
    for(let h=0;h<4;h++){
      const lanes=[null,null,null,null];
      ids.forEach((id,i)=>{lanes[(i+h)%4]=id});
      heats.push({id:h+1,round:null,lanes,results:[],scheduleEngine:'PerfectN-v38'});
    }
    return heats;
  }
  const offsets=chooseOffsetsV38(n);
  for(let h=0;h<n;h++){
    heats.push({id:h+1,round:null,lanes:offsets.map(o=>ids[(h+o)%n]),results:[],scheduleEngine:'PerfectN-v38',offsets:offsets.slice()});
  }
  return heats;
};

function verifyScheduleDetailedV38(heats,ids){
  heats=Array.isArray(heats)?heats:[];ids=Array.from(ids||[]);
  const n=ids.length,errors=[];
  if(n<2)return {ok:false,errors:['At least 2 racers are required.'],stats:{}};
  if(new Set(ids).size!==n)errors.push('Duplicate racer IDs found.');
  const idSet=new Set(ids),expectedHeats=n<4?4:n,expectedHeatSize=Math.min(n,4);
  if(heats.length!==expectedHeats)errors.push(`Expected ${expectedHeats} heats but found ${heats.length}.`);
  const races=new Map(ids.map(id=>[id,0]));
  const laneCounts=new Map(ids.map(id=>[id,[0,0,0,0]]));
  const opponents=new Map(ids.map(id=>[id,new Map()]));
  let badHeatCount=0,duplicateHeatCount=0,unknownCount=0,emptySlots=0;
  heats.forEach(h=>{
    const lanes=Array.isArray(h?.lanes)?h.lanes:[null,null,null,null];
    const active=lanes.filter(x=>x!==null&&x!==undefined&&x!=='');
    emptySlots+=Math.max(0,4-active.length);
    if(active.length!==expectedHeatSize)badHeatCount++;
    if(new Set(active).size!==active.length)duplicateHeatCount++;
    active.forEach(id=>{if(!idSet.has(id))unknownCount++});
    lanes.slice(0,4).forEach((id,l)=>{
      if(id===null||id===undefined||id==='')return;
      if(!idSet.has(id))return;
      races.set(id,(races.get(id)||0)+1);
      laneCounts.get(id)[l]++;
    });
    for(let i=0;i<active.length;i++)for(let j=i+1;j<active.length;j++){
      const a=active[i],b=active[j];if(!idSet.has(a)||!idSet.has(b))continue;
      opponents.get(a).set(b,(opponents.get(a).get(b)||0)+1);
      opponents.get(b).set(a,(opponents.get(b).get(a)||0)+1);
    }
  });
  if(badHeatCount)errors.push(`${badHeatCount} heat(s) have the wrong number of racers.`);
  if(duplicateHeatCount)errors.push(`${duplicateHeatCount} heat(s) contain the same racer more than once.`);
  if(unknownCount)errors.push('Unknown racer IDs are present in the schedule.');
  const badRaces=ids.filter(id=>races.get(id)!==4);
  if(badRaces.length)errors.push(`${badRaces.length} racer(s) do not have exactly 4 races.`);
  const badLanes=ids.filter(id=>laneCounts.get(id).some(v=>v!==1));
  if(badLanes.length)errors.push(`${badLanes.length} racer(s) do not use every lane exactly once.`);
  if(n>=4&&emptySlots!==0)errors.push(`${emptySlots} empty lane slot(s) found; none are needed with ${n} racers.`);
  const expectedUnique=Math.min(n-1,12),expectedEncounters=4*(Math.min(n,4)-1);
  const expectedMaxRepeat=n<=4?4:n<=6?3:n<=12?2:1;
  let minUnique=Infinity,maxUnique=-Infinity,maxPairRepeat=0,opponentPattern=null,patternMismatch=0,badEncounter=0;
  ids.forEach(id=>{
    const vals=[...opponents.get(id).values()].sort((a,b)=>b-a);
    const unique=vals.length,encounters=vals.reduce((s,v)=>s+v,0),maxRep=vals[0]||0;
    minUnique=Math.min(minUnique,unique);maxUnique=Math.max(maxUnique,unique);maxPairRepeat=Math.max(maxPairRepeat,maxRep);
    if(encounters!==expectedEncounters)badEncounter++;
    const pat=vals.join(',');if(opponentPattern===null)opponentPattern=pat;else if(pat!==opponentPattern)patternMismatch++;
  });
  if(minUnique!==expectedUnique||maxUnique!==expectedUnique)errors.push(`Opponent variety is not optimal. Expected ${expectedUnique} unique opponents per racer.`);
  if(maxPairRepeat>expectedMaxRepeat)errors.push(`Some opponents repeat ${maxPairRepeat} times; expected no more than ${expectedMaxRepeat}.`);
  if(badEncounter)errors.push(`${badEncounter} racer(s) have the wrong number of opponent encounters.`);
  if(patternMismatch)errors.push('Opponent repeat pattern is not equal for every racer.');
  return {ok:errors.length===0,errors,stats:{racers:n,heats:heats.length,emptySlots,minUnique,maxUnique,maxPairRepeat,expectedUnique,expectedMaxRepeat}};
}
window.mnltVerifyScheduleV38=verifyScheduleDetailedV38;
verifySchedule=function(heats,ids){return verifyScheduleDetailedV38(heats,ids).ok};

const baseRenderGenerateV38=renderGenerate;
renderGenerate=function(){
  baseRenderGenerateV38();
  if(!Array.isArray(S.heats)||!S.heats.length)return;
  const ids=S.racers.map(r=>r.id),v=verifyScheduleDetailedV38(S.heats,ids),status=document.getElementById('genStatus');
  if(status){
    status.innerHTML=v.ok
      ? `<div style="background:#10271d;border:2px solid #4e9b67;border-radius:10px;padding:12px"><div style="font-size:20px;font-weight:1000;color:#9ee7af">✓ RACE SCHEDULE VERIFIED</div><div class="muted" style="margin-top:5px">${v.stats.heats} heats • 4 races per racer • every lane once • ${v.stats.emptySlots} empty lanes • up to ${v.stats.maxPairRepeat} meeting(s) against the same opponent</div></div>`
      : `<div style="background:#29171b;border:2px solid #8d4a54;border-radius:10px;padding:12px"><div style="font-size:20px;font-weight:1000;color:#ff9da7">RACE SCHEDULE FAILED VERIFICATION</div><div class="muted" style="margin-top:5px">Race Control is locked until this is fixed.</div><ul>${v.errors.map(e=>`<li>${esc(e)}</li>`).join('')}</ul></div>`;
  }
  document.querySelectorAll('#scheduleList .scheduleHeat').forEach((d,i)=>{const t=d.querySelector('.heatTitle');if(t)t.textContent=`Heat ${i+1} of ${S.heats.length}`});
};

const baseRenderControlV38=renderControl;
renderControl=function(){
  if(Array.isArray(S.heats)&&S.heats.length){
    const v=verifyScheduleDetailedV38(S.heats,S.racers.map(r=>r.id));
    if(!v.ok){
      const host=document.getElementById('controlBody');
      host.innerHTML=`<div class="panel"><h2 class="red">RACE CONTROL LOCKED</h2><p>The schedule failed the race-day safety check.</p><ul>${v.errors.map(e=>`<li>${esc(e)}</li>`).join('')}</ul><div class="actions"><button class="btn primary" id="backGenerateV38">Go to Generate Race</button></div></div>`;
      document.getElementById('backGenerateV38').onclick=()=>show('generatePage');
      return;
    }
  }
  baseRenderControlV38();
  if(S.heats.length){const h=S.heats[S.current],t=document.querySelector('#controlBody .controlTitle');if(t&&h)t.textContent=`Heat ${h.id} of ${S.heats.length}`;}
};

const baseRenderProjectorV38=renderProjector;
renderProjector=function(){
  baseRenderProjectorV38();
  if(document.body.classList.contains('projectorOnly')&&S.heats.length){const h=S.heats[S.current],t=document.querySelector('#projectorView .projTitle');if(t&&h)t.textContent=`Heat ${h.id} of ${S.heats.length}`;}
};

const baseRenderResultsV38=renderResults;
renderResults=function(){
  if(S.heats.length){
    const v=verifyScheduleDetailedV38(S.heats,S.racers.map(r=>r.id));
    if(!v.ok){document.getElementById('resultsBody').innerHTML='<div class="panel"><h2 class="red">Results unavailable</h2><p>The race schedule failed verification.</p></div>';return;}
  }
  baseRenderResultsV38();
  const finished=S.heats.filter(h=>Array.isArray(h.results)&&h.results.length).length;
  if(S.heats.length&&finished<S.heats.length){
    const box=document.createElement('div');box.className='panel';box.style.borderColor='#d8a63d';box.innerHTML=`<b class="gold">PROVISIONAL RESULTS</b><div class="muted" style="margin-top:5px">${finished} of ${S.heats.length} heats are saved. Final places are not official yet.</div>`;
    document.getElementById('resultsBody').prepend(box);
  }
};

})();
