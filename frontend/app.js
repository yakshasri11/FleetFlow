// FleetFlow frontend — plain JS, no build step. Talks directly to the FastAPI backend.
// Change API_BASE if your backend runs somewhere other than localhost:8000.
const API_BASE = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
  ? "http://127.0.0.1:8000"
  : ""; // same-origin if served behind the backend / a reverse proxy

let cache = { vehicles: [], drivers: [], shipments: [], trips: [] };

// ---------------- Token helpers ----------------
function getToken() { return localStorage.getItem("fleetflow_token"); }
function setToken(t) { localStorage.setItem("fleetflow_token", t); }
function clearToken() { localStorage.removeItem("fleetflow_token"); }

// ---------------- API wrapper ----------------
async function api(path, options = {}) {
  const headers = options.headers || {};
  const token = getToken();
  if (token) headers["Authorization"] = "Bearer " + token;
  if (options.body && !(options.body instanceof URLSearchParams)) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(API_BASE + path, { ...options, headers });
  const isAuthAttempt = path.startsWith("/auth/login") || path.startsWith("/auth/register");
  if (res.status === 401 && !isAuthAttempt) {
    // A 401 on an already-authenticated request means the session/token is
    // no longer valid. A 401 on the login/register attempt itself just means
    // bad credentials — handled below like any other error, not as expiry.
    clearToken();
    showLogin("Session expired — please sign in again");
    throw new Error("Session expired — please sign in again");
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    const detail = data && data.detail
      ? (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail))
      : `Request failed (${res.status})`;
    throw new Error(detail);
  }
  return data;
}

function toast(msg, type = "success") {
  const t = document.getElementById("toast");
  t.textContent = msg;
  t.className = "toast " + type;
  setTimeout(() => t.classList.add("hidden"), 3200);
}

// ---------------- Auth screen ----------------
function showLogin(message) {
  document.getElementById("login-screen").classList.remove("hidden");
  document.getElementById("app").classList.add("hidden");
  const msg = document.getElementById("login-msg");
  if (message) { msg.textContent = message; msg.className = "form-msg error"; }
  else { msg.textContent = ""; msg.className = "form-msg"; }
}
let currentUser = null;

async function showApp() {
  document.getElementById("login-screen").classList.add("hidden");
  document.getElementById("app").classList.remove("hidden");

  try {
    currentUser = await api("/auth/me");
  } catch (err) {
    return; // api() already redirected to login on a real auth failure
  }

  applyRoleVisibility();
  const landing = currentUser.role === "driver" ? "driver-dashboard" : "dashboard";
  loadView(landing);
  loadNotifications();
  if (window.__notifInterval) clearInterval(window.__notifInterval);
  window.__notifInterval = setInterval(loadNotifications, 30000);
}

function applyRoleVisibility() {
  document.querySelectorAll(".nav-item[data-roles]").forEach(btn => {
    const allowed = btn.dataset.roles.split(",");
    btn.classList.toggle("hidden", !allowed.includes(currentUser.role));
  });
  document.getElementById("topbar-user").textContent = `${currentUser.username} · ${currentUser.role.replace(/_/g, " ")}`;
}

// ---------------- Notifications ----------------
async function loadNotifications() {
  try {
    const list = await api("/notifications/");
    const unread = list.filter(n => n.is_read === "false").length;
    const countEl = document.getElementById("notif-count");
    countEl.textContent = unread;
    countEl.classList.toggle("hidden", unread === 0);

    const listEl = document.getElementById("notif-list");
    listEl.innerHTML = list.length ? list.slice(0, 20).map(n => `
      <div class="notif-item ${n.is_read === "false" ? "unread" : ""}">
        <div class="notif-title">${n.title}</div>
        <div class="notif-msg">${n.message}</div>
        <div class="notif-time">${new Date(n.created_at).toLocaleString()}</div>
      </div>`).join("") : `<div class="loading">No notifications yet.</div>`;
  } catch (err) { /* silent — notifications are non-critical */ }
}

document.getElementById("notif-bell").addEventListener("click", () => {
  document.getElementById("notif-panel").classList.toggle("hidden");
});
document.getElementById("notif-mark-all").addEventListener("click", async () => {
  try { await api("/notifications/read-all", { method: "POST" }); loadNotifications(); }
  catch (err) { toast(err.message, "error"); }
});
document.addEventListener("click", (e) => {
  const panel = document.getElementById("notif-panel");
  const bell = document.getElementById("notif-bell");
  if (!panel.contains(e.target) && e.target !== bell && !panel.classList.contains("hidden")) {
    panel.classList.add("hidden");
  }
});

document.querySelectorAll(".toggle-password").forEach(btn => {
  btn.addEventListener("click", () => {
    const input = document.getElementById(btn.dataset.target);
    const showing = input.type === "text";
    input.type = showing ? "password" : "text";
    btn.querySelector(".icon-eye").classList.toggle("hidden", !showing);
    btn.querySelector(".icon-eye-off").classList.toggle("hidden", showing);
    btn.setAttribute("aria-label", showing ? "Show password" : "Hide password");
  });
});

document.querySelectorAll(".tab-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    const isLogin = btn.dataset.tab === "login";
    document.getElementById("login-form").classList.toggle("hidden", !isLogin);
    document.getElementById("register-form").classList.toggle("hidden", isLogin);
  });
});

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = document.getElementById("login-msg");
  msg.textContent = ""; msg.className = "form-msg";
  const username = document.getElementById("login-username").value;
  const password = document.getElementById("login-password").value;
  try {
    const body = new URLSearchParams();
    body.set("username", username);
    body.set("password", password);
    const data = await api("/auth/login", { method: "POST", body });
    setToken(data.access_token);
    showApp();
  } catch (err) {
    msg.textContent = err.message; msg.className = "form-msg error";
  }
});

document.getElementById("register-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const msg = document.getElementById("register-msg");
  msg.textContent = ""; msg.className = "form-msg";
  try {
    await api("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        username: document.getElementById("reg-username").value,
        email: document.getElementById("reg-email").value,
        password: document.getElementById("reg-password").value,
        role: "admin",
      }),
    });
    msg.textContent = "Administrator account created — you can sign in now."; msg.className = "form-msg success";
    document.querySelector('.tab-btn[data-tab="login"]').click();
    checkBootstrapStatus();
  } catch (err) {
    msg.textContent = err.message; msg.className = "form-msg error";
  }
});

async function checkBootstrapStatus() {
  try {
    const res = await fetch(API_BASE + "/auth/bootstrap-status");
    const data = await res.json();
    document.getElementById("login-tabs").classList.toggle("hidden", !data.registration_open);
    if (!data.registration_open) document.querySelector('.tab-btn[data-tab="login"]').click();
  } catch (err) { /* if this fails, leave the tab as-is */ }
}

document.getElementById("logout-btn").addEventListener("click", () => {
  clearToken();
  showLogin();
});

// ---------------- Sidebar navigation ----------------
document.querySelectorAll(".nav-item").forEach(btn => {
  btn.addEventListener("click", () => loadView(btn.dataset.view));
});

