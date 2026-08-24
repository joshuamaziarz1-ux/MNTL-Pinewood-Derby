(function(){
'use strict';
const BRIDGE_CFG='mnltDerbyRegistrationBridgeV1';
const BRIDGE_IGNORED='mnltDerbyRegistrationIgnoredV1';
let bridgeIncoming=[],bridgeLastChecked='',bridgeBusy=false,bridgeTimer=null;

function injectStyle(){
 if(document.getElementById('mnltBridgeStyle'))return;
 const s=document.createElement('style');s.id='mnltBridgeStyle';s.textContent=`
.emailBridge{margin-top:14px}.emailBridgeHead{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap}.emailBridgeStatus{font-weight:1000;padding:8px 11px;border-radius:8px;background:#243b56}.emailBridgeStatus.ok{background:#173c29;color:#a8efbc}.emailBridgeStatus.bad{background:#3a2025;color:#ffb0b7}.emailBridgeSetup{display:grid;grid-template-columns:1fr 260px;gap:10px 12px;align-items:end;margin-top:12px}.emailBridgeSetup label{margin:0}.emailBridgeSetup input{margin:5px 0 0}.emailBridgeButtons{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}.incomingReg{background:#0e1c2c;border:2px solid #d8a63d;border-radius:12px;padding:13px;margin:10px 0}.newTag{display:inline-block;background:#d8a63d;color:#111820;border-radius:999px;padding:5px 9px;font-size:12px;font-weight:1000;margin-bottom:7px}.incomingGrid{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center}.incomingName{font-size:20px;font-weight:1000}.incomingMeta{color:#9dafc1;font-size:14px;margin-top:4px}.incomingActions{display:flex;gap:7px;align-items:center;flex-wrap:wrap}.incomingActions select{width:auto;min-width:150px;margin:0}.bridgeTiny{color:#9dafc1;font-size:13px;margin-top:7px}.bridgeKey{font-family:monospace}.emailBridgeEmpty{color:#9dafc1;padding:8px 0}.homeNew{display:inline-block;margin-left:7px;background:#d8a63d;color:#111820;border-radius:999px;padding:3px 7px;font-size:11px;font-weight:1000}@media(max-width:850px){.emailBridgeSetup,.incomingGrid{grid-template-columns:1fr}.incomingActions{justify-content:flex-start}}
 `;document.head.appendChild(s)
}
function createPanel(){
 if(document.getElementById('emailBridgePanel'))return;
 const page=document.getElementById('registration');if(!page)return;
 const p=document.createElement('div');p.className='panel emailBridge';p.id='emailBridgePanel';p.innerHTML=`<div class="emailBridgeHead"><div><h2 style="margin-bottom:4px">Email Registration</h2><div class="muted">Checks SnapPages derby signups through the free Apps Script bridge.</div></div><div id="emailBridgeStatus" class="emailBridgeStatus">Not set up</div></div><div class="emailBridgeSetup"><div><label>Apps Script Web App URL</label><input id="bridgeUrl" placeholder="https://script.google.com/macros/s/.../exec"></div><div><label>Bridge Key</label><input id="bridgeKey" class="bridgeKey" type="password" placeholder="Paste bridge key"></div></div><div class="emailBridgeButtons"><button class="btn primary" id="saveBridge">Save Connection</button><button class="btn" id="checkBridge">Check Now</button><button class="btn" id="disconnectBridge">Disconnect</button></div><div id="bridgeTiny" class="bridgeTiny">Checks once an hour while the manager is open. Check Now works anytime.</div><div id="incomingRegs"></div>`;page.appendChild(p);
 document.getElementById('saveBridge').onclick=saveBridgeConnection;
 document.getElementById('checkBridge').onclick=()=>checkBridge(true);
 document.getElementById('disconnectBridge').onclick=disconnectBridge;
}
function bridgeConfig(){try{return JSON.parse(localStorage.getItem(BRIDGE_CFG)||'null')}catch(e){return null}}
function ignoredBridgeIds(){try{return JSON.parse(localStorage.getItem(BRIDGE_IGNORED)||'[]')}catch(e){return[]}}
function setIgnoredBridgeIds(a){localStorage.setItem(BRIDGE_IGNORED,JSON.stringify(Array.from(new Set(a)).slice(-500)))}
function normalizeBridgeUrl(v){v=String(v||'').trim();if(!/^https:\/\/script\.google\.com\/macros\/s\//i.test(v)||!/\/exec(?:[?#]|$)/i.test(v))return'';return v.split('#')[0]}
function bridgeKnownIds(){const a=new Set(ignoredBridgeIds());S.registrations.forEach(r=>{if(r.sourceMessageId)a.add(String(r.sourceMessageId));if(r.gmailMessageId)a.add(String(r.gmailMessageId))});return a}
function bridgeStatus(text,kind){const e=document.getElementById('emailBridgeStatus');if(!e)return;e.textContent=text;e.className='emailBridgeStatus '+(kind||'')}
function cleanupJsonp(name,script,timer){clearTimeout(timer);try{delete window[name]}catch(e){window[name]=undefined}if(script)script.remove()}
function bridgeJsonp(url,key){return new Promise((resolve,reject)=>{const name='__mnltBridge_'+Date.now()+'_'+Math.floor(Math.random()*1e6),script=document.createElement('script'),sep=url.includes('?')?'&':'?';let done=false;const timer=setTimeout(()=>{if(done)return;done=true;cleanupJsonp(name,script,timer);reject(new Error('timeout'))},18000);window[name]=data=>{if(done)return;done=true;cleanupJsonp(name,script,timer);resolve(data)};script.onerror=()=>{if(done)return;done=true;cleanupJsonp(name,script,timer);reject(new Error('load'))};script.src=url+sep+'key='+encodeURIComponent(key)+'&callback='+encodeURIComponent(name)+'&_='+Date.now();script.referrerPolicy='no-referrer';document.head.appendChild(script)})}
function renderBridge(){
 createPanel();const cfg=bridgeConfig(),u=document.getElementById('bridgeUrl'),k=document.getElementById('bridgeKey'),tiny=document.getElementById('bridgeTiny'),host=document.getElementById('incomingRegs');if(!u||!k||!host)return;
 if(document.activeElement!==u)u.value=cfg?.url||'';if(document.activeElement!==k)k.value=cfg?.key||'';
 if(bridgeBusy)bridgeStatus('Checking…');else if(cfg?.url&&cfg?.key)bridgeStatus(bridgeLastChecked?'Connected':'Ready','ok');else bridgeStatus('Not set up');
 tiny.textContent=cfg?.url&&cfg?.key?(bridgeLastChecked?`Last checked ${bridgeLastChecked}. Automatic check is hourly while the manager is open.`:'Connected. Automatic check is hourly while the manager is open.'):'Paste the Web App URL and Bridge Key from the free Apps Script setup.';
 host.innerHTML='';
 if(bridgeIncoming.length){bridgeIncoming.forEach((x,i)=>{const d=document.createElement('div');d.className='incomingReg';const div=['Traditional','Modified','Both'].includes(x.division)?x.division:'Traditional';d.innerHTML=`<div class="newTag">NEW REGISTRATION</div><div class="incomingGrid"><div><div class="incomingName">${esc(x.name||'Unnamed Racer')}</div><div class="incomingMeta">${esc(x.email||x.phone||'No contact shown')} • ${esc(x.choice||x.division||'Division not recognized')}</div></div><div class="incomingActions"><select class="incomingDivision"><option ${div==='Traditional'?'selected':''}>Traditional</option><option ${div==='Modified'?'selected':''}>Modified</option><option ${div==='Both'?'selected':''}>Both</option></select><button class="btn good addIncoming">ADD RACER</button><button class="btn ignoreIncoming">IGNORE</button></div></div>`;d.querySelector('.addIncoming').onclick=()=>addIncomingRegistration(i,d.querySelector('.incomingDivision').value);d.querySelector('.ignoreIncoming').onclick=()=>ignoreIncomingRegistration(i);host.appendChild(d)})}else if(cfg?.url&&cfg?.key)host.innerHTML='<div class="emailBridgeEmpty">No new signups waiting.</div>';
 const homeBtn=document.querySelector('#home [data-go="registration"]');if(homeBtn)homeBtn.innerHTML=bridgeIncoming.length?`Registration <span class="homeNew">${bridgeIncoming.length} NEW</span>`:'Registration'
}
async function checkBridge(manual=false){
 const cfg=bridgeConfig();if(!cfg?.url||!cfg?.key){if(manual)toast('Set up the email connection first.');renderBridge();return}if(bridgeBusy)return;
 bridgeBusy=true;renderBridge();
 try{const data=await bridgeJsonp(cfg.url,cfg.key);if(!data||data.ok!==true)throw new Error(data?.error||'bridge');const known=bridgeKnownIds(),existingNames=new Set(S.registrations.map(r=>String(r.name||'').trim().toLowerCase()));bridgeIncoming=(Array.isArray(data.registrations)?data.registrations:[]).filter(x=>x&&x.messageId&&!known.has(String(x.messageId))&&!existingNames.has(String(x.name||'').trim().toLowerCase())).sort((a,b)=>String(a.receivedAt||'').localeCompare(String(b.receivedAt||'')));bridgeLastChecked=new Date().toLocaleTimeString([],{hour:'numeric',minute:'2-digit'});if(manual)toast(bridgeIncoming.length?`${bridgeIncoming.length} new registration${bridgeIncoming.length===1?'':'s'} found.`:'No new registrations.')}catch(e){bridgeStatus('Connection problem','bad');if(manual)toast('Could not check registration email. Check the Web App URL and Bridge Key.')}finally{bridgeBusy=false;renderBridge()}
}
function saveBridgeConnection(){const url=normalizeBridgeUrl(document.getElementById('bridgeUrl').value),key=document.getElementById('bridgeKey').value.trim();if(!url){toast('Paste the Apps Script Web App URL ending in /exec.');return}if(!key){toast('Paste the Bridge Key.');return}localStorage.setItem(BRIDGE_CFG,JSON.stringify({url,key}));bridgeLastChecked='';renderBridge();toast('Email connection saved.');checkBridge(true)}
function disconnectBridge(){localStorage.removeItem(BRIDGE_CFG);bridgeIncoming=[];bridgeLastChecked='';renderBridge();toast('Email connection removed from this device.')}
function ignoreIncomingRegistration(i){const x=bridgeIncoming[i];if(!x)return;const ids=ignoredBridgeIds();ids.push(String(x.messageId));setIgnoredBridgeIds(ids);bridgeIncoming.splice(i,1);renderBridge()}
function addIncomingRegistration(i,division){
 const x=bridgeIncoming[i];if(!x)return;const name=String(x.name||'').trim();if(!name){toast('That signup is missing a racer name.');return}if(regDuplicate(name,null)){toast('That racer is already registered.');ignoreIncomingRegistration(i);return}
 const affectsTrad=division==='Traditional'||division==='Both';mutate(()=>{const r={id:Date.now()+Math.floor(Math.random()*100000),name,age:'',contact:String(x.email||x.phone||'').trim(),email:String(x.email||'').trim(),phone:String(x.phone||'').trim(),division,tradCar:'',modCar:'',status:'Registered',date:String(x.receivedAt||new Date().toISOString()).slice(0,10),notes:'Imported from SnapPages registration email',rulesSent:false,tradNo:null,modNo:null,tradRacerId:null,modRacerId:null,tradCheckIn:'waiting',modCheckIn:'waiting',sourceMessageId:String(x.messageId)};S.registrations.push(r);syncRegEntries(r);if(affectsTrad&&S.heats.length)clearTraditionalRace()});bridgeIncoming.splice(i,1);renderBridge();toast(`${name} added.`)
}
function startBridgePolling(){clearInterval(bridgeTimer);const cfg=bridgeConfig();if(cfg?.url&&cfg?.key){setTimeout(()=>checkBridge(false),1200);bridgeTimer=setInterval(()=>checkBridge(false),3600000)}}

injectStyle();createPanel();
const originalRenderVisible=renderVisible;renderVisible=function(){originalRenderVisible();renderBridge()};
renderBridge();startBridgePolling();
})();
