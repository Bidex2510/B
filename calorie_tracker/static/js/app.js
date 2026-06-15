/* ── CalTrack frontend ──────────────────────────────────── */

const $ = id => document.getElementById(id);
const MEALS = ["breakfast", "lunch", "dinner", "snack"];
const MEAL_LABELS = { breakfast: "🌅 Breakfast", lunch: "☀️ Lunch", dinner: "🌙 Dinner", snack: "🍎 Snack" };
const MACRO_COLORS = { protein: "#43c98e", carbs: "#4fc3f7", fat: "#f7a13a" };

let currentDate = new Date();
let selectedFood = null;
let calorieRingChart = null;
let macroPieChart = null;
let calorieTrendChart = null;
let macroTrendChart = null;
let weightTrendChart = null;
let weightChartInst = null;
let profile = {};
let scannerRunning = false;

// ── date helpers ──────────────────────────────────────────

function fmtDate(d) {
  return d.toISOString().split("T")[0];
}
function prettyDate(d) {
  const today = new Date();
  const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
  if (fmtDate(d) === fmtDate(today)) return "Today";
  if (fmtDate(d) === fmtDate(yesterday)) return "Yesterday";
  return d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });
}

// ── toast ─────────────────────────────────────────────────

function toast(msg, ms = 2200) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  clearTimeout(el._t);
  el._t = setTimeout(() => el.classList.add("hidden"), ms);
}

// ── API helpers ───────────────────────────────────────────

async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body) opts.body = JSON.stringify(body);
  const r = await fetch(path, opts);
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}
const GET  = path => api("GET", path);
const POST = (path, b) => api("POST", path, b);
const PUT  = (path, b) => api("PUT", path, b);
const DEL  = path => api("DELETE", path);

// ── nav ───────────────────────────────────────────────────

function navigate(page) {
  document.querySelectorAll(".page").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-link").forEach(a => a.classList.remove("active"));
  $(`page-${page}`).classList.add("active");
  document.querySelector(`[data-page="${page}"]`).classList.add("active");

  if (page === "dashboard") loadDashboard();
  if (page === "trends") loadTrends(7);
  if (page === "water") loadWater();
  if (page === "weight") loadWeightPage();
  if (page === "profile") loadProfile();
}

document.querySelectorAll(".nav-link").forEach(a => {
  a.addEventListener("click", e => {
    e.preventDefault();
    navigate(a.dataset.page);
    $("sidebar").classList.remove("open"); // mobile
  });
});
$("menuBtn").addEventListener("click", () => {
  document.querySelector(".sidebar").classList.toggle("open");
});

$("prevDay").addEventListener("click", () => {
  currentDate.setDate(currentDate.getDate() - 1);
  updateDateLabel();
  loadDashboard();
});
$("nextDay").addEventListener("click", () => {
  const tomorrow = new Date(); tomorrow.setDate(tomorrow.getDate() + 1);
  if (currentDate < tomorrow) {
    currentDate.setDate(currentDate.getDate() + 1);
    updateDateLabel();
    loadDashboard();
  }
});
function updateDateLabel() {
  $("currentDateLabel").textContent = prettyDate(currentDate);
}

// ── DASHBOARD ─────────────────────────────────────────────

async function loadDashboard() {
  const date = fmtDate(currentDate);
  const [summary, logs] = await Promise.all([
    GET(`/api/summary?date=${date}`),
    GET(`/api/log?date=${date}`),
  ]);

  // calorie ring
  const { calories: eaten } = summary.totals;
  const { calories: goal } = summary.goals;
  const remaining = Math.max(0, goal - eaten);
  $("calConsumed").textContent = Math.round(eaten);
  $("calGoal").textContent = goal;
  $("calRemaining").textContent = Math.round(remaining);
  drawCalorieRing(eaten, goal);

  // macro bars + pie
  drawMacros(summary.totals, summary.goals);

  // meal sections
  drawMealSections(logs);
}

function drawCalorieRing(eaten, goal) {
  const ctx = $("calorieRing").getContext("2d");
  const pct = Math.min(eaten / goal, 1);
  const over = eaten > goal;

  if (calorieRingChart) calorieRingChart.destroy();
  calorieRingChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      datasets: [{
        data: [pct, 1 - pct],
        backgroundColor: [over ? "#ff6584" : "#6c63ff", "#22263a"],
        borderWidth: 0,
        borderRadius: 8,
      }],
    },
    options: {
      cutout: "75%",
      plugins: { legend: { display: false }, tooltip: { enabled: false } },
      animation: { animateRotate: true, duration: 600 },
    },
  });
}

