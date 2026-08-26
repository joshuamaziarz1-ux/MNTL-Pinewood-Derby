(function(){
'use strict';
setTimeout(()=>{
 const save=document.getElementById('saveDerby');
 const panel=save?.closest('.panel');
 if(panel){
  const h=panel.querySelector('h2'),p=panel.querySelector('p.muted');
  if(h)h.textContent='Quick Backup Controls';
  if(p)p.textContent='v42 Full Backup includes your race progress and car photos. These buttons use the same full backup system shown above.';
 }
},0);
const basePersistV42Fix=persist;
persist=function(){
 try{basePersistV42Fix()}
 catch(e){
  console.error(e);
  try{window.MNLTBackupV42?.snapshot?.()}catch(_){}
  try{toast('SAVE ERROR — download a Full Derby Backup now.')}catch(_){}
  throw e;
 }
};
})();