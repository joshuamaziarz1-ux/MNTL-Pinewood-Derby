(function(){
'use strict';
const nativeOpen=window.open.bind(window);
function projectorUrlV41(){return 'v41-projector-live.html?v=41-audience-live'}
window.open=function(url,name,features){
 if(typeof url==='string'&&(url.includes('v40-projector.html')||url.includes('v41-projector.html')))url=projectorUrlV41();
 return nativeOpen(url,name,features);
};
openProjector=function(){
 try{
  S.raceType=currentDivision==='mod'?'Modified':'Traditional';
  if(currentDivision==='mod'&&S.modified)S.modified.exhibition={active:false};
  persist();
 }catch(e){}
 return nativeOpen(projectorUrlV41(),'mnltProjector','width=1500,height=900');
};
const live=document.getElementById('liveProjector');if(live)live.onclick=openProjector;
})();