function drawMacros(totals, goals) {
  const macros = [
    { key: "protein_g", label: "Protein", goal: goals.protein_g, cls: "bar-protein" },
    { key: "carbs_g",   label: "Carbs",   goal: goals.carbs_g,   cls: "bar-carbs" },
    { key: "fat_g",     label: "Fat",     goal: goals.fat_g,     cls: "bar-fat" },
  ];

  $("macroBars").innerHTML = macros.map(m => {
    const val = totals[m.key] || 0;
    const pct = Math.min((val / (m.goal || 1)) * 100, 100);
    return `
      <div class="macro-bar-wrap">
        <div class="macro-bar-label">
          <span>${m.label}</span>
          <span>${Math.round(val)}g / ${m.goal}g</span>
        </div>
        <div class="macro-bar-track">
          <div class="macro-bar-fill ${m.cls}" style="width:${pct}%"></div>
        </div>
      </div>`;
  }).join("");

  // pie
  const ctx = $("macroPie").getContext("2d");
  if (macroPieChart) macroPieChart.destroy();
  const p = totals.protein_g || 0.1, c = totals.carbs_g || 0.1, f = totals.fat_g || 0.1;
  macroPieChart = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels: ["Protein", "Carbs", "Fat"],
      datasets: [{ data: [p, c, f], backgroundColor: ["#43c98e", "#4fc3f7", "#f7a13a"], borderWidth: 0 }],
    },
    options: {
      cutout: "60%",
      plugins: {
        legend: { position: "bottom", labels: { color: "#8b93b5", font: { size: 11 } } },
        tooltip: { callbacks: { label: ctx => `${ctx.label}: ${Math.round(ctx.parsed)}g` } },
      },
    },
  });
}

function drawMealSections(logs) {
  const byMeal = {};
  MEALS.forEach(m => byMeal[m] = []);
  logs.forEach(l => (byMeal[l.meal_type] || (byMeal["snack"] = [])).push(l));

  $("mealSections").innerHTML = MEALS.map(meal => {
    const items = byMeal[meal] || [];
    const totalCal = items.reduce((s, i) => s + i.calories, 0);
    const rows = items.length
      ? items.map(i => `
        <div class="food-row">
          <div class="food-row-left">
            <div class="food-name">${escHtml(i.food_name)}${i.brand ? ` <small style="color:var(--muted)">${escHtml(i.brand)}</small>` : ""}</div>
            <div class="food-qty">${i.quantity_g}g</div>
          </div>
          <div class="food-row-right">
            <div>
              <div class="food-cal">${Math.round(i.calories)} kcal</div>
              <div class="food-macros">P${Math.round(i.protein_g)}g · C${Math.round(i.carbs_g)}g · F${Math.round(i.fat_g)}g</div>
            </div>
            <button class="delete-btn" data-id="${i.id}">✕</button>
          </div>
        </div>`).join("")
      : `<div class="empty-meal">No items logged yet</div>`;

    return `
      <div class="meal-section">
        <div class="meal-header" data-meal="${meal}">
          <span>${MEAL_LABELS[meal]}</span>
          <span class="meal-kcal">${Math.round(totalCal)} kcal</span>
          <button class="meal-add-btn" data-meal="${meal}">+</button>
        </div>
        <div class="meal-items">${rows}</div>
      </div>`;
  }).join("");

  // delete handlers
  document.querySelectorAll(".delete-btn").forEach(btn => {
    btn.addEventListener("click", async e => {
      e.stopPropagation();
      await DEL(`/api/log/${btn.dataset.id}`);
      toast("Removed");
      loadDashboard();
    });
  });

  // meal add → navigate to log
  document.querySelectorAll(".meal-add-btn").forEach(btn => {
    btn.addEventListener("click", e => {
      e.stopPropagation();
      $("mealType").value = btn.dataset.meal;
      navigate("log");
    });
  });
}

// ── FAB ───────────────────────────────────────────────────

$("fabAdd").addEventListener("click", () => navigate("log"));

// ── LOG FOOD PAGE ─────────────────────────────────────────

