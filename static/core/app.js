(() => {
  const toggle = document.querySelector("[data-menu-toggle]");
  const sidebar = document.getElementById("sidebar");
  if (toggle && sidebar) {
    toggle.addEventListener("click", () => sidebar.classList.toggle("sidebar-open"));
  }

  const notificationButton = document.querySelector(".notification-button");
  const notificationPanel = document.getElementById("notification-panel");
  const notificationList = document.querySelector("[data-notification-list]");
  const notificationClose = document.querySelector("[data-notifications-close]");
  if (notificationButton && notificationPanel && notificationList) {
    const closeNotifications = () => {
      notificationPanel.hidden = true;
      notificationButton.setAttribute("aria-expanded", "false");
    };

    const showNotificationState = (message) => {
      notificationList.replaceChildren();
      const state = document.createElement("p");
      state.className = "notification-state";
      state.textContent = message;
      notificationList.append(state);
    };

    const loadNotifications = async () => {
      showNotificationState("Loading notifications…");
      try {
        const response = await fetch(notificationButton.dataset.notificationsUrl, {
          headers: { Accept: "application/json" },
          credentials: "same-origin",
        });
        if (!response.ok) throw new Error(`Notification request failed (${response.status}).`);
        const data = await response.json();
        const indicator = notificationButton.querySelector(".notification-indicator");
        if (indicator) indicator.hidden = data.alert_count === 0;
        if (!data.notifications.length) {
          showNotificationState("You’re all caught up.");
          return;
        }

        notificationList.replaceChildren();
        data.notifications.forEach((item) => {
          const link = document.createElement("a");
          link.className = `notification-item notification-${item.type}`;
          link.href = item.url;
          const title = document.createElement("strong");
          title.textContent = item.title;
          const message = document.createElement("span");
          message.textContent = item.message;
          link.append(title, message);
          notificationList.append(link);
        });
      } catch (error) {
        showNotificationState("Couldn’t load notifications. Please try again.");
        console.error(error);
      }
    };

    notificationButton.addEventListener("click", () => {
      const opening = notificationPanel.hidden;
      notificationPanel.hidden = !opening;
      notificationButton.setAttribute("aria-expanded", String(opening));
      if (opening) loadNotifications();
    });
    if (notificationClose) notificationClose.addEventListener("click", closeNotifications);
    document.addEventListener("click", (event) => {
      if (!notificationPanel.hidden && !notificationPanel.contains(event.target) && !notificationButton.contains(event.target)) {
        closeNotifications();
      }
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") closeNotifications();
    });
  }

  const chart = document.getElementById("cash-chart");
  const labelsTarget = document.getElementById("chart-labels");
  const labelsNode = document.getElementById("chart-label-data");
  const valuesNode = document.getElementById("chart-value-data");
  if (!chart || !labelsTarget || !labelsNode || !valuesNode) return;

  const labels = JSON.parse(labelsNode.textContent);
  const values = JSON.parse(valuesNode.textContent);
  const width = 700;
  const height = 190;
  const left = 8;
  const right = 692;
  const top = 14;
  const bottom = 164;
  const max = Math.max(...values, 1) * 1.18;
  const points = values.map((value, index) => {
    const x = left + (labels.length < 2 ? 0 : (right - left) * index / (labels.length - 1));
    const y = bottom - (value / max) * (bottom - top);
    return [x, y];
  });
  const line = points.map((point) => point.join(",")).join(" ");
  const area = `${left},${bottom} ${line} ${right},${bottom}`;
  chart.innerHTML = `
    <defs><linearGradient id="cash-fill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stop-color="#3b82f6" stop-opacity=".20"/><stop offset="100%" stop-color="#3b82f6" stop-opacity="0"/></linearGradient></defs>
    ${[0, 1, 2].map((row) => `<line x1="${left}" y1="${top + row * (bottom - top) / 2}" x2="${right}" y2="${top + row * (bottom - top) / 2}" stroke="#edf1f7" stroke-dasharray="4 5"/>`).join("")}
    <polygon points="${area}" fill="url(#cash-fill)"/>
    <polyline points="${line}" fill="none" stroke="#3b82f6" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>
    ${points.map(([x, y]) => `<circle cx="${x}" cy="${y}" r="4" fill="#fff" stroke="#3b82f6" stroke-width="2.5"/>`).join("")}`;
  labelsTarget.innerHTML = labels.map((label) => `<span>${label}</span>`).join("");
})();
