async function loadStats(){
  try{
    const r=await fetch("/api/stats");
    if(!r.ok)return;
    const s=await r.json();
    document.querySelectorAll("[data-stat]").forEach(el=>{
      const key=el.dataset.stat;
      if(key in s) el.textContent=s[key];
    });
  }catch(e){}
}
loadStats();

document.querySelectorAll(".flash").forEach((el,i)=>{
  setTimeout(()=>{el.style.opacity="0";el.style.transform="translateY(-8px)";el.style.transition=".4s";setTimeout(()=>el.remove(),450)},4000+i*300);
});