let searchDebounce;
$("foodSearch").addEventListener("input", () => {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(doSearch, 350);
});

async function doSearch() {
  const q = $("foodSearch").value.trim();
  if (q.length < 2) { $("searchResults").innerHTML = ""; return; }
  try {
    const results = await GET(`/api/food/search?q=${encodeURIComponent(q)}`);
    $("searchResults").innerHTML = results.map(r => `
      <div class="search-item" data-food='${escAttr(JSON.stringify(r))}'>
        <div>
          <div class="search-item-name">${escHtml(r.name)}
            ${r.brand ? `<span style="color:var(--muted);font-size:12px"> · ${escHtml(r.brand)}</span>` : ""}
            <span class="source-badge">${r.source}</span>
          </div>
          <div class="search-item-meta">per ${r.serving_size_g}${r.serving_unit || "g"}</div>
        </div>
        <div class="search-item-cal">${Math.round(r.calories || 0)} kcal</div>
      </div>`).join("") || `<div style="color:var(--muted);padding:10px">No results found</div>`;

    document.querySelectorAll(".search-item").forEach(el => {
      el.addEventListener("click", () => selectFood(JSON.parse(el.dataset.food)));
    });
  } catch (e) { console.error(e); }
}

function selectFood(food) {
  selectedFood = food;
  $("logFoodName").textContent = food.name + (food.brand ? ` · ${food.brand}` : "");
  $("logForm").classList.remove("hidden");
  updatePreview();
  $("logForm").scrollIntoView({ behavior: "smooth" });
}

$("quantity").addEventListener("input", updatePreview);

function updatePreview() {
  if (!selectedFood) return;
  const qty = parseFloat($("quantity").value) || 100;
  const ratio = qty / (selectedFood.serving_size_g || 100);
  const cal = Math.round((selectedFood.calories || 0) * ratio);
  const n = selectedFood.nutrients || {};
  const protein = round1((selectedFood.protein_g || n[1003] || 0) * ratio);
  const carbs   = round1((selectedFood.carbs_g   || n[1005] || 0) * ratio);
  const fat     = round1((selectedFood.fat_g     || n[1004] || 0) * ratio);

  $("nutritionPreview").innerHTML = `
    <div class="preview-pill">🔥 <b>${cal}</b> kcal</div>
    <div class="preview-pill">🥩 P <b>${protein}g</b></div>
    <div class="preview-pill">🍚 C <b>${carbs}g</b></div>
    <div class="preview-pill">🧈 F <b>${fat}g</b></div>`;
}

$("logFoodBtn").addEventListener("click", async () => {
  if (!selectedFood) return;
  const qty = parseFloat($("quantity").value) || 100;
  const payload = {
    meal_type: $("mealType").value,
    quantity_g: qty,
    date: fmtDate(currentDate),
  };
  if (selectedFood.id) {
    payload.food_item_id = selectedFood.id;
  } else {
    // USDA or custom — send food_data to create on the fly
    const n = selectedFood.nutrients || {};
    payload.food_data = {
      name: selectedFood.name,
      brand: selectedFood.brand || null,
      usda_fdc_id: selectedFood.usda_fdc_id || null,
      serving_size_g: selectedFood.serving_size_g || 100,
      serving_unit: selectedFood.serving_unit || "g",
      calories: selectedFood.calories || 0,
      protein_g: selectedFood.protein_g || n[1003] || 0,
      carbs_g: selectedFood.carbs_g   || n[1005] || 0,
      fat_g: selectedFood.fat_g       || n[1004] || 0,
      fiber_g: n[1079] || 0,
      sugar_g: n[2000] || 0,
      sodium_mg: n[1093] || 0,
    };
  }
  try {
    await POST("/api/log", payload);
    toast("✅ Food logged!");
    selectedFood = null;
    $("logForm").classList.add("hidden");
    $("foodSearch").value = "";
    $("searchResults").innerHTML = "";
  } catch (e) { toast("❌ Error logging food"); console.error(e); }
});

// custom food save
$("cfSaveBtn").addEventListener("click", async () => {
  const name = $("cfName").value.trim();
  if (!name) { toast("Enter a food name"); return; }
  await POST("/api/food", {
    name,
    calories: parseFloat($("cfCal").value) || 0,
    protein_g: parseFloat($("cfProtein").value) || 0,
    carbs_g:   parseFloat($("cfCarbs").value) || 0,
    fat_g:     parseFloat($("cfFat").value) || 0,
    serving_size_g: 100,
  });
  toast(`✅ "${name}" saved to database`);
  ["cfName","cfCal","cfProtein","cfCarbs","cfFat"].forEach(id => $(id).value = "");
});

