document.addEventListener("DOMContentLoaded", function () {
  const csrfToken = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";

  // Мобильное меню
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

  // Всплывающие уведомления
  function hideToast(toast) {
    toast.classList.add("hide");
    setTimeout(() => toast.remove(), 300);
  }
  function attachToast(toast) {
    const closeBtn = toast.querySelector(".toast-close");
    if (closeBtn) closeBtn.addEventListener("click", () => hideToast(toast));
    setTimeout(() => hideToast(toast), 7000);
  }
  function showToast(message, type) {
    let stack = document.getElementById("toast-stack");
    if (!stack) {
      stack = document.createElement("div");
      stack.id = "toast-stack";
      stack.className = "toast-stack";
      document.body.appendChild(stack);
    }
    const toast = document.createElement("div");
    toast.className = "toast " + (type || "info");
    const text = document.createElement("span");
    text.className = "toast-text";
    text.textContent = message;
    const close = document.createElement("button");
    close.type = "button";
    close.className = "toast-close";
    close.setAttribute("aria-label", "Закрыть");
    close.textContent = "×";
    toast.appendChild(text);
    toast.appendChild(close);
    stack.appendChild(toast);
    attachToast(toast);
  }
  window.showToast = showToast;

  document.querySelectorAll(".toast").forEach(attachToast);

  // Живой таймер длительности открытой смены
  const shiftTimer = document.getElementById("shift-timer");
  if (shiftTimer) {
    const start = new Date(shiftTimer.dataset.start).getTime();
    const render = () => {
      const total = Math.max(0, Math.floor((Date.now() - start) / 1000));
      const hours = String(Math.floor(total / 3600)).padStart(2, "0");
      const minutes = String(Math.floor((total % 3600) / 60)).padStart(2, "0");
      const seconds = String(total % 60).padStart(2, "0");
      shiftTimer.textContent = hours + ":" + minutes + ":" + seconds;
    };
    render();
    setInterval(render, 1000);
  }

  // Уведомление, сохранённое перед перезагрузкой
  try {
    const pending = sessionStorage.getItem("hmd_toast");
    if (pending) {
      sessionStorage.removeItem("hmd_toast");
      const data = JSON.parse(pending);
      showToast(data.message, data.type);
    }
  } catch (e) {
    /* ignore */
  }

  // Простое подтверждение через window.confirm (удаления)
  document.querySelectorAll("form[data-confirm]").forEach(function (el) {
    el.addEventListener("submit", function (e) {
      if (!window.confirm(el.getAttribute("data-confirm"))) e.preventDefault();
    });
  });

  // Авто-отправка фильтров
  document.querySelectorAll("[data-auto-submit]").forEach(function (el) {
    el.addEventListener("change", function () {
      if (el.form) el.form.submit();
    });
  });

  // Модальное окно подтверждения
  const modal = document.getElementById("confirm-modal");
  let pendingForm = null;
  let pendingButton = null;

  function openModal(text, yesLabel) {
    if (!modal) return;
    document.getElementById("confirm-modal-text").textContent = text || "Вы уверены?";
    document.getElementById("confirm-modal-yes").textContent = yesLabel || "Да";
    modal.hidden = false;
  }
  function closeModal() {
    if (modal) modal.hidden = true;
    pendingForm = null;
    pendingButton = null;
  }

  // Кнопки-действия (AJAX без перехода на другую страницу)
  document.querySelectorAll("[data-action-url]").forEach(function (btn) {
    btn.addEventListener("click", function (e) {
      e.preventDefault();
      pendingButton = btn;
      openModal(btn.dataset.actionModal, btn.dataset.yesLabel);
    });
  });

  // Формы с модальным подтверждением (fallback)
  document.querySelectorAll("form[data-confirm-modal]").forEach(function (form) {
    form.addEventListener("submit", function (e) {
      if (form.dataset.confirmed === "1") return;
      e.preventDefault();
      pendingForm = form;
      openModal(form.getAttribute("data-confirm-modal"));
    });
  });

  function runAction(button) {
    const url = button.dataset.actionUrl;
    fetch(url, {
      method: "POST",
      headers: { "X-CSRFToken": csrfToken, "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
    })
      .then(function (res) {
        return res
          .json()
          .catch(function () {
            return {};
          })
          .then(function (data) {
            return { ok: res.ok && data.ok !== false, data: data };
          });
      })
      .then(function (result) {
        const message = result.data.message || (result.ok ? "Готово" : "Не удалось выполнить действие");
        try {
          sessionStorage.setItem(
            "hmd_toast",
            JSON.stringify({ message: message, type: result.ok ? "success" : "error" })
          );
        } catch (e) {
          /* ignore */
        }
        window.location.reload();
      })
      .catch(function () {
        showToast("Ошибка сети", "error");
      });
  }

  if (modal) {
    document.getElementById("confirm-modal-yes").addEventListener("click", function () {
      if (pendingButton) {
        const button = pendingButton;
        closeModal();
        runAction(button);
        return;
      }
      if (pendingForm) {
        const form = pendingForm;
        modal.hidden = true;
        pendingForm = null;
        form.dataset.confirmed = "1";
        form.submit();
        return;
      }
      closeModal();
    });
    document.getElementById("confirm-modal-no").addEventListener("click", closeModal);
    modal.addEventListener("click", function (event) {
      if (event.target === modal) closeModal();
    });
  }
});
