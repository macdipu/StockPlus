/* DSE Live Analyzer — router + market-wide views (Market, Scanner, Data, Tools) + stock extras.
   Relies on globals from index.html: API, $, esc, num, pct, cls, getJSON, state, open. */
"use strict";
const App = (() => {
  const view = () => $("view");
  let current = null, depthTimer = null, universeHandler = null;

  // ---------------------------------------------------------------- router
  function show(name) {
    current = name;
    $("main").hidden = name !== "stock";
    view().hidden = name === "stock";
    document.querySelectorAll("#tabs a").forEach(a => a.classList.toggle("on", a.getAttribute("href").startsWith(`#/${name}`)));
    if (name !== "stock" && depthTimer) { clearInterval(depthTimer); depthTimer = null; }
    universeHandler = null;
  }

  function route(fallback) {
    const [, name = "stock", arg] = location.hash.split("/");
    if (name === "stock") return open(arg || state.symbol || fallback);
    show(name);
    ({market: market, scanner: scannerView, data: dataView, tools: tools}[name] || market)(arg);
  }

  window.addEventListener("universe", e => { if (universeHandler) universeHandler(e.detail); });

  // ---------------------------------------------------------------- table component
  const FMT = {
    change_pct: v => `<span class="${cls(v)}">${pct(v, 2)}</span>`, percent: v => `<span class="${cls(v)}">${pct(v, 2)}</span>`,
    avg_change_pct: v => `<span class="${cls(v)}">${pct(v, 2)}</span>`,
    ret_1w: v => `<span class="${cls(v)}">${pct(v)}</span>`, ret_1m: v => `<span class="${cls(v)}">${pct(v)}</span>`,
    ret_3m: v => `<span class="${cls(v)}">${pct(v)}</span>`, ret_1y: v => `<span class="${cls(v)}">${pct(v)}</span>`,
    graham_gap_pct: v => `<span class="${cls(v)}">${pct(v, 0)}</span>`,
    pct_from_52w_high: v => pct(v), pct_from_52w_low: v => pct(v), range_position_pct: v => `${num(v, 0)}%`,
    patterns: v => esc((v || []).join(", ")), vol_ratio: v => v == null ? "–" : `${num(v)}×`,
    market_cap: v => num(v / 1e7, 0) + " cr", volume: v => num(v, 0), trades: v => num(v, 0), setup_score: v => v == null ? "–" : `${v}/6`,
    vpa: v => v ? `<span class="${/buying|Stopping|supply/.test(v) ? "up" : /selling|Upthrust|demand/.test(v) ? "dn" : ""}">${esc(v)}</span>` : "–",
  };
  const LABEL = {symbol: "Symbol", sector: "Sector", category: "Cat", ltp: "LTP", change_pct: "Chg %", value_mn: "Value mn",
    vol_ratio: "Vol/avg", rsi14: "RSI", setup_score: "Setup", vpa: "VPA", patterns: "Patterns", pe: "P/E", pb: "P/B",
    pct_from_52w_high: "vs 52w high", eps_ttm: "EPS TTM", nav: "NAV", dividend_yield_pct: "Yield %", sponsor_pct: "Sponsor %",
    free_float_pct: "Float %", market_cap: "Mkt cap", graham: "Graham", graham_gap_pct: "Graham gap", ret_1m: "1M", ret_3m: "3M",
    ret_1y: "1Y", name: "Name", macd_hist: "MACD hist", atr_pct: "ATR %", bb_width_pctile: "BB width pctile", percent: "Chg %",
    value: "Value mn", range_position_pct: "In range", low_52w: "52w low", high_52w: "52w high", instruments: "Stocks",
    advanced: "▲", declined: "▼", avg_change_pct: "Avg chg %", turnover_mn: "Turnover mn", turnover_share_pct: "Share %",
    median_pe: "Median P/E", weighted_pe: "Weighted P/E", avg_rsi: "Avg RSI", ret_6m: "6M", ret_1w: "1W"};

  function table(el, rows, cols, opts = {}) {
    let sortKey = opts.sort || null, desc = true;
    const draw = () => {
      const data = sortKey ? [...rows].sort((a, b) => {
        const x = a[sortKey], y = b[sortKey];
        if (x == null) return 1; if (y == null) return -1;
        return (x > y ? 1 : x < y ? -1 : 0) * (desc ? -1 : 1);
      }) : rows;
      el.innerHTML = `<div class="tablewrap"><table><thead><tr>${cols.map(c => `<th class="sort" data-k="${c}">${LABEL[c] || c}${c === sortKey ? (desc ? " ▾" : " ▴") : ""}</th>`).join("")}</tr></thead>
        <tbody>${data.map(r => `<tr class="${r.symbol ? "click" : ""}" data-s="${esc(r.symbol || "")}">${cols.map(c =>
          `<td>${FMT[c] ? FMT[c](r[c]) : typeof r[c] === "number" ? num(r[c], Number.isInteger(r[c]) ? 0 : 2) : c === "symbol" ? `<b>${esc(r[c])}</b>` : esc(r[c] ?? "–")}</td>`).join("")}</tr>`).join("")
          || `<tr><td colspan="${cols.length}" class="mute">No matches</td></tr>`}</tbody></table></div>`;
      el.querySelectorAll("th.sort").forEach(th => th.onclick = () => { desc = th.dataset.k === sortKey ? !desc : true; sortKey = th.dataset.k; draw(); });
      el.querySelectorAll("tr.click").forEach(tr => tr.onclick = () => { if (tr.dataset.s) location.hash = `#/stock/${tr.dataset.s}`; });
    };
    draw();
  }

  const card = (title, id, extra = "") => `<div class="card"><h3>${title}${extra ? " · " + extra : ""}</h3><div id="${id}" class="small mute">Loading…</div></div>`;
  const fail = (id, e) => { const el = $(id); if (el) el.innerHTML = `<span class="dn">${esc(e.message)}</span>`; };

  // ---------------------------------------------------------------- Market
  async function market() {
    view().innerHTML = `${card("Sectors", "mSectors", '<span class="mute small">click a row to scan that sector</span>')}
      <div class="cols3">${card("Top gainers", "mGain")}${card("Top losers", "mLose")}${card("Most active (value)", "mValue")}</div>
      <div class="grid2">${card("P/E — market & category", "mPe")}${card("52-week range", "m52")}</div>`;
    const load = async () => {
      try {
        const s = await getJSON(`${API}/market/sectors`);
        table($("mSectors"), s.data, ["sector", "instruments", "advanced", "declined", "avg_change_pct", "turnover_mn", "turnover_share_pct", "median_pe", "avg_rsi", "ret_1m"], {sort: "turnover_mn"});
        $("mSectors").querySelectorAll("tbody tr").forEach((tr, i) => { tr.classList.add("click"); tr.onclick = () => { location.hash = `#/data/${encodeURIComponent(s.data[i].sector)}`; }; });
      } catch (e) { fail("mSectors", e); }
      for (const [id, by] of [["mGain", "gainers"], ["mLose", "losers"], ["mValue", "value"]]) {
        getJSON(`${API}/market/movers?by=${by}&limit=10`).then(r => table($(id), r.data, ["symbol", "ltp", "percent", "value"])).catch(e => fail(id, e));
      }
      getJSON(`${API}/market/pe`).then(r => {
        const d = r.data, rows = [{symbol: "", name: "Market", ...d.market}, ...Object.entries(d.by_category).map(([k, v]) => ({name: `Category ${k}`, ...v})),
          ...Object.entries(d.by_sector).map(([k, v]) => ({name: k, ...v}))];
        table($("mPe"), rows, ["name", "instruments", "median_pe", "weighted_pe"]);
        $("mPe").insertAdjacentHTML("beforeend", `<p class="mute">${esc(d.note)}</p>`);
      }).catch(e => fail("mPe", e));
      getJSON(`${API}/market/52-week?limit=15`).then(r => table($("m52"), r.data, ["symbol", "ltp", "low_52w", "high_52w", "range_position_pct"])).catch(e => fail("m52", e));
    };
    await load();
    universeHandler = load;
  }

  // ---------------------------------------------------------------- Scanner
  const scan = {presets: [], fields: {}, ops: [], key: null, live: null, filters: {categories: [], sectors: [], min_value_mn: null},
                custom: [{field: "rsi14", op: "between", value: "50,70"}], match: "all"};

  async function scannerView(key) {
    if (!scan.presets.length) {
      const [p, f] = await Promise.all([getJSON(`${API}/scanner/presets`), getJSON(`${API}/scanner/fields`)]);
      scan.presets = p.data; scan.fields = f.data; scan.ops = f.ops;
    }
    scan.key = key || scan.key || "short_term_setup";
    const groups = {};
    scan.presets.forEach(p => (groups[p.group] = groups[p.group] || []).push(p));
    view().innerHTML = `<div class="card"><h3>Preset scanners</h3>${Object.entries(groups).map(([g, ps]) =>
        `<div style="margin-bottom:8px"><div class="small mute">${esc(g)}</div><div class="chips">${ps.map(p =>
          `<button class="chip ${p.key === scan.key ? "on" : ""}" data-k="${p.key}" title="${esc(p.description)}">${esc(p.name)}${p.premarket ? " ☾" : ""}</button>`).join("")}</div></div>`).join("")}
        <p class="small mute">☾ = pre-market scan: evaluates the last completed session by default.</p></div>
      <div class="card"><h3>Custom scanner</h3><div id="rules"></div>
        <div class="rule"><button class="ghost" id="addRule">+ rule</button>
          <select id="match"><option value="all">match ALL</option><option value="any">match ANY</option></select>
          <button id="runCustom">Run custom scan</button></div></div>
      <div class="card"><h3>Filters</h3><div class="rule">
          <select id="fCat"><option value="">All categories</option><option>A</option><option>B</option><option>N</option><option>Z</option></select>
          <input class="inp" id="fMinVal" type="number" step="0.5" placeholder="Min turnover mn" style="width:150px">
          <select id="fLive"><option value="">Session: preset default</option><option value="true">Live (today)</option><option value="false">Last close (pre-market)</option></select>
        </div></div>
      <div class="card"><h3 id="scanTitle">Results</h3><p id="scanDesc" class="small mute"></p><div id="scanOut" class="small mute">Loading…</div></div>`;
    view().querySelectorAll(".chip[data-k]").forEach(b => b.onclick = () => { location.hash = `#/scanner/${b.dataset.k}`; });
    $("fCat").value = scan.filters.categories[0] || ""; $("fMinVal").value = scan.filters.min_value_mn ?? ""; $("fLive").value = scan.live ?? "";
    $("fCat").onchange = $("fMinVal").onchange = $("fLive").onchange = () => {
      scan.filters.categories = $("fCat").value ? [$("fCat").value] : []; scan.filters.min_value_mn = $("fMinVal").value ? +$("fMinVal").value : null;
      scan.live = $("fLive").value || null; runPreset();
    };
    $("match").value = scan.match; $("match").onchange = () => scan.match = $("match").value;
    $("addRule").onclick = () => { scan.custom.push({field: "close", op: ">", field2: "sma50"}); drawRules(); };
    $("runCustom").onclick = runCustom;
    drawRules();
    await runPreset();
    universeHandler = () => (scan.mode === "custom" ? runCustom() : runPreset());
  }

  function drawRules() {
    const fields = Object.keys(scan.fields).sort();
    const fopt = sel => fields.map(f => `<option value="${f}" ${f === sel ? "selected" : ""}>${f} — ${esc(scan.fields[f])}</option>`).join("");
    $("rules").innerHTML = scan.custom.map((r, i) => `<div class="rule" data-i="${i}">
        <select data-p="field">${fopt(r.field)}</select>
        <select data-p="op">${scan.ops.map(o => `<option ${o === r.op ? "selected" : ""}>${o}</option>`).join("")}</select>
        <select data-p="field2"><option value="">(value)</option>${fopt(r.field2)}</select>
        <input class="inp" data-p="value" value="${esc(r.value ?? "")}" placeholder="value, or a,b for between / in" style="width:170px">
        <button class="ghost" data-del="${i}">×</button></div>`).join("");
    $("rules").querySelectorAll("[data-p]").forEach(el => el.onchange = () => { scan.custom[+el.closest(".rule").dataset.i][el.dataset.p] = el.value || undefined; });
    $("rules").querySelectorAll("[data-del]").forEach(b => b.onclick = () => { scan.custom.splice(+b.dataset.del, 1); drawRules(); });
  }

  const COLS = ["symbol", "sector", "category", "ltp", "change_pct", "value_mn", "vol_ratio", "rsi14", "setup_score", "vpa", "patterns", "pe", "pct_from_52w_high"];
  const filterQS = () => {
    const q = new URLSearchParams({limit: 200});
    if (scan.filters.categories.length) q.set("categories", scan.filters.categories.join(","));
    if (scan.filters.min_value_mn) q.set("min_value_mn", scan.filters.min_value_mn);
    if (scan.live) q.set("live", scan.live);
    return q;
  };

  async function runPreset() {
    scan.mode = "preset";
    const p = scan.presets.find(x => x.key === scan.key);
    $("scanTitle").textContent = p ? p.name : scan.key; $("scanDesc").textContent = p ? p.description : "";
    try {
      const r = await getJSON(`${API}/scanner/presets/${scan.key}?${filterQS()}`);
      showResults(r);
    } catch (e) { fail("scanOut", e); }
  }

  async function runCustom() {
    scan.mode = "custom";
    const rules = scan.custom.map(r => {
      const out = {field: r.field, op: r.op};
      if (r.field2) out.field2 = r.field2;
      else if (r.value != null && r.value !== "") {
        const parts = String(r.value).split(",").map(s => s.trim()), conv = s => (isNaN(+s) ? s : +s);
        out.value = ["between", "in", "not_in"].includes(r.op) ? parts.map(conv) : conv(parts[0]);
      }
      return out;
    });
    $("scanTitle").textContent = "Custom scan"; $("scanDesc").textContent = JSON.stringify(rules);
    try {
      const r = await fetch(`${API}/scanner/run`, {method: "POST", headers: {"content-type": "application/json"},
        body: JSON.stringify({rules, match: scan.match, limit: 200, live: scan.live !== "false",
          universe: {assetTypes: ["EQ"], categories: scan.filters.categories.length ? scan.filters.categories : null, min_value_mn: scan.filters.min_value_mn}})});
      const body = await r.json(); if (!r.ok) throw new Error(body.detail || body.title);
      showResults(body);
    } catch (e) { fail("scanOut", e); }
  }

  function showResults(r) {
    const m = r.meta;
    table($("scanOut"), r.data, COLS);
    $("scanOut").insertAdjacentHTML("afterbegin", `<p class="mute">${m.matched} of ${m.scanned} instruments · ${m.live ? "live session" : "last completed session"} ·
      universe v${m.universeVersion} built ${m.universeBuiltAtMs ? new Date(m.universeBuiltAtMs).toLocaleTimeString() : "–"} · trade time ${esc(m.tradeTime || "–")} · refreshes on every tick</p>`);
  }

  // ---------------------------------------------------------------- Data (matrix + TA values)
  async function dataView(arg) {
    const sector = arg ? decodeURIComponent(arg) : "";
    view().innerHTML = `<div class="card"><div class="rule"><div class="chips"><button class="chip on" data-t="matrix">Data matrix (fundamentals)</button><button class="chip" data-t="ta">TA values</button></div>
      <span class="mute small">${sector ? `Sector: <b>${esc(sector)}</b> · <a href="#/data">all</a>` : "All sectors"}</span>
      <button class="ghost small" id="csv" style="margin-left:auto">Export CSV</button></div><div id="dOut" class="small mute">Loading…</div></div>`;
    let tab = "matrix", rows = [], cols = [];
    const load = async () => {
      const q = sector ? `?sector=${encodeURIComponent(sector)}` : "";
      try {
        const r = await getJSON(`${API}/market/${tab === "matrix" ? "data-matrix" : "ta-values"}${q}`);
        rows = r.data; cols = rows.length ? Object.keys(rows[0]).filter(c => c !== "name") : [];
        table($("dOut"), rows, cols);
      } catch (e) { fail("dOut", e); }
    };
    view().querySelectorAll("[data-t]").forEach(b => b.onclick = () => { tab = b.dataset.t; view().querySelectorAll("[data-t]").forEach(x => x.classList.toggle("on", x === b)); load(); });
    $("csv").onclick = () => {
      const csv = [cols.join(","), ...rows.map(r => cols.map(c => JSON.stringify(Array.isArray(r[c]) ? r[c].join(" ") : r[c] ?? "")).join(","))].join("\n");
      const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([csv], {type: "text/csv"})); a.download = `dse-${tab}.csv`; a.click();
    };
    await load();
    universeHandler = load;
  }

  // ---------------------------------------------------------------- Tools
  async function tools() {
    view().innerHTML = `<div class="grid2">
      <div class="card"><h3>Return calculator</h3><div class="rule">
        <input class="inp" id="rSym" placeholder="Symbol" value="${esc(state.symbol || "")}" style="width:120px">
        <input class="inp" id="rBuy" type="date" value="${new Date(Date.now() - 180 * 864e5).toISOString().slice(0, 10)}">
        <input class="inp" id="rSell" type="date"><input class="inp" id="rQty" type="number" value="100" style="width:90px">
        <button id="rGo">Calculate</button></div><div id="rOut" class="small"></div></div>
      <div class="card"><h3>Data download</h3><div class="rule"><input class="inp" id="dlSym" placeholder="Symbol" value="${esc(state.symbol || "")}" style="width:120px">
        <button id="dlGo">Download daily OHLCV (CSV)</button></div><p class="small mute">History available after <code>python main.py sync</code>.</p></div></div>
      <div class="card"><h3>Correlation of daily returns</h3><div class="rule">
        <input class="inp" id="cSyms" style="flex:1;min-width:260px" value="${esc([state.symbol, ...state.watch].filter(Boolean).slice(0, 8).join(","))}">
        <select id="cDays"><option>60</option><option selected>120</option><option>250</option></select><button id="cGo">Compute</button></div>
        <div id="cOut" style="height:440px"></div></div>`;
    $("rGo").onclick = async () => {
      const q = new URLSearchParams({symbol: $("rSym").value.toUpperCase(), buy_date: $("rBuy").value, quantity: $("rQty").value});
      if ($("rSell").value) q.set("sell_date", $("rSell").value);
      try {
        const d = (await getJSON(`${API}/tools/return?${q}`)).data;
        $("rOut").innerHTML = `<table>${[["Bought", `${d.buyDate} @ ${num(d.buyPrice)}`], ["Sold / now", `${d.sellDate} @ ${num(d.sellPrice)}`],
          ["Cost (incl. fees)", num(d.cost)], ["Proceeds (after fees)", num(d.proceeds)], ["Profit", `<b class="${cls(d.profit)}">${num(d.profit)}</b>`],
          ["Return", `<b class="${cls(d.returnPct)}">${pct(d.returnPct, 2)}</b> over ${d.days} days`], ["Annualised", pct(d.annualisedPct, 1)]]
          .map(([k, v]) => `<tr><th>${k}</th><td>${v}</td></tr>`).join("")}</table><p class="mute">${esc(d.note)}</p>`;
      } catch (e) { fail("rOut", e); }
    };
    $("dlGo").onclick = () => { location.href = `${API}/data/${encodeURIComponent($("dlSym").value.toUpperCase())}.csv`; };
    $("cGo").onclick = async () => {
      try {
        const d = (await getJSON(`${API}/tools/correlation?symbols=${encodeURIComponent($("cSyms").value.toUpperCase())}&days=${$("cDays").value}`)).data;
        Plotly.react("cOut", [{z: d.matrix, x: d.symbols, y: d.symbols, type: "heatmap", zmin: -1, zmax: 1, colorscale: "RdBu", reversescale: true,
          text: d.matrix.map(r => r.map(v => v == null ? "" : v.toFixed(2))), texttemplate: "%{text}", hovertemplate: "%{y} / %{x}: %{z:.2f}<extra></extra>"}],
          {margin: {l: 90, r: 10, t: 10, b: 90}, paper_bgcolor: "rgba(0,0,0,0)", font: {color: getComputedStyle(document.documentElement).getPropertyValue("--ink")}},
          {displaylogo: false, responsive: true});
      } catch (e) { fail("cOut", e); }
    };
  }

  // ---------------------------------------------------------------- stock extras: depth, VPA, intraday
  async function depth(symbol) {
    try {
      const d = (await getJSON(`${API}/stocks/${symbol}/depth`)).data, s = d.stats;
      const maxQ = Math.max(1, ...d.bids.map(b => b.quantity), ...d.asks.map(a => a.quantity));
      const rows = Array.from({length: Math.max(d.bids.length, d.asks.length)}, (_, i) => {
        const b = d.bids[i], a = d.asks[i];
        return `<tr><td class="q" style="text-align:right">${b ? `<i style="right:0;width:${b.quantity / maxQ * 100}%;background:var(--up)"></i>${num(b.quantity, 0)}` : ""}</td>
          <td class="up"><b>${b ? num(b.price) : ""}</b></td><td class="dn"><b>${a ? num(a.price) : ""}</b></td>
          <td class="q">${a ? `<i style="left:0;width:${a.quantity / maxQ * 100}%;background:var(--dn)"></i>${num(a.quantity, 0)}` : ""}</td></tr>`;
      }).join("");
      $("depth").innerHTML = `<table class="ladder"><tr><th style="text-align:right">Bid qty</th><th>Bid</th><th>Ask</th><th>Ask qty</th></tr>${rows || "<tr><td colspan=4>No orders</td></tr>"}</table>
        <p>Spread <b>${num(s.spread)}</b> (${num(s.spreadPct, 2)}%) · bid qty ${num(s.bidQty, 0)} vs ask ${num(s.askQty, 0)} ·
        imbalance <b class="${cls(s.imbalance)}">${s.imbalance == null ? "–" : (s.imbalance * 100).toFixed(0) + "%"}</b></p>`;
      $("depthTs").textContent = `· ${new Date().toLocaleTimeString()} · refreshes every 10 s`;
    } catch (e) { fail("depth", e); }
  }

  async function stockExtras(symbol) {
    if (depthTimer) clearInterval(depthTimer);
    depth(symbol);
    depthTimer = setInterval(() => { if (state.symbol === symbol && current === "stock" && !document.hidden) depth(symbol); }, 10000);
    getJSON(`${API}/stocks/${symbol}/vpa?days=20`).then(r => {
      const rows = r.data.filter(x => x.vpa).reverse();
      $("vpa").innerHTML = rows.length ? `<table>${rows.map(x => `<tr><td style="white-space:nowrap">${x.date}</td><td>${FMT.vpa(x.vpa)}</td>
        <td class="mute">vol ${num(x.vol_rel)}× · spread ${num(x.spread_rel)}× · close at ${Math.round(x.close_pos * 100)}% of range</td></tr>`).join("")}</table>
        <p class="mute">${Object.entries(r.legend).map(([k, v]) => `<b>${esc(k)}</b>: ${esc(v.meaning)}`).join(" · ")}</p>` : "No VPA signals in the last 20 sessions.";
    }).catch(e => fail("vpa", e));
    getJSON(`${API}/stocks/${symbol}/intraday`).then(r => {
      if (!r.data.length) { $("intraday").textContent = r.meta.note; return; }
      $("intraday").innerHTML = `<div id="intraChart" style="height:280px"></div>`;
      const d = r.data, css = getComputedStyle(document.documentElement);
      Plotly.react("intraChart", [{x: d.map(x => x.time), open: d.map(x => x.open), high: d.map(x => x.high), low: d.map(x => x.low), close: d.map(x => x.close), type: "candlestick", name: "1m"},
        {x: d.map(x => x.time), y: d.map(x => x.volume), type: "bar", yaxis: "y2", name: "Volume", opacity: .4, text: d.map(x => x.vpa || ""), hovertemplate: "%{y:,} %{text}<extra></extra>"}],
        {margin: {l: 48, r: 10, t: 10, b: 30}, paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)", font: {color: css.getPropertyValue("--ink")},
         xaxis: {type: "category", rangeslider: {visible: false}}, yaxis: {domain: [.3, 1]}, yaxis2: {domain: [0, .25]}, showlegend: false}, {displaylogo: false, responsive: true});
    }).catch(e => fail("intraday", e));
  }

  function start(fallback) {
    window.addEventListener("hashchange", () => route(fallback));
    route(fallback);
  }

  return {start, show, stockExtras};
})();
window.App = App;  // top-level const is not a window property; index.html guards on window.App
