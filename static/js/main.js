// Small progressive-enhancement layer.
// The backend remains authoritative for parking state.
setTimeout(() => {
    document.querySelectorAll(".flash").forEach(el => {
        el.style.transition = "opacity .4s";
        setTimeout(() => { el.style.opacity = "0"; }, 4500);
    });
}, 50);