function loadView(view) {
  const navBtn = document.querySelector(`.nav-item[data-view="${view}"]`);
  if (navBtn && currentUser && !navBtn.dataset.roles.split(",").includes(currentUser.role)) {
    // Not authorized for this view per role — the backend would reject the
    // underlying API calls anyway, but redirect before even trying.
    view = currentUser.role === "driver" ? "driver-dashboard" : "dashboard";
  }
  document.querySelectorAll(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  document.querySelectorAll(".view").forEach(v => v.classList.remove("active"));
  document.getElementById("view-" + view).classList.add("active");
  document.getElementById("view-title").textContent = document.querySelector(`.nav-item[data-view="${view}"]`).textContent;

  const loaders = {
    dashboard: loadDashboard, tracking: loadTracking, vehicles: loadVehicles, drivers: loadDrivers,
    shipments: loadShipments, trips: loadTrips, fuel: loadFuel,
    maintenance: loadMaintenance, reports: loadReports, profile: loadProfile,
    "driver-dashboard": loadDriverDashboard, "my-trips": loadMyTrips, "my-shipments": loadMyShipments,
    users: loadUsers,
  };
  if (loaders[view]) loaders[view]();
}

function badge(text) {
  return `<span class="badge ${text}">${text.replace(/_/g, " ")}</span>`;
}

// ---------------- Dashboard ----------------
let charts = {};
function renderChart(id, config) {
  const canvas = document.getElementById(id);
  if (!canvas) return;
  if (charts[id]) { charts[id].destroy(); delete charts[id]; }
  charts[id] = new Chart(canvas.getContext("2d"), {
    ...config,
    options: { responsive: true, maintainAspectRatio: false, ...config.options },
  });
}

function showChartEmptyState(canvasId, message) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  if (charts[canvasId]) { charts[canvasId].destroy(); delete charts[canvasId]; }
  canvas.style.display = "none";
  let empty = canvas.parentElement.querySelector(".chart-empty");
  if (!empty) {
    empty = document.createElement("div");
    empty.className = "chart-empty";
    canvas.parentElement.appendChild(empty);
  }
  empty.textContent = message;
}
function hideChartEmptyState(canvasId) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  canvas.style.display = "";
  const empty = canvas.parentElement.querySelector(".chart-empty");
  if (empty) empty.remove();
}

const PALETTE = ["#2563eb", "#16a34a", "#f59e0b", "#dc2626", "#7c3aed", "#0891b2"];

let dashboardChartsRequestId = 0;

async function loadDashboardCharts() {
  const requestId = ++dashboardChartsRequestId;
  let c;
  try { c = await api("/dashboard/charts"); } catch (err) {
    console.error("Failed to load /dashboard/charts:", err);
    if (requestId !== dashboardChartsRequestId) return; // a newer call already resolved — don't clobber it
    ["chart-utilization", "chart-vehicle-status", "chart-shipment-status", "chart-fuel", "chart-eta", "chart-maintenance"]
      .forEach(id => showChartEmptyState(id, `Couldn't load chart data (${err.message}).`));
    return;
  }
  if (requestId !== dashboardChartsRequestId) return; // a newer call is already in flight/resolved — discard this stale one

  // 1. Fleet Utilization Trend
  if (!c.fleet_utilization_trend.length) {
    showChartEmptyState("chart-utilization", "No trips recorded yet — utilization trend will appear once trips are scheduled.");
  } else {
    hideChartEmptyState("chart-utilization");
    renderChart("chart-utilization", {
      type: "line",
      data: {
        labels: c.fleet_utilization_trend.map(r => r.date),
        datasets: [{ label: "Utilization %", data: c.fleet_utilization_trend.map(r => r.utilization_percent),
          borderColor: PALETTE[0], backgroundColor: PALETTE[0] + "33", fill: true, tension: 0.3, pointRadius: 3 }],
      },
      options: {
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => `Utilization: ${ctx.parsed.y}%` } } },
        scales: {
          y: { beginAtZero: true, max: 100, title: { display: true, text: "Utilization %" } },
          x: { title: { display: true, text: "Date" } },
        },
      },
    });
  }

  // 2. Vehicle Status Distribution
  const vsTotal = Object.values(c.vehicle_status_distribution).reduce((a, b) => a + b, 0);
  if (!vsTotal) {
    showChartEmptyState("chart-vehicle-status", "No vehicles registered yet.");
  } else {
    hideChartEmptyState("chart-vehicle-status");
    renderChart("chart-vehicle-status", {
      type: "doughnut",
      data: {
        labels: Object.keys(c.vehicle_status_distribution).map(s => s.replace(/_/g, " ")),
        datasets: [{ data: Object.values(c.vehicle_status_distribution), backgroundColor: PALETTE, borderWidth: 2, borderColor: "#fff" }],
      },
      options: { plugins: { legend: { position: "bottom", labels: { boxWidth: 12, padding: 12 } } } },
    });
  }

  // 3. Shipment Delivery Performance
  const shTotal = Object.values(c.shipment_status_distribution).reduce((a, b) => a + b, 0);
  if (!shTotal) {
    showChartEmptyState("chart-shipment-status", "No shipments recorded yet.");
  } else {
    hideChartEmptyState("chart-shipment-status");
    renderChart("chart-shipment-status", {
      type: "bar",
      data: {
        labels: Object.keys(c.shipment_status_distribution).map(s => s.replace(/_/g, " ")),
        datasets: [{ label: "Shipments", data: Object.values(c.shipment_status_distribution), backgroundColor: PALETTE[0], borderRadius: 4 }],
      },
      options: {
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: "Shipments" } } },
      },
    });
  }

  // 4. Fuel Consumption
  if (!c.fuel_consumption_trend.length) {
    showChartEmptyState("chart-fuel", "No fuel records yet — add a fuel entry to see consumption trends.");
  } else {
    hideChartEmptyState("chart-fuel");
    renderChart("chart-fuel", {
      type: "line",
      data: {
        labels: c.fuel_consumption_trend.map(r => r.date),
        datasets: [{ label: "Liters", data: c.fuel_consumption_trend.map(r => r.liters),
          borderColor: PALETTE[2], backgroundColor: PALETTE[2] + "33", fill: true, tension: 0.3, pointRadius: 3 }],
      },
      options: {
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: ctx => `${ctx.parsed.y} L` } } },
        scales: { y: { beginAtZero: true, title: { display: true, text: "Liters" } }, x: { title: { display: true, text: "Date" } } },
      },
    });
  }

  // 5. Delivery / ETA Performance
  const etaTotal = c.delivery_eta_performance.delivered + c.delivery_eta_performance.delayed;
  if (!etaTotal) {
    showChartEmptyState("chart-eta", "No delivered or delayed shipments yet.");
  } else {
    hideChartEmptyState("chart-eta");
    renderChart("chart-eta", {
      type: "pie",
      data: {
        labels: ["Delivered on schedule", "Delayed"],
        datasets: [{ data: [c.delivery_eta_performance.delivered, c.delivery_eta_performance.delayed],
          backgroundColor: [PALETTE[1], PALETTE[3]], borderWidth: 2, borderColor: "#fff" }],
      },
      options: {
        plugins: {
          legend: { position: "bottom", labels: { boxWidth: 12, padding: 12 } },
          tooltip: { callbacks: { label: ctx => `${ctx.label}: ${ctx.parsed} (${Math.round(ctx.parsed / etaTotal * 100)}%)` } },
        },
      },
    });
  }

  // 6. Maintenance Overview
  const maintTotal = c.maintenance_overview.upcoming + c.maintenance_overview.overdue + c.maintenance_overview.completed;
  if (!maintTotal) {
    showChartEmptyState("chart-maintenance", "No maintenance records yet.");
  } else {
    hideChartEmptyState("chart-maintenance");
    renderChart("chart-maintenance", {
      type: "bar",
      data: {
        labels: ["Upcoming (7 days)", "Overdue", "Completed"],
        datasets: [{ label: "Records",
          data: [c.maintenance_overview.upcoming, c.maintenance_overview.overdue, c.maintenance_overview.completed],
          backgroundColor: [PALETTE[2], PALETTE[3], PALETTE[1]], borderRadius: 4 }],
      },
      options: {
        indexAxis: "y",
        plugins: { legend: { display: false } },
        scales: { x: { beginAtZero: true, ticks: { precision: 0 }, title: { display: true, text: "Records" } } },
      },
    });
  }
}