// ── BARCODE SCANNER ───────────────────────────────────────

$("barcodeBtn").addEventListener("click", () => {
  if (scannerRunning) { stopScanner(); return; }
  startScanner();
});
$("closeScannerBtn").addEventListener("click", stopScanner);

function startScanner() {
  $("barcodeScanner").classList.remove("hidden");
  scannerRunning = true;
  Quagga.init({
    inputStream: {
      name: "Live",
      type: "LiveStream",
      target: $("scannerViewport"),
      constraints: { facingMode: "environment" },
    },
    decoder: { readers: ["ean_reader", "upc_reader", "code_128_reader"] },
  }, err => {
    if (err) { toast("Camera not available"); stopScanner(); return; }
    Quagga.start();
    Quagga.onDetected(onBarcodeDetected);
  });
}

function stopScanner() {
  if (scannerRunning) { Quagga.stop(); scannerRunning = false; }
  $("barcodeScanner").classList.add("hidden");
}

async function onBarcodeDetected(result) {
  const code = result.codeResult.code;
  stopScanner();
  toast(`🔍 Looking up barcode ${code}…`);
  try {
    const food = await GET(`/api/food/barcode/${code}`);
    selectFood(food);
  } catch {
    toast("Product not found. Try searching manually.");
  }
}

// ── TRENDS PAGE ───────────────────────────────────────────

document.querySelectorAll(".trend-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".trend-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    loadTrends(parseInt(btn.dataset.days));
  });
});

async function loadTrends(days) {
  const data = await GET(`/api/trends?days=${days}`);
  const labels = data.map(d => d.date);

  // calorie trend
  destroyChart(calorieTrendChart);
  calorieTrendChart = new Chart($("calorieTrend").getContext("2d"), {
    type: "bar",
    data: {
      labels,
      datasets: [{
        label: "Calories",
        data: data.map(d => d.calories),
        backgroundColor: "rgba(108,99,255,0.6)",
        borderColor: "#6c63ff",
        borderWidth: 1,
        borderRadius: 6,
      }],
    },
    options: lineOpts("Calorie Intake (kcal)"),
  });

  // macro trend
  destroyChart(macroTrendChart);
  macroTrendChart = new Chart($("macroTrend").getContext("2d"), {
    type: "line",
    data: {
      labels,
      datasets: [
        lineDs("Protein (g)", data.map(d => d.protein), "#43c98e"),
        lineDs("Carbs (g)",   data.map(d => d.carbs),   "#4fc3f7"),
        lineDs("Fat (g)",     data.map(d => d.fat),     "#f7a13a"),
      ],
    },
    options: lineOpts("Macronutrients (g)"),
  });

  // weight trend
  destroyChart(weightTrendChart);
  const wData = data.map(d => d.weight);
  weightTrendChart = new Chart($("weightTrend").getContext("2d"), {
    type: "line",
    data: {
      labels,
      datasets: [lineDs("Weight (kg)", wData, "#ff6584", true)],
    },
    options: lineOpts("Body Weight (kg)"),
  });
}

function lineOpts(title) {
  return {
    responsive: true,
    plugins: {
      legend: { labels: { color: "#8b93b5" } },
      title: { display: true, text: title, color: "#e8eaf6", font: { size: 14 } },
    },
    scales: {
      x: { ticks: { color: "#8b93b5" }, grid: { color: "#2d3250" } },
      y: { ticks: { color: "#8b93b5" }, grid: { color: "#2d3250" } },
    },
  };
}
function lineDs(label, data, color, fill = false) {
  return {
    label, data,
    borderColor: color,
    backgroundColor: color + "33",
    pointBackgroundColor: color,
    tension: 0.3, fill,
  };
}
function destroyChart(c) { if (c) c.destroy(); }

// ── WATER PAGE ────────────────────────────────────────────

async function loadWater() {
  const s = await GET(`/api/summary?date=${fmtDate(currentDate)}`);
  updateWaterUI(s.water_ml, s.water_goal_ml);
}

