(function(){
'use strict';
const CFG='mnltDerbyRegistrationBridgeV1';
let mailRows=[];
let pending=null;
let refreshing=false;

function esc37(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function cfg37(){try{return JSON.parse(localStorage.getItem(CFG)||'null')}catch(e){return null}}
function bridgeCall37(params){
 return new Promise((resolve,reject)=>{
  const cfg=cfg37();
  if(!cfg?.url||!cfg?.key){reject(new Error('not configured'));return}
  const cb='__mnltBridge_'+Date.now()+'_'+Math.floor(Math.random()*1e6);
  const s=document.createElement('script');
  const u=new URL(cfg.url);
  u.searchParams.set('key',cfg.key);
  u.searchParams.set('callback',cb);
  u.searchParams.set('_',Date.now());
  Object.entries(params||{}).forEach(([k,v])=>u.searchParams.set(k,String(v??'')));
  let done=false;
  const timer=setTimeout(()=>finish(false,new Error('timeout')),18000);
  function cleanup(){clearTimeout(timer);try{delete window[cb]}catch(e){window[cb]=undefined}try{s.remove()}catch(e){}}
  function finish(ok,val){if(done)return;done=true;cleanup();ok?resolve(val):reject(val)}
  window[cb]=data=>finish(true,data);
  s.onerror=()=>finish(false,new Error('load'));
  s.src=u.toString();
  s.referrerPolicy='no-referrer';
  document.head.appendChild(s);
 });
}

async function refresh37(){
 if(refreshing)return;
 refreshing=true;
 try{
  const data=await bridgeCall37({});
  if(data?.ok===true&&Array.isArray(data.registrations))mailRows=data.registrations;
 }catch(e){}
 finally{refreshing=false;relabel37()}
}

function findMail37(card){
 const name=String(card?.querySelector('.incomingName')?.textContent||'').trim().toLowerCase();
 const meta=String(card?.querySelector('.incomingMeta')?.textContent||'').toLowerCase();
 return mailRows.find(x=>String(x.name||'').trim().toLowerCase()===name&&(x.email?meta.includes(String(x.email).toLowerCase()):true))||
        mailRows.find(x=>String(x.name||'').trim().toLowerCase()===name)||null;
}

function ensureReviewBox37(){
 if(document.getElementById('emailReviewBox37'))return document.getElementById('emailReviewBox37');
 const formPanel=document.getElementById('regTitle')?.closest('.panel');
 if(!formPanel)return null;
 const box=document.createElement('div');
 box.id='emailReviewBox37';
 box.style.cssText='display:none;background:#0e1c2c;border:2px solid #d8a63d;border-radius:10px;padding:12px;margin-bottom:14px';
 formPanel.insertBefore(box,formPanel.firstChild);
 return box;
}

function showPending37(){
 const box=ensureReviewBox37();
 if(!box)return;
 if(!pending){box.style.display='none';box.innerHTML='';return}
 const contact=[pending.email,pending.phone].filter(Boolean).join(' • ');
 box.style.display='block';
 box.innerHTML=`<div style="font-weight:1000;font-size:18px;margin-bottom:5px">Review Email Registration</div><div style="color:#9dafc1">${esc37(pending.name)}${contact?' • '+esc37(contact):''}</div><label style="display:flex;align-items:center;gap:8px;margin-top:9px"><input id="makeDraft37" type="checkbox" checked style="width:auto;margin:0"> Create Gmail confirmation draft after saving</label><div style="color:#9dafc1;font-size:13px;margin-top:6px">Review the fields below. Add the car name if you have it, then save.</div>`;
 const b=document.getElementById('saveReg');
 if(b)b.textContent='Save Racer + Create Email Draft';
 const c=document.getElementById('makeDraft37');
 if(c)c.onchange=()=>{if(b)b.textContent=c.checked?'Save Racer + Create Email Draft':'Save Racer'};
}

function clearPending37(){
 pending=null;
 showPending37();
 const title=document.getElementById('regTitle');if(title&&title.textContent==='Review Registration')title.textContent='Add Registration';
 const b=document.getElementById('saveReg');if(b&&!window.editingRegId)b.textContent='Add Racer';
}

function review37(x,division){
 if(!x)return;
 if(typeof resetRegForm==='function')resetRegForm();
 pending={...x,division:division||x.division||'Traditional'};
 const set=(id,val)=>{const e=document.getElementById(id);if(e)e.value=val??''};
 set('regName',x.name||'');
 set('regAge','');
 set('regContact',[x.email,x.phone].filter(Boolean).join(' | '));
 set('regDivision',pending.division);
 set('regTradCar','');
 set('regModCar','');
 set('regStatus','Registered');
 set('regDate',String(x.receivedAt||new Date().toISOString()).slice(0,10));
 set('regNotes','Imported from SnapPages registration email');
 const rules=document.getElementById('regRules');if(rules)rules.checked=false;
 if(typeof updateDivisionFields==='function')updateDivisionFields();
 const title=document.getElementById('regTitle');if(title)title.textContent='Review Registration';
 showPending37();
 const formPanel=title?.closest('.panel');if(formPanel)formPanel.scrollIntoView({behavior:'smooth',block:'start'});
}

async function createDraft37(p,r){
 try{
  const data=await bridgeCall37({
   action:'createDraft',
   messageId:p.messageId||'',
   division:r.division||p.division||'Traditional',
   tradCar:r.tradCar||'',
   modCar:r.modCar||''
  });
  if(data?.ok===true&&data?.draftCreated){
   const miss=Array.isArray(data.missingAttachments)?data.missingAttachments:[];
   if(miss.length)toast('Racer saved and Gmail draft created. Rule PDF attachment needs attention.');
   else toast('Racer saved. Gmail confirmation draft created.');
  }else{
   toast('Racer saved. Update Apps Script to v37 to create the Gmail draft.');
  }
 }catch(e){toast('Racer saved, but the Gmail draft could not be created.')}
}

function installSaveWrap37(){
 const b=document.getElementById('saveReg');
 if(!b||b.dataset.v37Wrapped)return;
 b.dataset.v37Wrapped='1';
 const base=b.onclick;
 b.onclick=function(ev){
  if(!pending){return typeof base==='function'?base.call(this,ev):undefined}
  const p={...pending,division:document.getElementById('regDivision')?.value||pending.division};
  const wantDraft=document.getElementById('makeDraft37')?.checked!==false;
  const before=new Set((S.registrations||[]).map(r=>r.id));
  const wantedName=String(document.getElementById('regName')?.value||'').trim().toLowerCase();
  if(typeof base==='function')base.call(this,ev);
  const saved=(S.registrations||[]).find(r=>!before.has(r.id)&&String(r.name||'').trim().toLowerCase()===wantedName);
  if(!saved)return;
  saved.sourceMessageId=String(p.messageId||'');
  saved.email=String(p.email||'').trim();
  saved.phone=String(p.phone||'').trim();
  if(!saved.notes)saved.notes='Imported from SnapPages registration email';
  if(typeof persist==='function')persist();
  pending=null;
  showPending37();
  b.textContent='Add Racer';
  document.querySelectorAll('.incomingReg').forEach(card=>{const n=String(card.querySelector('.incomingName')?.textContent||'').trim().toLowerCase();if(n===wantedName)card.remove()});
  if(wantDraft)createDraft37(p,saved);else toast('Racer saved.');
  setTimeout(()=>{refresh37();document.getElementById('checkBridge')?.click()},500);
 };
 const c=document.getElementById('cancelReg');
 if(c&&!c.dataset.v37Wrapped){
  c.dataset.v37Wrapped='1';
  const baseCancel=c.onclick;
  c.onclick=function(ev){clearPending37();return typeof baseCancel==='function'?baseCancel.call(this,ev):undefined};
 }
}

function relabel37(){
 document.querySelectorAll('.addIncoming').forEach(b=>{b.textContent='REVIEW';b.title='Fill the registration form so you can review it before saving'});
 installSaveWrap37();
 ensureReviewBox37();
}

document.addEventListener('click',function(e){
 const b=e.target.closest('.addIncoming');
 if(!b)return;
 e.preventDefault();
 e.stopPropagation();
 e.stopImmediatePropagation();
 const card=b.closest('.incomingReg');
 const division=card?.querySelector('.incomingDivision')?.value||'Traditional';
 const found=findMail37(card);
 if(found){review37(found,division);return}
 refresh37().then(()=>{const x=findMail37(card);if(x)review37(x,division);else toast('Could not load that registration. Click Check Now and try again.')});
},true);

document.getElementById('checkBridge')?.addEventListener('click',()=>setTimeout(refresh37,700));
const obs=new MutationObserver(relabel37);obs.observe(document.documentElement,{childList:true,subtree:true});
relabel37();
setTimeout(refresh37,900);
setInterval(refresh37,3600000);
})();
