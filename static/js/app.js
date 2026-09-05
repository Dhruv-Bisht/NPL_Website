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


// Prevent the browser from briefly showing unstyled HTML during page navigation.
(function(){
  function showLoader(){ document.documentElement.classList.add('page-loading'); }
  function hideLoader(){ document.documentElement.classList.remove('page-loading'); }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', hideLoader, {once:true});
  } else {
    hideLoader();
  }

  window.addEventListener('pageshow', hideLoader);

  document.addEventListener('click', function(e){
    const link = e.target.closest('a');
    if(!link) return;
    if(link.target === '_blank' || link.hasAttribute('download')) return;
    const href = link.getAttribute('href');
    if(!href || href.startsWith('#') || href.startsWith('mailto:') || href.startsWith('tel:')) return;
    try {
      const url = new URL(link.href, window.location.href);
      if(url.origin === window.location.origin) showLoader();
    } catch(_) {}
  });

  document.addEventListener('submit', function(e){
    if(e.defaultPrevented) return;
    showLoader();
  });
})();
