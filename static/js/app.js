document.addEventListener("DOMContentLoaded", function () {
  const csrfToken = (document.querySelector('meta[name="csrf-token"]') || {}).content || "";

  // Оформление: классика ↔ стиль Apple (выбор запоминается в cookie и localStorage)
  const root = document.documentElement;
  const themeButton = document.getElementById("theme-toggle");
  const themeKey = "hmd_style";

  function currentTheme() {
    return root.getAttribute("data-theme") === "classic" ? "classic" : "apple";
  }

  function applyTheme(theme, persist) {
    root.setAttribute("data-theme", theme);
    if (persist) {
      document.cookie =
        themeKey + "=" + theme + "; path=/; max-age=31536000; SameSite=Lax";
      try {
        localStorage.setItem(themeKey, theme);
      } catch (error) {
        /* localStorage может быть недоступен */
      }
    }
    if (themeButton) {
      const nextLabel =
        theme === "apple"
          ? "Вернуть классическое оформление"
          : "Включить оформление в стиле Apple";
      themeButton.title = nextLabel;
      themeButton.setAttribute("aria-label", nextLabel);
      themeButton.setAttribute("aria-pressed", theme === "apple" ? "true" : "false");
    }
    window.dispatchEvent(
      new CustomEvent("hmd-theme-change", { detail: { theme: theme } })
    );
  }

  if (themeButton) {
    applyTheme(currentTheme(), false);
    themeButton.addEventListener("click", function () {
      applyTheme(currentTheme() === "apple" ? "classic" : "apple", true);
    });
  }

  window.addEventListener("storage", function (event) {
    if (
      event.key === themeKey &&
      (event.newValue === "apple" || event.newValue === "classic")
    ) {
      applyTheme(event.newValue, false);
    }
  });

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

  // Живой поиск по складу (AJAX, без перезагрузки, фокус не теряется)
  document.querySelectorAll("[data-live-search]").forEach(function (el) {
    let timer = null;
    el.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        const form = el.form;
        if (!form) return;
        const params = new URLSearchParams(new FormData(form)).toString();
        const url = window.location.pathname + (params ? "?" + params : "");
        fetch(url, { headers: { "X-Requested-With": "XMLHttpRequest" } })
          .then(function (r) { return r.text(); })
          .then(function (html) {
            const box = document.getElementById("items-results");
            if (box) box.innerHTML = html;
          })
          .catch(function () {});
      }, 250);
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

  // Реальные камеры: кадры по WebSocket напрямую с камеры (как в её веб-интерфейсе).
  // ws://<ip>/ws/monitor_image (subprotocol = uuid) — binary JPEG + text-метаданные (нужен ack);
  // ws://<ip>/ws/monitor_control (тот же uuid) — команды качества.
  function camUuid() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
      const r = (Math.random() * 16) | 0;
      return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
    });
  }

  function drawCameraFrame(box, canvas, blob) {
    createImageBitmap(blob)
      .then(function (bmp) {
        canvas.width = bmp.width;
        canvas.height = bmp.height;
        canvas.getContext("2d").drawImage(bmp, 0, 0);
        bmp.close();
        box.classList.add("has-img");
        canvas.classList.add("loaded");
      })
      .catch(function () {});
  }

  function startCamera(box) {
    const ip = box.getAttribute("data-cam-ip");
    const canvas = box.querySelector("canvas");
    if (!ip || !canvas) return;
    const proto = location.protocol === "https:" ? "wss://" : "ws://";

    function connect() {
      if (!box.isConnected) return;
      const uuid = camUuid();
      let lastImage = null;
      let control = null;
      let image;
      try {
        image = new WebSocket(proto + ip + "/ws/monitor_image", uuid);
      } catch (e) {
        setTimeout(connect, 5000);
        return;
      }
      image.binaryType = "blob";
      image.onopen = function () {
        try {
          control = new WebSocket(proto + ip + "/ws/monitor_control", uuid);
          control.onopen = function () {
            control.send("IMG_SEND_ALL");
            control.send("QUALITY_MEDIUM");
          };
          control.onerror = function () {};
        } catch (e) { /* ignore */ }
      };
      image.onmessage = function (ev) {
        if (ev.data instanceof Blob) {
          lastImage = ev.data;
          return;
        }
        try {
          const meta = JSON.parse(ev.data);
          if (lastImage) drawCameraFrame(box, canvas, lastImage);
          if (image.readyState === WebSocket.OPEN) {
            image.send(
              JSON.stringify({ ack: true, imageId: meta.imageId, phaseId: meta.phaseId })
            );
          }
        } catch (e) { /* ignore */ }
      };
      image.onerror = function () {};
      image.onclose = function () {
        if (control) {
          try { control.close(); } catch (e) { /* ignore */ }
        }
        if (box.isConnected) setTimeout(connect, 5000);
      };
    }

    connect();
  }

  document.querySelectorAll("[data-cam-ip]").forEach(startCamera);

  // Увеличение кадра камеры — родной веб-интерфейс камеры
  (function () {
    const box = document.getElementById("cam-lightbox");
    if (!box) return;
    const frame = document.getElementById("cam-lightbox-frame");
    const caption = document.getElementById("cam-lightbox-cap");

    function close() {
      box.hidden = true;
      frame.removeAttribute("src");
    }

    function open(ip, text) {
      caption.textContent = text || "";
      frame.src = "http://" + ip + "/monitor";
      box.hidden = false;
    }

    document.querySelectorAll("[data-cam-open]").forEach(function (el) {
      el.addEventListener("click", function () {
        const ip = el.getAttribute("data-cam-ip");
        if (ip) open(ip, el.getAttribute("data-cam-caption"));
      });
    });
    box.addEventListener("click", function (e) {
      if (e.target === box || e.target.hasAttribute("data-cam-close")) close();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") close();
    });
  })();

  // Принтеры: открытие веб-интерфейса принтера по IP
  (function () {
    const box = document.getElementById("printer-lightbox");
    if (!box) return;
    const frame = document.getElementById("printer-lightbox-frame");
    const caption = document.getElementById("printer-lightbox-cap");

    function close() {
      box.hidden = true;
      frame.removeAttribute("src");
    }

    function open(ip, text) {
      caption.textContent = text || "";
      frame.src = "http://" + ip + "/";
      box.hidden = false;
    }

    document.querySelectorAll("[data-printer-open]").forEach(function (el) {
      el.addEventListener("click", function () {
        const ip = el.getAttribute("data-printer-ip");
        if (ip) open(ip, el.getAttribute("data-printer-caption"));
      });
    });
    box.addEventListener("click", function (e) {
      if (e.target === box || e.target.hasAttribute("data-printer-close")) close();
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") close();
    });
  })();

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
        if (result.ok && result.data) {
          if (result.data.briefing) {
            showBriefing(result.data.briefing);
            return;
          }
          if (Array.isArray(result.data.events)) {
            showBriefing(result.data.events);
            return;
          }
        }
        window.location.reload();
      })
      .catch(function () {
        window.location.reload();
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

  // Модальное окно сводки при приёме смены
  const eventsModal = document.getElementById("events-modal");

  function makeElement(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function renderPlainEvents(list, events, emptyText) {
    list.innerHTML = "";
    if (!events || !events.length) {
      list.appendChild(makeElement("li", "change-empty", emptyText));
      return;
    }
    events.forEach(function (item) {
      const li = document.createElement("li");
      const obj = item && typeof item === "object" ? item : { text: item };
      li.appendChild(document.createTextNode(obj.text || ""));
      if (obj.qty) {
        li.appendChild(document.createTextNode(" "));
        const span = makeElement(
          "span",
          "event-qty" + (obj.tone ? " event-" + obj.tone : ""),
          obj.qty
        );
        li.appendChild(span);
      }
      list.appendChild(li);
    });
  }

  function renderChanges(container, changes) {
    container.innerHTML = "";
    if (!changes || !changes.length) {
      container.appendChild(
        makeElement("div", "change-empty", "За выбранный период релизов не было.")
      );
      return;
    }
    const groups = [];
    changes.forEach(function (item) {
      const key = item.date || "";
      let group = groups[groups.length - 1];
      if (!group || group.key !== key) {
        group = { key: key, label: item.date_label || key, items: [] };
        groups.push(group);
      }
      group.items.push(item);
    });
    groups.forEach(function (group) {
      const block = makeElement("div", "change-day");
      block.appendChild(
        makeElement(
          "div",
          "change-day-title",
          group.label + (group.items[0].weekday ? " · " + group.items[0].weekday : "")
        )
      );
      group.items.forEach(function (item) {
        const article = makeElement("article", "change-item");
        const head = makeElement("div", "change-head");
        if (item.app) head.appendChild(makeElement("span", "badge", item.app));
        if (item.version) {
          head.appendChild(makeElement("span", "change-version", "v" + item.version));
        }
        if (item.time) head.appendChild(makeElement("span", "change-time", item.time));
        if (item.is_beta) head.appendChild(makeElement("span", "badge badge-warn", "beta"));
        article.appendChild(head);
        if (item.text) {
          article.appendChild(makeElement("div", "change-text", item.text));
        }
        block.appendChild(article);
      });
      container.appendChild(block);
    });
  }

  function renderWarehouse(list, movements) {
    list.innerHTML = "";
    if (!movements || !movements.length) {
      list.appendChild(
        makeElement("li", "change-empty", "За предыдущую смену склад не менялся.")
      );
      return;
    }
    movements.forEach(function (item) {
      const li = document.createElement("li");
      const head = makeElement("div", "warehouse-item-head");
      const title = makeElement("span", "", item.text || "");
      if (item.at) title.textContent = "(" + item.at + ") " + title.textContent;
      head.appendChild(title);
      if (item.qty) {
        head.appendChild(
          makeElement(
            "span",
            "event-qty" + (item.tone ? " event-" + item.tone : ""),
            item.qty
          )
        );
      }
      li.appendChild(head);

      const line = makeElement("div", "warehouse-line");
      if (item.line) {
        line.appendChild(document.createTextNode("Линия/оборудование: "));
        line.appendChild(makeElement("strong", "", item.line));
      } else if (item.operation !== "Новая позиция") {
        line.appendChild(document.createTextNode("Линия/оборудование не указана"));
      }
      if (item.remaining) {
        if (line.textContent) line.appendChild(document.createTextNode(" · "));
        line.appendChild(document.createTextNode("Остаток на складе: "));
        line.appendChild(makeElement("strong", "", item.remaining));
      }
      if (line.textContent) li.appendChild(line);
      if (item.comment) {
        li.appendChild(makeElement("div", "warehouse-line", item.comment));
      }
      list.appendChild(li);
    });
  }

  function showBriefing(briefing) {
    if (!eventsModal) {
      window.location.reload();
      return;
    }
    if (Array.isArray(briefing)) {
      // совместимость со старым ответом: только список событий
      renderPlainEvents(
        document.getElementById("events-modal-list"),
        briefing,
        "За предыдущую смену изменений не было."
      );
      eventsModal.hidden = false;
      return;
    }
    const data = briefing || {};
    const meta = data.changes_meta || {};
    const title = document.getElementById("events-modal-title");
    if (title) title.textContent = "Сводка при приёме смены";

    const period = document.getElementById("briefing-changes-period");
    if (period) {
      period.textContent = data.changes_period
        ? data.changes_period +
          (typeof meta.count === "number" ? " · релизов: " + meta.count : "")
        : "";
    }
    const note = document.getElementById("briefing-changes-note");
    if (note) {
      note.textContent = meta.ok
        ? ""
        : meta.error
          ? "Сервис истории изменений недоступен: " + meta.error
          : "";
      note.className = "briefing-note" + (meta.ok ? "" : " is-error");
      note.hidden = !note.textContent;
    }
    renderChanges(document.getElementById("briefing-changes"), data.changes);
    renderWarehouse(document.getElementById("briefing-warehouse"), data.warehouse);
    renderPlainEvents(
      document.getElementById("events-modal-list"),
      data.previous_events,
      "За предыдущую смену изменений не было."
    );
    eventsModal.hidden = false;
  }

  if (eventsModal) {
    const acceptEvents = document.getElementById("events-modal-accept");
    if (acceptEvents) {
      acceptEvents.addEventListener("click", function () {
        eventsModal.hidden = true;
        window.location.reload();
      });
    }

    // Сводка, сохранённая после обычного (не AJAX) приёма смены
    const briefingData = document.getElementById("shift-briefing-data");
    if (briefingData) {
      try {
        showBriefing(JSON.parse(briefingData.textContent || "null"));
      } catch (error) {
        /* некорректные данные не должны ломать страницу */
      }
    }
  }

  // Чеклист оборудования: перемещение по матрице стрелками для быстрого заполнения
  function initChecklistGrid() {
    document.querySelectorAll("table.checklist-matrix").forEach(function (table) {
      const body = table.tBodies[0];
      if (!body) return;
      const rows = Array.prototype.slice.call(body.rows);
      table.addEventListener("keydown", function (event) {
        const input = event.target;
        if (!input || !input.classList || !input.classList.contains("score-input")) return;
        const steps = {
          ArrowUp: [-1, 0],
          ArrowDown: [1, 0],
          ArrowLeft: [0, -1],
          ArrowRight: [0, 1],
          Enter: [1, 0],
        };
        const step = steps[event.key];
        if (!step) return;
        // Стрелки не должны менять значение в поле — только переносить фокус.
        event.preventDefault();
        const cell = input.closest("td");
        const row = input.closest("tr");
        if (!cell || !row) return;
        const nextRow = rows[rows.indexOf(row) + step[0]];
        if (!nextRow) return;
        const nextCell = nextRow.cells[cell.cellIndex + step[1]];
        if (!nextCell) return;
        const nextInput = nextCell.querySelector("input.score-input");
        if (!nextInput) return;
        nextInput.focus();
        nextInput.select();
      });
    });
  }

  initChecklistGrid();
});