async function loadDashboard() {
  const el = document.getElementById("dashboard-cards");
  try {
    const d = await api("/dashboard/fleet");
    const cards = [
      ["Total Vehicles", d.total_vehicles], ["Active Vehicles", d.active_vehicles],
      ["Under Maintenance", d.vehicles_under_maintenance], ["Total Drivers", d.total_drivers],
      ["Available Drivers", d.available_drivers], ["Assigned Drivers", d.assigned_drivers],
      ["Total Trips", d.total_trips], ["Completed Trips", d.completed_trips],
      ["Active Shipments", d.active_shipments], ["Maintenance Records", d.total_maintenance_records],
      ["Fuel Consumed (L)", d.total_fuel_consumed.toFixed(1)],
    ];
    el.innerHTML = cards.map(([label, val], i) =>
      `<div class="stat-card${i === 0 ? " accent" : ""}"><div class="stat-label">${label}</div><div class="stat-value">${val}</div></div>`
    ).join("");
  } catch (err) { el.innerHTML = `<div class="loading">${err.message}</div>`; }
  loadDashboardCharts();
  loadOperationsTables();
}

async function loadOperationsTables() {
  const activeEl = document.getElementById("ops-active-shipments");
  const maintEl = document.getElementById("ops-upcoming-maintenance");
  try {
    const shipments = await api("/shipments/");
    const active = shipments.filter(s => ["assigned", "in_transit", "delayed"].includes(s.status)).slice(0, 8);
    activeEl.innerHTML = active.length ? `<table class="mini-table"><tbody>${active.map(s => `
      <tr><td class="mono">${s.tracking_number}</td><td>${s.origin} → ${s.destination}</td><td>${badge(s.status)}</td></tr>`).join("")}</tbody></table>`
      : `<div class="loading">No active shipments right now.</div>`;
  } catch (err) { activeEl.innerHTML = `<div class="loading">${err.message}</div>`; }

  try {
    const records = await api("/maintenance/");
    const now = new Date();
    const soon = new Date(now.getTime() + 7 * 86400000);
    const upcoming = records.filter(m => m.status !== "completed" && m.next_service_date &&
      new Date(m.next_service_date) <= soon).slice(0, 8);
    maintEl.innerHTML = upcoming.length ? `<table class="mini-table"><tbody>${upcoming.map(m => `
      <tr><td class="mono">Vehicle #${m.vehicle_id}</td><td>${m.category.replace(/_/g, " ")}</td>
      <td>${new Date(m.next_service_date).toLocaleDateString()}</td></tr>`).join("")}</tbody></table>`
      : `<div class="loading">Nothing due in the next 7 days.</div>`;
  } catch (err) { maintEl.innerHTML = `<div class="loading">${err.message}</div>`; }
}

// ---------------- Live Tracking (Leaflet + OpenStreetMap — free, no API key) ----------------
let trackingMap = null;
let trackingLayer = null;

async function loadTracking() {
  if (!trackingMap) {
    trackingMap = L.map("tracking-map").setView([20, 78], 4);
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors", maxZoom: 18,
    }).addTo(trackingMap);
  }
  if (trackingLayer) trackingLayer.clearLayers();
  else trackingLayer = L.layerGroup().addTo(trackingMap);

  const emptyEl = document.getElementById("tracking-empty");
  const tableEl = document.getElementById("tracking-active-table");
  let shipments, trips, activeTracking;
  try {
    [shipments, trips, activeTracking] = await Promise.all([
      api("/shipments/"), api("/trips/"), api("/tracking/active").catch(() => []),
    ]);
  } catch (err) {
    emptyEl.textContent = err.message; emptyEl.classList.remove("hidden");
    tableEl.innerHTML = "";
    return;
  }

  const liveByTrip = {};
  activeTracking.forEach(t => { liveByTrip[t.trip_id] = t; });

  // Active Trips table — Dispatcher/Manager overview (Driver only ever
  // gets their own trip back from /tracking/active, enforced server-side).
  if (activeTracking.length) {
    tableEl.innerHTML = `<table><thead><tr>
      <th>Trip</th><th>Driver</th><th>Shipment</th><th>Status</th><th>Last Location</th>
    </tr></thead><tbody>${activeTracking.map(t => `
      <tr style="cursor:pointer" onclick="focusTrackingTrip(${t.trip_id})">
        <td class="mono">TRP-${t.trip_id}</td><td>${t.driver_name || "—"}</td>
        <td class="mono">${t.tracking_number || "—"}</td><td>${badge(t.status)}</td>
        <td>${t.has_live_location ? `Live — ${t.seconds_since_update}s ago` : "Estimated"}</td>
      </tr>`).join("")}</tbody></table>`;
  } else {
    tableEl.innerHTML = `<div class="loading">No active trips right now.</div>`;
  }

  const trackable = shipments.filter(s => s.trip_id && ["assigned", "in_transit", "delayed"].includes(s.status));
  const bounds = [];
  let plotted = 0;

  for (const shipment of trackable) {
    let routes;
    try { routes = await api(`/routes/?trip_id=${shipment.trip_id}`); } catch { continue; }
    const route = routes[0]; // most recent
    if (!route || route.origin_lat == null || route.destination_lat == null) continue;

    const trip = trips.find(t => t.id === shipment.trip_id);
    const live = liveByTrip[shipment.trip_id];

    const origin = [route.origin_lat, route.origin_lng];
    const dest = [route.destination_lat, route.destination_lng];
    bounds.push(origin, dest);
    plotted++;

    L.circleMarker(origin, { radius: 7, color: "#16a34a", fillColor: "#16a34a", fillOpacity: 0.9 })
      .bindPopup(`<strong>Pickup</strong><br>${route.origin}`).addTo(trackingLayer);
    L.circleMarker(dest, { radius: 7, color: "#dc2626", fillColor: "#dc2626", fillOpacity: 0.9 })
      .bindPopup(`<strong>Destination</strong><br>${route.destination}`).addTo(trackingLayer);
    L.polyline([origin, dest], { color: "#2563eb", weight: 3, opacity: 0.6, dashArray: "6 6" }).addTo(trackingLayer);

    let vehLat, vehLng, positionLabel;
    if (live && live.has_live_location) {
      // Real position reported by the driver's browser, via periodic polling.
      vehLat = live.latest_latitude; vehLng = live.latest_longitude;
      positionLabel = `Live location — last updated ${live.seconds_since_update}s ago`;
    } else {
      // No real location yet — estimate along the route from elapsed time,
      // clearly labeled as such, never presented as live GPS.
      let fraction = 0.5;
      if (trip && trip.scheduled_start && shipment.eta) {
        const start = new Date(trip.scheduled_start).getTime();
        const eta = new Date(shipment.eta).getTime();
        const now = Date.now();
        if (eta > start) fraction = Math.min(Math.max((now - start) / (eta - start), 0.02), 0.98);
      }
      vehLat = origin[0] + (dest[0] - origin[0]) * fraction;
      vehLng = origin[1] + (dest[1] - origin[1]) * fraction;
      positionLabel = "Estimated position — no live GPS feed yet";
    }

    const popup = `
      <strong>${shipment.tracking_number}</strong> ${badge(shipment.status)}<br>
      Vehicle: ${trip ? (trip.vehicle_registration || "—") : "—"}<br>
      Driver: ${trip ? (trip.driver_name || "—") : "—"}<br>
      Distance: ${route.distance_km ?? "—"} km &middot; ETA: ${shipment.eta ? new Date(shipment.eta).toLocaleString() : "—"}<br>
      <em>${positionLabel}</em>`;
    trackingMarkerPositions[shipment.trip_id] = [vehLat, vehLng];
    L.marker([vehLat, vehLng], {
      icon: L.divIcon({ className: "truck-marker", html: "🚚", iconSize: [24, 24] }),
    }).bindPopup(popup).addTo(trackingLayer);
  }

  if (plotted === 0) {
    emptyEl.classList.remove("hidden");
  } else {
    emptyEl.classList.add("hidden");
    trackingMap.fitBounds(bounds, { padding: [40, 40] });
  }
  setTimeout(() => trackingMap.invalidateSize(), 100);
}

