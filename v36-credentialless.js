(function(){
'use strict';
const CFG='mnltDerbyRegistrationBridgeV1';
try{
  const c=JSON.parse(localStorage.getItem(CFG)||'null');
  if(c&&c.url){
    const u=new URL(c.url);
    u.searchParams.delete('authuser');
    c.url=u.toString();
    localStorage.setItem(CFG,JSON.stringify(c));
  }
}catch(e){}

const nativeAppend=HTMLHeadElement.prototype.appendChild;
HTMLHeadElement.prototype.appendChild=function(node){
  try{
    if(node&&node.tagName==='SCRIPT'&&/^https:\/\/script\.google\.com\/macros\/s\//i.test(node.src)){
      const u=new URL(node.src);
      const cb=u.searchParams.get('callback');
      if(cb&&/^__mnltBridge_\d+_\d+$/.test(cb)){
        const frame=document.createElement('iframe');
        frame.style.display='none';
        frame.setAttribute('sandbox','allow-scripts');
        frame.setAttribute('credentialless','');
        try{frame.credentialless=true}catch(e){}
        const tag='mnltBridgeFrame_'+cb;
        let finished=false;
        const finish=function(ok,payload){
          if(finished)return;
          finished=true;
          window.removeEventListener('message',onMessage);
          try{frame.remove()}catch(e){}
          if(ok){
            const fn=window[cb];
            if(typeof fn==='function')fn(payload);
          }else if(typeof node.onerror==='function'){
            node.onerror(new Event('error'));
          }
        };
        const onMessage=function(ev){
          if(ev.source!==frame.contentWindow||!ev.data||ev.data.tag!==tag)return;
          if(ev.data.error)finish(false);
          else finish(true,ev.data.payload);
        };
        window.addEventListener('message',onMessage);
        const src=u.toString();
        frame.srcdoc='<!doctype html><meta charset="utf-8"><script>(function(){const cb='+JSON.stringify(cb)+',tag='+JSON.stringify(tag)+';window[cb]=function(d){parent.postMessage({tag:tag,payload:d},"*")};const s=document.createElement("script");s.src='+JSON.stringify(src)+';s.onerror=function(){parent.postMessage({tag:tag,error:true},"*")};document.head.appendChild(s)})();<\/script>';
        document.body.appendChild(frame);
        setTimeout(function(){finish(false)},17000);
        return node;
      }
    }
  }catch(e){}
  return nativeAppend.call(this,node);
};

function moveEmail(){
  const page=document.getElementById('registration');
  const panel=document.getElementById('emailBridgePanel');
  if(!page||!panel)return false;
  const nav=page.querySelector('.nav');
  if(nav&&panel.previousElementSibling!==nav)nav.insertAdjacentElement('afterend',panel);
  return true;
}
if(!moveEmail()){
  const obs=new MutationObserver(function(){if(moveEmail())obs.disconnect()});
  obs.observe(document.documentElement,{childList:true,subtree:true});
  setTimeout(function(){try{obs.disconnect()}catch(e){}},10000);
}
})();