function updateWaterUI(consumed, goal) {
  const pct = Math.min(Math.round((consumed / goal) * 100), 100);
  $("waterConsumed").textContent = consumed + " ml";
  $("waterGoal").textContent = `/ ${goal} ml`;
  $("waterPct").textContent = pct + "%";
  $("waterFill").style.height = pct + "%";
}

document.querySelectorAll(".water-btn").forEach(btn => {
  btn.addEventListener("click", async () => {
    await POST("/api/water", { amount_ml: parseInt(btn.dataset.ml), date: fmtDate(currentDate) });
    toast(`💧 +${btn.dataset.ml}ml logged`);
    loadWater();
  });
});

$("addCustomWater").addEventListener("click", async () => {
  const ml = parseInt($("customWater").value);
  if (!ml || ml <= 0) return;
  await POST("/api/water", { amount_ml: ml, date: fmtDate(currentDate) });
  toast(`💧 +${ml}ml logged`);
  $("customWater").value = "";
  loadWater();
});

// ── WEIGHT PAGE ───────────────────────────────────────────

async function loadWeightPage() {
  const data = await GET("/api/trends?days=30");
  const labels = data.map(d => d.date);
  const weights = data.map(d => d.weight);

  destroyChart(weightChartInst);
  weightChartInst = new Chart($("weightChart").getContext("2d"), {
    type: "line",
    data: {
      labels,
      datasets: [lineDs("Weight (kg)", weights, "#ff6584", true)],
    },
    options: lineOpts("30-Day Weight Trend"),
  });
}

$("logWeightBtn").addEventListener("click", async () => {
  const w = parseFloat($("weightInput").value);
  if (!w || w <= 0) { toast("Enter a valid weight"); return; }
  await POST("/api/weight", { weight_kg: w, date: fmtDate(currentDate) });
  toast(`✅ Weight ${w}kg logged`);
  $("weightInput").value = "";
  loadWeightPage();
});

// ── PROFILE PAGE ──────────────────────────────────────────

async function loadProfile() {
  profile = await GET("/api/profile");
  $("pName").value     = profile.name;
  $("pAge").value      = profile.age;
  $("pSex").value      = profile.sex;
  $("pWeight").value   = profile.weight_kg;
  $("pHeight").value   = profile.height_cm;
  $("pActivity").value = profile.activity_level;
  $("pGoal").value     = profile.goal;
  $("pWater").value    = profile.water_goal_ml;
  renderGoalGrid(profile);
}

function renderGoalGrid(p) {
  $("goalGrid").innerHTML = [
    { label: "Daily Calories", val: p.calorie_goal + " kcal", color: "#6c63ff" },
    { label: "Protein",        val: p.protein_goal + " g",    color: "#43c98e" },
    { label: "Carbohydrates",  val: p.carbs_goal   + " g",    color: "#4fc3f7" },
    { label: "Fat",            val: p.fat_goal     + " g",    color: "#f7a13a" },
  ].map(g => `
    <div class="goal-item">
      <div class="goal-item-label">${g.label}</div>
      <div class="goal-item-val" style="color:${g.color}">${g.val}</div>
    </div>`).join("");
}

$("saveProfileBtn").addEventListener("click", async () => {
  const body = {
    name:           $("pName").value,
    age:            parseInt($("pAge").value),
    sex:            $("pSex").value,
    weight_kg:      parseFloat($("pWeight").value),
    height_cm:      parseFloat($("pHeight").value),
    activity_level: $("pActivity").value,
    goal:           $("pGoal").value,
    water_goal_ml:  parseInt($("pWater").value),
  };
  const updated = await PUT("/api/profile", body);
  profile = { ...profile, ...body, ...updated };
  renderGoalGrid(profile);
  $("profileSaved").classList.remove("hidden");
  setTimeout(() => $("profileSaved").classList.add("hidden"), 3000);
});

// ── utils ─────────────────────────────────────────────────

function escHtml(s) {
  return String(s || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}
function escAttr(s) {
  return String(s || "").replace(/'/g,"&#39;").replace(/"/g,"&quot;");
}
function round1(n) { return Math.round(n * 10) / 10; }

// ── init ──────────────────────────────────────────────────

async function init() {
  updateDateLabel();
  // seed common foods on first run
  try { await POST("/api/seed"); } catch {}
  // load profile to get goals
  profile = await GET("/api/profile");
  navigate("dashboard");
}

init();