let trackingMarkerPositions = {};
window.focusTrackingTrip = (tripId) => {
  const pos = trackingMarkerPositions[tripId];
  if (pos && trackingMap) trackingMap.setView(pos, 10);
};

// ---------------- Vehicles ----------------
async function loadVehicles() {
  cache.vehicles = await api("/vehicles/").catch(() => []);
  renderVehicles();
}
function renderVehicles() {
  const q = (document.getElementById("vehicles-search").value || "").toLowerCase();
  const rows = cache.vehicles.filter(v => v.registration_number.toLowerCase().includes(q));
  document.querySelector("#vehicles-table tbody").innerHTML = rows.map(v => `
    <tr><td class="mono">${v.id}</td><td class="mono">${v.registration_number}</td>
    <td>${v.vehicle_type}</td><td>${v.capacity ?? "—"}</td><td>${v.fuel_type ?? "—"}</td>
    <td>${badge(v.status)}</td></tr>`).join("") || `<tr><td colspan="6" class="loading">No vehicles yet.</td></tr>`;
}
document.getElementById("vehicles-search").addEventListener("input", renderVehicles);

// ---------------- Drivers ----------------
async function loadDrivers() {
  cache.drivers = await api("/drivers/").catch(() => []);
  renderDrivers();
}
async function renderDrivers() {
  const q = (document.getElementById("drivers-search").value || "").toLowerCase();
  const rows = cache.drivers.filter(d => d.name.toLowerCase().includes(q) || d.license_number.toLowerCase().includes(q));
  document.querySelector("#drivers-table tbody").innerHTML = rows.map(d => `
    <tr><td class="mono">${d.id}</td><td>${d.name}</td><td class="mono">${d.license_number}</td>
    <td>${d.phone ?? "—"}</td><td>${badge(d.status)}</td>
    <td><button class="link-btn" onclick="showPerformance(${d.id})">View</button></td></tr>`).join("")
    || `<tr><td colspan="6" class="loading">No drivers yet.</td></tr>`;
}
document.getElementById("drivers-search").addEventListener("input", renderDrivers);

window.showPerformance = async (id) => {
  try {
    const p = await api(`/driver/${id}/performance`);
    toast(`Trips — total: ${p.total_trips}, completed: ${p.completed_trips}, active: ${p.active_trips}, cancelled: ${p.cancelled_trips}`, "success");
  } catch (err) { toast(err.message, "error"); }
};

// ---------------- Shipments ----------------
async function loadShipments() {
  cache.shipments = await api("/shipments/").catch(() => []);
  renderShipments();
}
function renderShipments() {
  const q = (document.getElementById("shipments-search").value || "").toLowerCase();
  const rows = cache.shipments.filter(s => s.tracking_number.toLowerCase().includes(q));
  const canDelete = currentUser && ["admin", "fleet_manager"].includes(currentUser.role);
  document.querySelector("#shipments-table tbody").innerHTML = rows.map(s => `
    <tr><td class="mono">${s.id}</td><td class="mono">${s.tracking_number}</td>
    <td>${s.origin}</td><td>${s.destination}</td><td>${badge(s.status)}</td>
    <td>${canDelete ? `<button class="link-btn danger" onclick="confirmDeleteShipment(${s.id}, '${s.tracking_number}')">Delete</button>` : "—"}</td></tr>`).join("")
    || `<tr><td colspan="6" class="loading">No shipments yet.</td></tr>`;
}
document.getElementById("shipments-search").addEventListener("input", renderShipments);

// ---------------- Generic delete confirmation ----------------
window.confirmDelete = (title, body, onConfirm) => {
  document.querySelectorAll(".modal").forEach(m => m.classList.add("hidden"));
  document.getElementById("confirm-delete-title").textContent = title;
  document.getElementById("confirm-delete-body").textContent = body;
  const modal = document.getElementById("confirm-delete-modal");
  modal.classList.remove("hidden");
  document.getElementById("modal-overlay").classList.remove("hidden");
  const btn = document.getElementById("confirm-delete-btn");
  const freshBtn = btn.cloneNode(true); // strip old listeners
  btn.replaceWith(freshBtn);
  freshBtn.addEventListener("click", async () => {
    document.getElementById("modal-overlay").classList.add("hidden");
    await onConfirm();
  });
};

window.confirmDeleteShipment = (id, trackingNumber) => {
  confirmDelete(
    "Delete Shipment?",
    `Are you sure you want to delete ${trackingNumber}? This action cannot be undone.`,
    async () => {
      try { await api(`/shipments/${id}`, { method: "DELETE" }); toast(`${trackingNumber} deleted`); loadShipments(); loadDashboard(); }
      catch (err) { toast(err.message, "error"); }
    }
  );
};

