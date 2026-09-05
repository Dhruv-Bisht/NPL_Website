var player = document.getElementById("player");

player.addEventListener("click",function(){
    window.location.href="/player";
})

document.getElementById("captain").addEventListener("click",function(){
    window.location.href="/captain";
})

document.getElementById("teams").addEventListener('click',function(){
    window.location.href="/teams";
})

document.getElementById("auction").addEventListener('click',function(){
    window.location.href="/auction";
})

document.getElementById("register_player").addEventListener('click',function(){
    window.location.href="/register_player";
})