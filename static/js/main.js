document.addEventListener("DOMContentLoaded", () => {
  const isAuthenticated = false;
  if (!isAuthenticated) {
    document.body.classList.add("auth-locked");
  }

  const items = document.querySelectorAll(".reveal");
  setTimeout(() => {
    items.forEach(el => el.classList.add("visible"));
  }, 120);
});