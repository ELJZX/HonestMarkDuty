document.addEventListener("DOMContentLoaded", function () {
  const burger = document.getElementById("burger");
  const sidebar = document.getElementById("sidebar");
  const overlay = document.getElementById("overlay");
  if (burger && sidebar) {
    const toggle = () => {
      sidebar.classList.toggle("open");
      if (overlay) overlay.classList.toggle("show");
    };
    burger.addEventListener("click", toggle);
    if (overlay) overlay.addEventListener("click", toggle);
  }

  document.querySelectorAll("[data-confirm]").forEach(function (el) {
    el.addEventListener("submit", function (e) {
      if (!window.confirm(el.getAttribute("data-confirm"))) e.preventDefault();
    });
  });

  document.querySelectorAll("[data-auto-submit]").forEach(function (el) {
    el.addEventListener("change", function () {
      if (el.form) el.form.submit();
    });
  });
});
