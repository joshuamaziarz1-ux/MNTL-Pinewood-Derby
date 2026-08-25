(function(){
'use strict';
const nativeOpen=window.open.bind(window);
function projectorUrlV41(){return 'v41-projector.html?v=41-audience'}
window.open=function(url,name,features){
 if(typeof url==='string'&&url.includes('v40-projector.html'))url=projectorUrlV41();
 return nativeOpen(url,name,features);
};
openProjector=function(){
 try{
  if(typeof ensureModifiedStateV40==='function')ensureModifiedStateV40();
  S.raceType=currentDivision==='mod'?'Modified':'Traditional';
  if(currentDivision==='mod'&&S.modified)S.modified.exhibition={active:false};
  persist();
 }catch(e){}
 return nativeOpen(projectorUrlV41(),'mnltProjector','width=1500,height=900');
};
const live=document.getElementById('liveProjector');if(live)live.onclick=openProjector;
})();