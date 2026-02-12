/* Stock Earnings Calendar - Frontend */

(function () {
  "use strict";

  // DOM refs — calendar
  const calendarEl = document.getElementById("calendar");
  const calendarTitle = document.getElementById("calendarTitle");
  const calendarError = document.getElementById("calendarError");
  const calendarLoading = document.getElementById("calendarLoading");
  const sourceInfo = document.getElementById("sourceInfo");
  const dayDetail = document.getElementById("dayDetail");
  const dayDetailTitle = document.getElementById("dayDetailTitle");
  const dayDetailBody = document.getElementById("dayDetailBody");

  // DOM refs — ticker search
  const tickerInput = document.getElementById("tickerInput");
  const searchBtn = document.getElementById("searchBtn");
  const errorMsg = document.getElementById("errorMsg");
  const tickerLoading = document.getElementById("tickerLoading");
  const results = document.getElementById("results");
  const companyNameEl = document.getElementById("companyName");
  const tickerBadge = document.getElementById("tickerBadge");
  const upcomingSection = document.getElementById("upcomingSection");
  const upcomingDates = document.getElementById("upcomingDates");
  const earningsBody = document.getElementById("earningsBody");
  const quarterlySection = document.getElementById("quarterlySection");
  const yearlySection = document.getElementById("yearlySection");

  let calendarMonth = new Date().getMonth();
  let calendarYear = new Date().getFullYear();
  let calendarEvents = []; // [{date, symbol, epsEstimate, revenueEstimate, hour}]
  let quarterlyChartInstance = null;
  let yearlyChartInstance = null;

  // ── Calendar ──────────────────────────────────────────────────────

  document.getElementById("prevMonth").addEventListener("click", () => {
    calendarMonth--;
    if (calendarMonth < 0) { calendarMonth = 11; calendarYear--; }
    fetchCalendar();
  });
  document.getElementById("nextMonth").addEventListener("click", () => {
    calendarMonth++;
    if (calendarMonth > 11) { calendarMonth = 0; calendarYear++; }
    fetchCalendar();
  });

  async function fetchCalendar() {
    const fromDate = `${calendarYear}-${pad(calendarMonth + 1)}-01`;
    const lastDay = new Date(calendarYear, calendarMonth + 1, 0).getDate();
    const toDate = `${calendarYear}-${pad(calendarMonth + 1)}-${pad(lastDay)}`;

    renderCalendarTitle();
    calendarLoading.style.display = "flex";
    calendarError.style.display = "none";
    calendarEl.innerHTML = "";

    try {
      const resp = await fetch(`/api/calendar?from=${fromDate}&to=${toDate}`);
      const data = await resp.json();
      calendarLoading.style.display = "none";

      if (!resp.ok) {
        calendarError.textContent = data.error || "Failed to load calendar.";
        calendarError.style.display = "block";
        calendarEvents = [];
        renderCalendar();
        return;
      }

      calendarEvents = data.events || [];
      const src = data.source || "";
      if (src) {
        const label = src === "finnhub" ? "Finnhub" : src === "demo" ? "Demo data" : src;
        sourceInfo.textContent = `${calendarEvents.length} earnings event(s) this month via ${label}`;
        sourceInfo.style.display = "block";
      }
      renderCalendar();
    } catch (err) {
      calendarLoading.style.display = "none";
      calendarError.textContent = "Network error loading calendar.";
      calendarError.style.display = "block";
      calendarEvents = [];
      renderCalendar();
    }
  }

  function renderCalendarTitle() {
    const monthNames = [
      "January","February","March","April","May","June",
      "July","August","September","October","November","December",
    ];
    calendarTitle.textContent = `${monthNames[calendarMonth]} ${calendarYear}`;
  }

  function renderCalendar() {
    renderCalendarTitle();

    const firstDay = new Date(calendarYear, calendarMonth, 1).getDay();
    const daysInMonth = new Date(calendarYear, calendarMonth + 1, 0).getDate();
    const today = new Date();
    const todayStr = `${today.getFullYear()}-${pad(today.getMonth() + 1)}-${pad(today.getDate())}`;

    // Group events by day
    const eventMap = {};
    calendarEvents.forEach((ev) => {
      if (!ev.date) return;
      const [y, m, d] = ev.date.split("-").map(Number);
      if (y === calendarYear && m === calendarMonth + 1) {
        if (!eventMap[d]) eventMap[d] = [];
        eventMap[d].push(ev);
      }
    });

    let html = "";
    // Day headers
    ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].forEach((d) => {
      html += `<div class="cal-header">${d}</div>`;
    });

    // Leading blanks
    for (let i = 0; i < firstDay; i++) {
      html += `<div class="cal-day"></div>`;
    }

    // Days
    for (let d = 1; d <= daysInMonth; d++) {
      const dateStr = `${calendarYear}-${pad(calendarMonth + 1)}-${pad(d)}`;
      const isToday = dateStr === todayStr;
      const events = eventMap[d] || [];
      const count = events.length;

      let classes = "cal-day current-month";
      if (isToday) classes += " today";
      if (count > 0) classes += " has-event";

      let badge = "";
      let tooltip = "";
      if (count > 0) {
        badge = `<span class="event-count">${count}</span>`;
        const preview = events.slice(0, 5).map((e) => e.symbol).join(", ");
        const more = count > 5 ? `, +${count - 5} more` : "";
        tooltip = `<div class="cal-tooltip">${preview}${more}</div>`;
      }

      html += `<div class="${classes}" data-date="${dateStr}">${d}${badge}${tooltip}</div>`;
    }

    calendarEl.innerHTML = html;

    // Click handler for day cells
    calendarEl.querySelectorAll(".cal-day.has-event").forEach((cell) => {
      cell.addEventListener("click", () => {
        const date = cell.dataset.date;
        showDayDetail(date);
      });
    });
  }

  function showDayDetail(dateStr) {
    const events = calendarEvents.filter((e) => e.date === dateStr);
    if (!events.length) { dayDetail.style.display = "none"; return; }

    const dt = new Date(dateStr + "T00:00:00");
    dayDetailTitle.textContent = `Earnings on ${formatDateNice(dt)} (${events.length} companies)`;

    dayDetailBody.innerHTML = events
      .sort((a, b) => (a.symbol || "").localeCompare(b.symbol || ""))
      .map((e) => {
        const hour = e.hour === "bmo" ? "Before Open" : e.hour === "amc" ? "After Close" : e.hour || "TBD";
        const eps = e.epsEstimate != null ? `$${Number(e.epsEstimate).toFixed(2)}` : "-";
        const rev = e.revenueEstimate != null ? formatLargeNumber(e.revenueEstimate) : "-";
        return `<tr>
          <td><strong>${e.symbol}</strong></td>
          <td>${hour}</td>
          <td>${eps}</td>
          <td>${rev}</td>
        </tr>`;
      })
      .join("");

    dayDetail.style.display = "block";
    dayDetail.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  // ── Ticker Search ─────────────────────────────────────────────────

  searchBtn.addEventListener("click", doSearch);
  tickerInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") doSearch();
  });

  async function doSearch() {
    const ticker = tickerInput.value.trim().toUpperCase();
    if (!ticker) return showError("Please enter a stock ticker.");
    if (!/^[A-Z]{1,5}$/.test(ticker))
      return showError("Invalid ticker. Use 1-5 letters (e.g., AAPL).");

    hideError();
    results.style.display = "none";
    tickerLoading.style.display = "flex";

    try {
      const resp = await fetch(`/api/earnings?ticker=${encodeURIComponent(ticker)}`);
      const data = await resp.json();
      if (!resp.ok) {
        showError(data.error || "Failed to fetch data.");
        tickerLoading.style.display = "none";
        return;
      }
      tickerLoading.style.display = "none";
      renderTickerResults(data);
    } catch (err) {
      tickerLoading.style.display = "none";
      showError("Network error. Please try again.");
    }
  }

  function showError(msg) {
    errorMsg.textContent = msg;
    errorMsg.style.display = "block";
  }
  function hideError() {
    errorMsg.style.display = "none";
  }

  function renderTickerResults(data) {
    results.style.display = "block";
    companyNameEl.textContent = data.companyName || data.ticker;
    tickerBadge.textContent = data.ticker;

    // Upcoming dates
    if (data.upcomingEarningsDates && data.upcomingEarningsDates.length) {
      upcomingSection.style.display = "block";
      upcomingDates.textContent = data.upcomingEarningsDates
        .map((d) => formatDateNice(new Date(d + "T00:00:00")))
        .join(", ");
    } else {
      upcomingSection.style.display = "none";
    }

    // Earnings history table
    renderTable(data.earningsHistory || []);

    // Charts
    renderQuarterlyChart(data.quarterlyFinancials || []);
    renderYearlyChart(data.yearlyFinancials || []);
  }

  function renderTable(history) {
    if (!history.length) {
      earningsBody.innerHTML =
        '<tr><td colspan="5" style="text-align:center;color:var(--text-dim);">No historical data available</td></tr>';
      return;
    }
    earningsBody.innerHTML = history
      .map((h) => {
        const surpriseClass =
          h.surprisePct !== null && h.surprisePct !== undefined
            ? h.surprisePct >= 0 ? "surprise-positive" : "surprise-negative"
            : "";
        const surpriseText =
          h.surprisePct !== null && h.surprisePct !== undefined
            ? `${h.surprisePct >= 0 ? "+" : ""}${h.surprisePct.toFixed(1)}%`
            : "-";
        return `<tr>
          <td>${h.period || "-"}</td>
          <td>${h.reportDate ? formatDateNice(new Date(h.reportDate + "T00:00:00")) : "-"}</td>
          <td>${h.epsActual != null ? "$" + h.epsActual.toFixed(2) : "-"}</td>
          <td>${h.epsEstimate != null ? "$" + h.epsEstimate.toFixed(2) : "-"}</td>
          <td class="${surpriseClass}">${surpriseText}</td>
        </tr>`;
      })
      .join("");
  }

  // ── Charts ────────────────────────────────────────────────────────

  function renderQuarterlyChart(data) {
    const ctx = document.getElementById("quarterlyChart").getContext("2d");
    if (quarterlyChartInstance) quarterlyChartInstance.destroy();
    if (!data.length) { quarterlySection.style.display = "none"; return; }
    quarterlySection.style.display = "block";

    quarterlyChartInstance = new Chart(ctx, {
      type: "bar",
      data: {
        labels: data.map((d) => d.period),
        datasets: [
          { label: "Revenue", data: data.map((d) => d.revenue), backgroundColor: "rgba(108,92,231,0.6)", borderColor: "rgba(108,92,231,1)", borderWidth: 1, borderRadius: 4 },
          { label: "Earnings", data: data.map((d) => d.earnings), backgroundColor: "rgba(0,206,201,0.6)", borderColor: "rgba(0,206,201,1)", borderWidth: 1, borderRadius: 4 },
        ],
      },
      options: chartOptions(),
    });
  }

  function renderYearlyChart(data) {
    const ctx = document.getElementById("yearlyChart").getContext("2d");
    if (yearlyChartInstance) yearlyChartInstance.destroy();
    if (!data.length) { yearlySection.style.display = "none"; return; }
    yearlySection.style.display = "block";

    yearlyChartInstance = new Chart(ctx, {
      type: "bar",
      data: {
        labels: data.map((d) => d.period),
        datasets: [
          { label: "Revenue", data: data.map((d) => d.revenue), backgroundColor: "rgba(108,92,231,0.6)", borderColor: "rgba(108,92,231,1)", borderWidth: 1, borderRadius: 4 },
          { label: "Earnings", data: data.map((d) => d.earnings), backgroundColor: "rgba(0,206,201,0.6)", borderColor: "rgba(0,206,201,1)", borderWidth: 1, borderRadius: 4 },
        ],
      },
      options: chartOptions(),
    });
  }

  function chartOptions() {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: "#8b8fa8", font: { size: 12 } } },
        tooltip: { callbacks: { label: (ctx) => ctx.dataset.label + ": " + formatLargeNumber(ctx.parsed.y) } },
      },
      scales: {
        x: { ticks: { color: "#8b8fa8" }, grid: { color: "rgba(46,49,72,0.5)" } },
        y: { ticks: { color: "#8b8fa8", callback: (val) => formatLargeNumber(val) }, grid: { color: "rgba(46,49,72,0.5)" } },
      },
    };
  }

  // ── Helpers ────────────────────────────────────────────────────────

  function pad(n) { return String(n).padStart(2, "0"); }

  function formatDateNice(dt) {
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    return `${months[dt.getMonth()]} ${dt.getDate()}, ${dt.getFullYear()}`;
  }

  function formatLargeNumber(n) {
    if (n == null) return "N/A";
    const abs = Math.abs(n);
    const sign = n < 0 ? "-" : "";
    if (abs >= 1e12) return sign + "$" + (abs / 1e12).toFixed(1) + "T";
    if (abs >= 1e9) return sign + "$" + (abs / 1e9).toFixed(1) + "B";
    if (abs >= 1e6) return sign + "$" + (abs / 1e6).toFixed(1) + "M";
    if (abs >= 1e3) return sign + "$" + (abs / 1e3).toFixed(1) + "K";
    return sign + "$" + Number(n).toFixed(2);
  }

  // ── Init ───────────────────────────────────────────────────────────
  fetchCalendar();
})();
