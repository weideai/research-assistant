document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) window.lucide.createIcons();

  const sidebar = document.querySelector("#sidebar");
  document.querySelector("#menu-toggle")?.addEventListener("click", () => sidebar?.classList.toggle("open"));
  document.addEventListener("click", (event) => {
    if (window.innerWidth <= 820 && sidebar?.classList.contains("open") &&
        !sidebar.contains(event.target) && !event.target.closest("#menu-toggle")) sidebar.classList.remove("open");
  });

  document.querySelectorAll("form[data-confirm]").forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!window.confirm(form.dataset.confirm)) event.preventDefault();
    });
  });
  document.querySelectorAll(".flash-close").forEach((button) => {
    button.addEventListener("click", () => button.closest(".flash")?.remove());
  });
  document.querySelectorAll(".reveal-secret").forEach((button) => {
    button.addEventListener("click", () => {
      const input = button.closest(".secret-field")?.querySelector("input");
      if (!input) return;
      input.type = input.type === "password" ? "text" : "password";
      button.innerHTML = `<i data-lucide="${input.type === "password" ? "eye" : "eye-off"}"></i>`;
      if (window.lucide) window.lucide.createIcons();
    });
  });
  document.querySelectorAll(".copy-value").forEach((button) => {
    button.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(button.dataset.copy || "");
        const original = button.innerHTML;
        button.textContent = "已复制";
        window.setTimeout(() => {
          button.innerHTML = original;
          if (window.lucide) window.lucide.createIcons();
        }, 1600);
      } catch (_error) {
        window.alert("复制失败，请手动选择链接。");
      }
    });
  });
});
