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

  // Шаблоны быстрого добавления оборудования
  const OPTIONAL_FIELDS = ["print_head"];
  const presetButtons = document.querySelectorAll("[data-preset]");
  if (presetButtons.length) {
    OPTIONAL_FIELDS.forEach(function (name) {
      const row = document.querySelector('.form-row[data-field="' + name + '"]');
      if (row) row.hidden = true;
    });
  }
  presetButtons.forEach(function (btn) {
    btn.addEventListener("click", function () {
      function setValue(id, value) {
        const el = document.getElementById(id);
        if (el && value) el.value = value;
      }
      setValue("id_name", btn.dataset.name);
      setValue("id_manufacturer", btn.dataset.manufacturer);
      setValue("id_model_name", btn.dataset.model);
      const category = document.getElementById("id_category");
      if (category && btn.dataset.category) {
        const want = btn.dataset.category.toLowerCase();
        Array.prototype.forEach.call(category.options, function (opt) {
          if (opt.text.trim().toLowerCase() === want) category.value = opt.value;
        });
      }
      const visible = (btn.dataset.fields || "")
        .split(",")
        .map(function (s) { return s.trim(); });
      OPTIONAL_FIELDS.forEach(function (name) {
        const row = document.querySelector('.form-row[data-field="' + name + '"]');
        if (row) row.hidden = visible.indexOf(name) === -1;
      });
      presetButtons.forEach(function (b) {
        b.classList.toggle("active", b === btn);
      });
    });
  });

  // Перетаскивание карточек ([data-sortable]) с сохранением порядка
  document.querySelectorAll("[data-sortable]").forEach(function (list) {
    const form = document.getElementById(list.dataset.form);
    const toggle = document.getElementById(list.dataset.toggle);
    const cancel = document.getElementById(list.dataset.cancel);
    const hint = document.getElementById(list.dataset.hint);
    const orderInput = document.getElementById(list.dataset.order);
    const itemSelector = list.dataset.item || ".line-card";
    const idAttr = list.dataset.idAttr || "lineId";
    const editActions = list.dataset.actions
      ? document.querySelectorAll(list.dataset.actions)
      : [];
    let editing = false;
    let dragged = null;

    function cards() {
      return Array.prototype.slice.call(list.querySelectorAll(itemSelector));
    }

    function setEdit(on) {
      editing = on;
      list.classList.toggle("edit-mode", on);
      cards().forEach(function (card) {
        card.setAttribute("draggable", on ? "true" : "false");
      });
      if (toggle) toggle.hidden = on;
      editActions.forEach(function (btn) { btn.hidden = !on; });
      if (hint) hint.hidden = !on;
    }

    if (toggle) toggle.addEventListener("click", function () { setEdit(true); });
    if (cancel) cancel.addEventListener("click", function () { setEdit(false); });

    list.addEventListener("dragstart", function (e) {
      if (!editing) return;
      const card = e.target.closest(itemSelector);
      if (!card) return;
      dragged = card;
      e.dataTransfer.effectAllowed = "move";
      try { e.dataTransfer.setData("text/plain", card.dataset[idAttr] || ""); } catch (err) { /* ignore */ }
      // Прячем исходную карточку после того, как браузер снимет drag-image
      setTimeout(function () { card.classList.add("dragging"); }, 0);
    });

    list.addEventListener("dragend", function () {
      if (dragged) dragged.classList.remove("dragging");
      dragged = null;
    });

    list.addEventListener("dragover", function (e) {
      if (!editing || !dragged) return;
      e.preventDefault();
      const items = cards().filter(function (c) { return c !== dragged; });
      if (!items.length) return;
      // Для расчёта вставки карточка «по факту» вдвое короче:
      // решаем по центральной зоне (половина высоты/ширины), а не по краям.
      function isBefore(cursorX, cursorY, rect) {
        const cx = rect.left + rect.width / 2;
        const cy = rect.top + rect.height / 2;
        const halfH = rect.height / 4;
        if (cursorY < cy - halfH) return true;
        if (cursorY > cy + halfH) return false;
        return cursorX < cx;
      }
      let ref = null;
      for (let i = 0; i < items.length; i++) {
        if (isBefore(e.clientX, e.clientY, items[i].getBoundingClientRect())) {
          ref = items[i];
          break;
        }
      }
      if (ref) {
        list.insertBefore(dragged, ref);
      } else {
        list.appendChild(dragged);
      }
    });

    if (form) {
      form.addEventListener("submit", function () {
        if (orderInput) {
          orderInput.value = cards()
            .map(function (c) { return c.dataset[idAttr]; })
            .join(",");
        }
      });
    }
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