// ---------------- Trips ----------------
async function loadTrips() {
  const [trips, drivers, vehicles] = await Promise.all([
    api("/trips/").catch(() => []), api("/drivers/").catch(() => []), api("/vehicles/").catch(() => []),
  ]);
  cache.trips = trips; cache.drivers = drivers; cache.vehicles = vehicles;
  renderTrips();
}
function nameFor(list, id) { const item = list.find(x => x.id === id); return item ? (item.name || item.registration_number) : `#${id}`; }
function renderTrips() {
  const q = (document.getElementById("trips-search").value || "").toLowerCase();
  const rows = cache.trips.filter(t =>
    nameFor(cache.drivers, t.driver_id).toLowerCase().includes(q) ||
    nameFor(cache.vehicles, t.vehicle_id).toLowerCase().includes(q));
  const canDelete = currentUser && ["admin", "fleet_manager"].includes(currentUser.role);
  document.querySelector("#trips-table tbody").innerHTML = rows.map(t => {
    const isFinal = t.status === "completed" || t.status === "cancelled";
    const actions = [];
    if (!isFinal) {
      actions.push(`<button class="link-btn" onclick="completeTrip(${t.id})">Complete</button>`);
      actions.push(`<button class="link-btn danger" onclick="cancelTrip(${t.id})">Cancel</button>`);
    }
    if (isFinal && canDelete) {
      actions.push(`<button class="link-btn danger" onclick="confirmDeleteTrip(${t.id})">Delete</button>`);
    }
    return `<tr><td class="mono">${t.id}</td><td>${nameFor(cache.drivers, t.driver_id)}</td>
    <td class="mono">${nameFor(cache.vehicles, t.vehicle_id)}</td><td>${badge(t.status)}</td>
    <td>${actions.join(" ") || "—"}</td></tr>`;
  }).join("")
    || `<tr><td colspan="5" class="loading">No trips yet.</td></tr>`;
}
document.getElementById("trips-search").addEventListener("input", renderTrips);

window.confirmDeleteTrip = (id) => {
  confirmDelete(
    "Delete Trip?",
    `Are you sure you want to delete Trip #${id}? This action cannot be undone.`,
    async () => {
      try { await api(`/trips/${id}`, { method: "DELETE" }); toast(`Trip #${id} deleted`); loadTrips(); loadDashboard(); }
      catch (err) { toast(err.message, "error"); }
    }
  );
};

window.completeTrip = async (id) => {
  try { await api(`/trips/${id}`, { method: "PUT", body: JSON.stringify({ status: "completed" }) }); toast("Trip marked completed"); loadTrips(); loadDashboard(); }
  catch (err) { toast(err.message, "error"); }
};
window.cancelTrip = async (id) => {
  try { await api(`/trips/${id}`, { method: "PUT", body: JSON.stringify({ status: "cancelled" }) }); toast("Trip cancelled"); loadTrips(); loadDashboard(); }
  catch (err) { toast(err.message, "error"); }
};

// ---------------- Fuel ----------------
async function loadFuel() {
  const [fuel, drivers, vehicles] = await Promise.all([
    api("/fuel/").catch(() => []), api("/drivers/").catch(() => []), api("/vehicles/").catch(() => []),
  ]);
  cache.fuel = fuel; cache.drivers = drivers; cache.vehicles = vehicles;
  renderFuel();
}
function renderFuel() {
  const q = (document.getElementById("fuel-search").value || "").toLowerCase();
  const rows = (cache.fuel || []).filter(f =>
    nameFor(cache.vehicles, f.vehicle_id).toLowerCase().includes(q) || nameFor(cache.drivers, f.driver_id).toLowerCase().includes(q));
  document.querySelector("#fuel-table tbody").innerHTML = rows.map(f => `
    <tr><td class="mono">${f.id}</td><td>${nameFor(cache.vehicles, f.vehicle_id)}</td>
    <td>${nameFor(cache.drivers, f.driver_id)}</td><td>${f.fuel_quantity_liters}</td>
    <td>${f.fuel_cost}</td><td>${f.odometer_reading ?? "—"}</td></tr>`).join("")
    || `<tr><td colspan="6" class="loading">No fuel records yet.</td></tr>`;
}
document.getElementById("fuel-search").addEventListener("input", renderFuel);

// ---------------- Maintenance ----------------
async function loadMaintenance() {
  const [records, vehicles] = await Promise.all([api("/maintenance/").catch(() => []), api("/vehicles/").catch(() => [])]);
  cache.maintenance = records; cache.vehicles = vehicles;
  renderMaintenance();
}
function renderMaintenance() {
  const q = (document.getElementById("maintenance-search").value || "").toLowerCase();
  const rows = (cache.maintenance || []).filter(m => nameFor(cache.vehicles, m.vehicle_id).toLowerCase().includes(q) || m.category.toLowerCase().includes(q));
  document.querySelector("#maintenance-table tbody").innerHTML = rows.map(m => `
    <tr><td class="mono">${m.id}</td><td>${nameFor(cache.vehicles, m.vehicle_id)}</td>
    <td>${m.category}</td><td>${m.service_date.slice(0, 10)}</td><td>${badge(m.status.toLowerCase().replace(" ", "_"))}</td>
    <td>${m.status !== "Completed" ? `<button class="link-btn" onclick="completeMaintenance(${m.id})">Mark Completed</button>` : ""}
    <button class="link-btn danger" onclick="archiveMaintenance(${m.id})">Archive</button></td></tr>`).join("")
    || `<tr><td colspan="6" class="loading">No maintenance records yet.</td></tr>`;
}
document.getElementById("maintenance-search").addEventListener("input", renderMaintenance);

window.completeMaintenance = async (id) => {
  try { await api(`/maintenance/${id}`, { method: "PUT", body: JSON.stringify({ status: "Completed" }) }); toast("Maintenance marked completed"); loadMaintenance(); loadDashboard(); }
  catch (err) { toast(err.message, "error"); }
};
window.archiveMaintenance = async (id) => {
  if (!confirm("Archive this record? It stays in the database for history but leaves the active list.")) return;
  try { await api(`/maintenance/${id}`, { method: "DELETE" }); toast("Record archived"); loadMaintenance(); }
  catch (err) { toast(err.message, "error"); }
};

// ---------------- Reports & Analytics ----------------
async function loadReports() {
  try {
    const f = await api("/analytics/fuel");
    document.getElementById("fuel-analytics-body").innerHTML = `
      <div class="report-row"><span>Total Fuel Consumed</span><span class="val">${f.total_fuel_consumed.toFixed(1)} L</span></div>
      <div class="report-row"><span>Total Fuel Cost</span><span class="val">${f.total_fuel_cost.toFixed(2)}</span></div>
      <div class="report-row"><span>Average Consumption</span><span class="val">${f.average_fuel_consumption.toFixed(1)} L</span></div>
      <div class="report-row"><span>Highest Usage Vehicle</span><span class="val">${f.vehicle_highest_usage ?? "—"}</span></div>
      <div class="report-row"><span>Lowest Usage Vehicle</span><span class="val">${f.vehicle_lowest_usage ?? "—"}</span></div>`;
  } catch (err) { document.getElementById("fuel-analytics-body").innerHTML = err.message; }

  try {
    const o = await api("/analytics/operations");
    document.getElementById("ops-analytics-body").innerHTML = `
      <div class="report-row"><span>Total Deliveries</span><span class="val">${o.total_deliveries}</span></div>
      <div class="report-row"><span>Successful</span><span class="val">${o.successful_deliveries}</span></div>
      <div class="report-row"><span>Delayed</span><span class="val">${o.delayed_deliveries}</span></div>
      <div class="report-row"><span>Cancelled</span><span class="val">${o.cancelled_deliveries}</span></div>
      <div class="report-row"><span>Avg Trip Distance</span><span class="val">${o.average_trip_distance ? o.average_trip_distance.toFixed(1) + " km" : "—"}</span></div>
      <div class="report-row"><span>Avg Delivery Time</span><span class="val">${o.average_delivery_time_minutes ? o.average_delivery_time_minutes.toFixed(0) + " min" : "—"}</span></div>`;
  } catch (err) { document.getElementById("ops-analytics-body").innerHTML = err.message; }

  const reportTypes = [
    ["fleet_utilization", "Fleet Utilization"], ["fuel_consumption", "Fuel Consumption"],
    ["driver_performance", "Driver Performance"], ["delivery_performance", "Delivery Performance"],
    ["maintenance", "Maintenance"],
  ];
  document.getElementById("export-grid").innerHTML = reportTypes.map(([type, label]) => `
    <div class="export-card">
      <span>${label}</span>
      <div class="export-actions">
        <button class="btn-secondary small" onclick="downloadReport('${type}', 'pdf')">PDF</button>
        <button class="btn-secondary small" onclick="downloadReport('${type}', 'excel')">Excel</button>
      </div>
    </div>`).join("");
}

window.downloadReport = async (type, format) => {
  try {
    const res = await fetch(`${API_BASE}/reports/${type}/${format}`, {
      headers: { Authorization: "Bearer " + getToken() },
    });
    if (!res.ok) throw new Error(`Export failed (${res.status})`);
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `fleetflow_${type}_report.${format === "excel" ? "xlsx" : "pdf"}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
    toast(`${type.replace(/_/g, " ")} report downloaded`);
  } catch (err) { toast(err.message, "error"); }
};

// ---------------- Profile ----------------
async function loadProfile() {
  try {
    const me = await api("/auth/me");
    document.getElementById("topbar-user").textContent = `${me.username} · ${me.role}`;
    document.getElementById("profile-body").innerHTML = `
      <div class="prow"><span>Username</span><span>${me.username}</span></div>
      <div class="prow"><span>Email</span><span>${me.email}</span></div>
      <div class="prow"><span>Role</span><span>${badge(me.role)}</span></div>
      <div class="prow"><span>Member since</span><span>${me.created_at.slice(0, 10)}</span></div>`;
  } catch (err) { document.getElementById("profile-body").innerHTML = err.message; }
}

// ---------------- Driver views ----------------
function isToday(dateStr) {
  if (!dateStr) return false;
  const d = new Date(dateStr), now = new Date();
  return d.toDateString() === now.toDateString();
}

function tripActionButtons(trip) {
  if (trip.status === "scheduled") return `<button class="btn-primary small" onclick="doTripAction(${trip.id},'start')">Start Trip</button>`;
  if (trip.status === "in_progress" && !trip.actual_arrival) return `<button class="btn-secondary small" onclick="doTripAction(${trip.id},'arrive')">Mark Arrived</button>`;
  if (trip.status === "in_progress" && trip.actual_arrival) return `<button class="btn-primary small" onclick="openCompletionModal(${trip.id})">Complete Delivery</button>`;
  return "";
}

window.doTripAction = async (tripId, action) => {
  try {
    await api(`/trips/${tripId}/${action}`, { method: "POST" });
    toast(`Trip ${action === "start" ? "started — location tracking active" : "marked arrived"}`);
    if (action === "start") startLocationTracking(tripId);
    loadView(document.querySelector(".nav-item.active").dataset.view);
  } catch (err) { toast(err.message, "error"); }
};

// ---------------- Live location tracking (browser Geolocation API) ----------------
// Polls the backend every 20s with the driver's current position while a
// trip is in progress — no persistent WebSocket, which keeps this working
// on Vercel's serverless functions. This is real browser-reported location,
// not simulated, but it's only as "live" as how often we poll.
let watchId = null;
let pollIntervalId = null;
let lastKnownPosition = null;

function startLocationTracking(tripId) {
  stopLocationTracking();
  if (!navigator.geolocation) {
    toast("This browser doesn't support location tracking.", "error");
    return;
  }
  const sendLocation = (lat, lng) => {
    api("/tracking/location", { method: "POST", body: JSON.stringify({ trip_id: tripId, latitude: lat, longitude: lng }) })
      .then(() => { window.__lastLocationSentAt = Date.now(); })
      .catch(() => { /* non-fatal — next poll will retry */ });
  };
  watchId = navigator.geolocation.watchPosition(
    (pos) => { lastKnownPosition = pos.coords; },
    (err) => {
      document.querySelectorAll(".location-status").forEach(el => {
        el.textContent = err.code === err.PERMISSION_DENIED
          ? "Location access is disabled. Enable browser location permission to use live tracking."
          : "Location unavailable right now.";
      });
    },
    { enableHighAccuracy: true, maximumAge: 15000 }
  );
  pollIntervalId = setInterval(() => {
    if (lastKnownPosition) sendLocation(lastKnownPosition.latitude, lastKnownPosition.longitude);
  }, 20000);
  // Send an initial reading right away rather than waiting a full interval.
  if (navigator.geolocation.getCurrentPosition) {
    navigator.geolocation.getCurrentPosition(pos => sendLocation(pos.coords.latitude, pos.coords.longitude));
  }
}

function stopLocationTracking() {
  if (watchId !== null) { navigator.geolocation.clearWatch(watchId); watchId = null; }
  if (pollIntervalId !== null) { clearInterval(pollIntervalId); pollIntervalId = null; }
}

// Resume tracking automatically if the driver has an in-progress trip when
// the dashboard loads (e.g. after a page refresh mid-trip).
function resumeTrackingIfActive(trips) {
  const active = trips.find(t => t.status === "in_progress");
  if (active) startLocationTracking(active.id);
  else stopLocationTracking();
}

// ---------------- Completion note modal ----------------
window.openCompletionModal = (tripId) => {
  document.querySelectorAll(".modal").forEach(m => m.classList.add("hidden"));
  const modal = document.getElementById("completion-modal");
  modal.reset();
  modal.dataset.tripId = tripId;
  modal.classList.remove("hidden");
  document.getElementById("modal-overlay").classList.remove("hidden");
};

document.getElementById("completion-modal").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const tripId = form.dataset.tripId;
  const msg = form.querySelector(".form-msg");
  const payload = { completion_note: form.querySelector('[name="completion_note"]').value };
  if (lastKnownPosition) {
    payload.completion_lat = lastKnownPosition.latitude;
    payload.completion_lng = lastKnownPosition.longitude;
  }
  try {
    await api(`/trips/${tripId}/complete`, { method: "POST", body: JSON.stringify(payload) });
    toast("Delivery marked complete");
    stopLocationTracking();
    document.getElementById("modal-overlay").classList.add("hidden");
    loadView(document.querySelector(".nav-item.active").dataset.view);
  } catch (err) { msg.textContent = err.message; msg.className = "form-msg error"; }
});

function trackingStatusLine(trip) {
  if (trip.status !== "in_progress") return "";
  return `<div class="location-status">Live location — starting…</div>`;
}

function tripCard(trip, shipment) {
  return `
    <div class="trip-card">
      <div class="trip-card-header">
        <strong>Trip #${trip.id}</strong> ${badge(trip.status)}
        <span class="trip-card-vehicle">${trip.vehicle_registration || ""}</span>
      </div>
      ${shipment ? `<div class="trip-card-route">${shipment.origin} → ${shipment.destination}</div>` : ""}
      <div class="trip-card-meta">
        Scheduled: ${trip.scheduled_start ? new Date(trip.scheduled_start).toLocaleString() : "—"}<br>
        ${trip.actual_start ? `Started: ${new Date(trip.actual_start).toLocaleString()}<br>` : ""}
        ${trip.actual_arrival ? `Arrived: ${new Date(trip.actual_arrival).toLocaleString()}<br>` : ""}
        ${trip.actual_end ? `Completed: ${new Date(trip.actual_end).toLocaleString()}<br>` : ""}
        Distance: ${trip.total_distance_km ?? "—"} km
      </div>
      ${trackingStatusLine(trip)}
      <div class="trip-card-actions">${tripActionButtons(trip)}</div>
    </div>`;
}

async function loadDriverDashboard() {
  const cardsEl = document.getElementById("driver-summary-cards");
  const todayEl = document.getElementById("driver-today");
  const activeEl = document.getElementById("driver-active-trips");
  try {
    const [trips, shipments] = await Promise.all([api("/trips/"), api("/shipments/")]);
    const shipmentByTrip = {};
    shipments.forEach(s => { if (s.trip_id) shipmentByTrip[s.trip_id] = s; });

    const todayTrips = trips.filter(t => isToday(t.scheduled_start));
    const activeTrips = trips.filter(t => t.status === "scheduled" || t.status === "in_progress");
    const completedCount = trips.filter(t => t.status === "completed").length;

    cardsEl.innerHTML = [
      ["Today's Trips", todayTrips.length], ["Active/Upcoming", activeTrips.length],
      ["Completed Trips", completedCount], ["Assigned Shipments", shipments.length],
    ].map(([label, val], i) => `<div class="stat-card${i === 0 ? " accent" : ""}"><div class="stat-label">${label}</div><div class="stat-value">${val}</div></div>`).join("");

    todayEl.innerHTML = todayTrips.length
      ? todayTrips.map(t => tripCard(t, shipmentByTrip[t.id])).join("")
      : `<div class="loading">No trips scheduled for today.</div>`;

    activeEl.innerHTML = activeTrips.length
      ? activeTrips.map(t => tripCard(t, shipmentByTrip[t.id])).join("")
      : `<div class="loading">No active or upcoming trips.</div>`;

    resumeTrackingIfActive(trips);
    refreshLocationStatusLabels();
  } catch (err) {
    cardsEl.innerHTML = `<div class="loading">${err.message}</div>`;
    todayEl.innerHTML = ""; activeEl.innerHTML = "";
  }
}

function refreshLocationStatusLabels() {
  document.querySelectorAll(".location-status").forEach(el => {
    if (!navigator.geolocation) { el.textContent = "This browser doesn't support location tracking."; return; }
    el.textContent = lastKnownPosition ? "Live location — active" : "Live location — waiting for GPS fix…";
  });
}
setInterval(() => {
  document.querySelectorAll(".location-status").forEach(el => {
    if (el.textContent.startsWith("Live location — active") && window.__lastLocationSentAt) {
      const secs = Math.round((Date.now() - window.__lastLocationSentAt) / 1000);
      el.textContent = `Live location — last updated ${secs}s ago`;
    }
  });
}, 5000);

async function loadMyTrips() {
  const el = document.getElementById("my-trips-list");
  try {
    const [trips, shipments] = await Promise.all([api("/trips/"), api("/shipments/")]);
    const shipmentByTrip = {};
    shipments.forEach(s => { if (s.trip_id) shipmentByTrip[s.trip_id] = s; });
    el.innerHTML = trips.length
      ? trips.map(t => tripCard(t, shipmentByTrip[t.id])).join("")
      : `<div class="loading">No trips assigned yet.</div>`;
  } catch (err) { el.innerHTML = `<div class="loading">${err.message}</div>`; }
}

async function loadMyShipments() {
  const body = document.getElementById("my-shipments-body");
  try {
    const shipments = await api("/shipments/");
    body.innerHTML = shipments.length ? shipments.map(s => `
      <tr><td class="mono">${s.tracking_number}</td><td>${s.origin}</td><td>${s.destination}</td>
      <td>${badge(s.status)}</td><td>${s.eta ? new Date(s.eta).toLocaleString() : "—"}</td></tr>`).join("")
      : `<tr><td colspan="5" class="loading">No shipments assigned yet.</td></tr>`;
  } catch (err) { body.innerHTML = `<tr><td colspan="5" class="loading">${err.message}</td></tr>`; }
}

// ---------------- User Management (Admin only) ----------------
async function loadUsers() {
  const body = document.getElementById("users-body");
  try {
    const users = await api("/auth/users");
    body.innerHTML = users.map(u => `
      <tr>
        <td>${u.username}</td><td>${u.email}</td>
        <td>${badge(u.role)}</td>
        <td class="mono">${u.driver_id ?? "—"}</td>
        <td>${u.is_active === "true" ? badge("active") : badge("disabled")}</td>
        <td class="row-actions">
          <button class="btn-secondary small" onclick="toggleUserActive(${u.id}, '${u.is_active}')" ${u.id === currentUser.id ? "disabled" : ""}>
            ${u.is_active === "true" ? "Disable" : "Enable"}
          </button>
          <button class="btn-secondary small" onclick="resetUserPassword(${u.id}, '${u.username}')">Reset Password</button>
        </td>
      </tr>`).join("");
  } catch (err) { body.innerHTML = `<tr><td colspan="6" class="loading">${err.message}</td></tr>`; }
}

window.toggleUserActive = async (id, currentlyActive) => {
  try {
    await api(`/auth/users/${id}`, { method: "PUT", body: JSON.stringify({ is_active: currentlyActive === "true" ? "false" : "true" }) });
    toast("User updated"); loadUsers();
  } catch (err) { toast(err.message, "error"); }
};

window.resetUserPassword = async (id, username) => {
  const newPassword = prompt(`New password for ${username} (min 6 characters):`);
  if (!newPassword) return;
  try {
    await api(`/auth/users/${id}/reset-password`, { method: "POST", body: JSON.stringify({ new_password: newPassword }) });
    toast(`Password reset for ${username}`);
  } catch (err) { toast(err.message, "error"); }
};

window.openUserModal = async () => {
  document.querySelectorAll(".modal").forEach(m => m.classList.add("hidden"));
  const modal = document.getElementById("user-modal");
  modal.reset();
  modal.classList.remove("hidden");
  document.getElementById("modal-overlay").classList.remove("hidden");
  document.getElementById("user-modal-driver-label").classList.add("hidden");
  document.getElementById("user-modal-driver").classList.add("hidden");
};

document.getElementById("user-modal-role").addEventListener("change", async (e) => {
  const isDriver = e.target.value === "driver";
  document.getElementById("user-modal-driver-label").classList.toggle("hidden", !isDriver);
  const sel = document.getElementById("user-modal-driver");
  sel.classList.toggle("hidden", !isDriver);
  if (isDriver && !sel.dataset.loaded) {
    try {
      const drivers = await api("/drivers/");
      sel.innerHTML = drivers.map(d => `<option value="${d.id}">${d.name} (${d.license_number})</option>`).join("");
      sel.dataset.loaded = "true";
    } catch (err) { /* Admin always has drivers access; ignore transient failure */ }
  }
});

document.getElementById("user-modal").addEventListener("submit", async (e) => {
  e.preventDefault();
  const form = e.target;
  const msg = form.querySelector(".form-msg");
  const payload = {
    username: form.username.value, email: form.email.value, password: form.password.value, role: form.role.value,
  };
  if (form.role.value === "driver" && form.driver_id.value) payload.driver_id = parseInt(form.driver_id.value, 10);
  try {
    await api("/auth/users", { method: "POST", body: JSON.stringify(payload) });
    toast("User created");
    document.getElementById("modal-overlay").classList.add("hidden");
    loadUsers();
  } catch (err) { msg.textContent = err.message; msg.className = "form-msg error"; }
});

// ---------------- Modals ----------------
const overlay = document.getElementById("modal-overlay");
document.querySelectorAll("[data-modal]").forEach(btn => {
  btn.addEventListener("click", async () => {
    document.querySelectorAll(".modal").forEach(m => m.classList.add("hidden"));
    const modal = document.getElementById(btn.dataset.modal);
    modal.classList.remove("hidden");
    overlay.classList.remove("hidden");
    await populateModalSelects(btn.dataset.modal);
  });
});
document.querySelectorAll("[data-close]").forEach(btn => btn.addEventListener("click", () => overlay.classList.add("hidden")));
overlay.addEventListener("click", (e) => { if (e.target === overlay) overlay.classList.add("hidden"); });

async function populateModalSelects(modalId) {
  if (modalId === "trip-modal" || modalId === "fuel-modal") {
    const drivers = await api("/drivers/").catch(() => []);
    const vehicles = await api("/vehicles/").catch(() => []);
    const form = document.getElementById(modalId);
    const driverSel = form.querySelector('[name="driver_id"]');
    const vehicleSel = form.querySelector('[name="vehicle_id"]');
    if (driverSel) driverSel.innerHTML = drivers.map(d => `<option value="${d.id}">${d.name} (${d.status})</option>`).join("");
    if (vehicleSel) vehicleSel.innerHTML = vehicles.map(v => `<option value="${v.id}">${v.registration_number} (${v.status})</option>`).join("");
    if (modalId === "trip-modal") {
      const shipments = await api("/shipments/").catch(() => []);
      const shipSel = form.querySelector('[name="shipment_id"]');
      shipSel.innerHTML = '<option value="">— none —</option>' + shipments.filter(s => !s.trip_id).map(s => `<option value="${s.id}">${s.tracking_number}</option>`).join("");
    }
  }
  if (modalId === "maintenance-modal") {
    const vehicles = await api("/vehicles/").catch(() => []);
    document.getElementById("maintenance-modal").querySelector('[name="vehicle_id"]').innerHTML =
      vehicles.map(v => `<option value="${v.id}">${v.registration_number}</option>`).join("");
  }
}

function formToObject(form) {
  const obj = {};
  new FormData(form).forEach((v, k) => { if (v !== "") obj[k] = v; });
  return obj;
}

document.getElementById("vehicle-modal").addEventListener("submit", (e) => submitModal(e, "/vehicles/", v => ({
  ...v, capacity: v.capacity ? parseFloat(v.capacity) : null,
}), loadVehicles));

document.getElementById("driver-modal").addEventListener("submit", (e) => submitModal(e, "/drivers/", v => v, loadDrivers));

document.getElementById("shipment-modal").addEventListener("submit", (e) => submitModal(e, "/shipments/", v => v, loadShipments));

document.getElementById("trip-modal").addEventListener("submit", (e) => submitModal(e, "/trips/", v => ({
  driver_id: parseInt(v.driver_id), vehicle_id: parseInt(v.vehicle_id),
  shipment_ids: v.shipment_id ? [parseInt(v.shipment_id)] : undefined,
}), () => { loadTrips(); loadDashboard(); }));

document.getElementById("fuel-modal").addEventListener("submit", (e) => submitModal(e, "/fuel/", v => ({
  ...v, vehicle_id: parseInt(v.vehicle_id), driver_id: parseInt(v.driver_id),
  fuel_quantity_liters: parseFloat(v.fuel_quantity_liters), fuel_cost: parseFloat(v.fuel_cost),
  odometer_reading: v.odometer_reading ? parseFloat(v.odometer_reading) : null,
}), () => { loadFuel(); loadDashboard(); }));

document.getElementById("maintenance-modal").addEventListener("submit", (e) => submitModal(e, "/maintenance/", v => ({
  ...v, vehicle_id: parseInt(v.vehicle_id),
  service_date: v.service_date + "T00:00:00",
  next_service_date: v.next_service_date ? v.next_service_date + "T00:00:00" : null,
  service_cost: v.service_cost ? parseFloat(v.service_cost) : null,
}), () => { loadMaintenance(); loadDashboard(); }));

async function submitModal(e, endpoint, transform, refresh) {
  e.preventDefault();
  const form = e.target;
  const msgEl = form.querySelector(".form-msg");
  msgEl.textContent = ""; msgEl.className = "form-msg";
  try {
    const payload = transform(formToObject(form));
    await api(endpoint, { method: "POST", body: JSON.stringify(payload) });
    toast("Saved successfully");
    form.reset();
    overlay.classList.add("hidden");
    refresh();
  } catch (err) {
    msgEl.textContent = err.message; msgEl.className = "form-msg error";
  }
}

// ---------------- Boot ----------------
if (getToken()) { showApp(); } else { showLogin(); checkBootstrapStatus(); }
