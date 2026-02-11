/* Stock Earnings Calendar - Frontend */

(function () {
  "use strict";

  // DOM refs
  const tickerInput = document.getElementById("tickerInput");
  const searchBtn = document.getElementById("searchBtn");
  const errorMsg = document.getElementById("errorMsg");
  const loading = document.getElementById("loading");
  const results = document.getElementById("results");
  const companyNameEl = document.getElementById("companyName");
  const tickerBadge = document.getElementById("tickerBadge");
  const upcomingSection = document.getElementById("upcomingSection");
  const upcomingDates = document.getElementById("upcomingDates");
  const calendarEl = document.getElementById("calendar");
  const calendarTitle = document.getElementById("calendarTitle");
  const earningsBody = document.getElementById("earningsBody");
  const yearlySection = document.getElementById("yearlySection");

  let calendarMonth = new Date().getMonth();
  let calendarYear = new Date().getFullYear();
  let earningsEvents = []; // {date, type, detail}
  let quarterlyChartInstance = null;
  let yearlyChartInstance = null;

  // --- Search ---
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
    loading.style.display = "flex";

    try {
      const resp = await fetch(`/api/earnings?ticker=${encodeURIComponent(ticker)}`);
      const data = await resp.json();
      if (!resp.ok) {
        showError(data.error || "Failed to fetch data.");
        loading.style.display = "none";
        return;
      }
      loading.style.display = "none";
      renderResults(data);
    } catch (err) {
      loading.style.display = "none";
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

  // --- Render Results ---
  function renderResults(data) {
    results.style.display = "block";
    companyNameEl.textContent = data.companyName || data.ticker;
    tickerBadge.textContent = data.ticker;

    // Build earnings events for calendar
    earningsEvents = [];

    // Upcoming dates
    if (data.upcomingEarningsDates && data.upcomingEarningsDates.length) {
      upcomingSection.style.display = "block";
      upcomingDates.innerHTML = data.upcomingEarningsDates
        .map((d) => {
          const dt = new Date(d + "T00:00:00");
          earningsEvents.push({
            date: d,
            type: "upcoming",
            detail: "Upcoming Earnings Report",
          });
          return `<div class="upcoming-date-card">
            <div class="date-value">${formatDateNice(dt)}</div>
            <div class="date-label">${dayOfWeek(dt)}</div>
          </div>`;
        })
        .join("");

      // Jump calendar to first upcoming date
      const first = new Date(data.upcomingEarningsDates[0] + "T00:00:00");
      calendarMonth = first.getMonth();
      calendarYear = first.getFullYear();
    } else {
      upcomingSection.style.display = "none";
    }

    // Historical earnings
    if (data.earningsHistory) {
      data.earningsHistory.forEach((h) => {
        if (h.reportDate) {
          let type = "neutral";
          if (h.surprisePct !== null && h.surprisePct !== undefined) {
            type = h.surprisePct >= 0 ? "beat" : "miss";
          }
          const detail = buildHistoryDetail(h);
          earningsEvents.push({ date: h.reportDate, type, detail });
        }
      });
    }

    // If no upcoming date, jump to most recent historical
    if (
      (!data.upcomingEarningsDates || !data.upcomingEarningsDates.length) &&
      earningsEvents.length
    ) {
      const sorted = earningsEvents
        .map((e) => e.date)
        .sort()
        .reverse();
      if (sorted.length) {
        const latest = new Date(sorted[0] + "T00:00:00");
        calendarMonth = latest.getMonth();
        calendarYear = latest.getFullYear();
      }
    }

    renderCalendar();
    renderTable(data.earningsHistory || []);
    renderQuarterlyChart(data.quarterlyFinancials || []);
    renderYearlyChart(data.yearlyFinancials || []);
  }

  function buildHistoryDetail(h) {
    let lines = [];
    if (h.period) lines.push(`Period: ${h.period}`);
    if (h.epsActual !== null && h.epsActual !== undefined)
      lines.push(`EPS Actual: $${h.epsActual.toFixed(2)}`);
    if (h.epsEstimate !== null && h.epsEstimate !== undefined)
      lines.push(`EPS Est: $${h.epsEstimate.toFixed(2)}`);
    if (h.surprisePct !== null && h.surprisePct !== undefined) {
      const sign = h.surprisePct >= 0 ? "+" : "";
      lines.push(`Surprise: ${sign}${h.surprisePct.toFixed(1)}%`);
    }
    return lines.join("<br>");
  }

  // --- Calendar ---
  document.getElementById("prevMonth").addEventListener("click", () => {
    calendarMonth--;
    if (calendarMonth < 0) {
      calendarMonth = 11;
      calendarYear--;
    }
    renderCalendar();
  });
  document.getElementById("nextMonth").addEventListener("click", () => {
    calendarMonth++;
    if (calendarMonth > 11) {
      calendarMonth = 0;
      calendarYear++;
    }
    renderCalendar();
  });

  function renderCalendar() {
    const monthNames = [
      "January","February","March","April","May","June",
      "July","August","September","October","November","December",
    ];
    calendarTitle.textContent = `${monthNames[calendarMonth]} ${calendarYear}`;

    const firstDay = new Date(calendarYear, calendarMonth, 1).getDay();
    const daysInMonth = new Date(calendarYear, calendarMonth + 1, 0).getDate();
    const today = new Date();
    const todayStr =
      today.getFullYear() +
      "-" +
      String(today.getMonth() + 1).padStart(2, "0") +
      "-" +
      String(today.getDate()).padStart(2, "0");

    // Build event map for this month
    const eventMap = {};
    earningsEvents.forEach((ev) => {
      const [y, m] = ev.date.split("-").map(Number);
      if (y === calendarYear && m === calendarMonth + 1) {
        const day = parseInt(ev.date.split("-")[2], 10);
        if (!eventMap[day]) eventMap[day] = [];
        eventMap[day].push(ev);
      }
    });

    let html = "";
    // Day headers
    ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].forEach((d) => {
      html += `<div class="cal-header">${d}</div>`;
    });

    // Leading blanks
    for (let i = 0; i < firstDay; i++) {
      html += `<div class="cal-day"></div>`;
    }

    // Days
    for (let d = 1; d <= daysInMonth; d++) {
      const dateStr =
        calendarYear +
        "-" +
        String(calendarMonth + 1).padStart(2, "0") +
        "-" +
        String(d).padStart(2, "0");
      const isToday = dateStr === todayStr;
      const events = eventMap[d] || [];
      const hasEvent = events.length > 0;

      let classes = "cal-day current-month";
      if (isToday) classes += " today";
      if (hasEvent) classes += " has-event";

      let dotHtml = "";
      let tooltipHtml = "";
      if (hasEvent) {
        const ev = events[0];
        dotHtml = `<span class="event-dot ${ev.type}"></span>`;
        tooltipHtml = `<div class="cal-tooltip">${events.map((e) => e.detail).join("<hr style='border-color:var(--border);margin:4px 0'>")}</div>`;
      }

      html += `<div class="${classes}">${d}${dotHtml}${tooltipHtml}</div>`;
    }

    calendarEl.innerHTML = html;
  }

  // --- Table ---
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
            ? h.surprisePct >= 0
              ? "surprise-positive"
              : "surprise-negative"
            : "";
        const surpriseText =
          h.surprisePct !== null && h.surprisePct !== undefined
            ? `${h.surprisePct >= 0 ? "+" : ""}${h.surprisePct.toFixed(1)}%`
            : "-";
        return `<tr>
          <td>${h.period || "-"}</td>
          <td>${h.reportDate ? formatDateNice(new Date(h.reportDate + "T00:00:00")) : "-"}</td>
          <td>${h.epsActual !== null && h.epsActual !== undefined ? "$" + h.epsActual.toFixed(2) : "-"}</td>
          <td>${h.epsEstimate !== null && h.epsEstimate !== undefined ? "$" + h.epsEstimate.toFixed(2) : "-"}</td>
          <td class="${surpriseClass}">${surpriseText}</td>
        </tr>`;
      })
      .join("");
  }

  // --- Charts ---
  function renderQuarterlyChart(data) {
    const ctx = document.getElementById("quarterlyChart").getContext("2d");
    if (quarterlyChartInstance) quarterlyChartInstance.destroy();
    if (!data.length) return;

    quarterlyChartInstance = new Chart(ctx, {
      type: "bar",
      data: {
        labels: data.map((d) => d.period),
        datasets: [
          {
            label: "Revenue",
            data: data.map((d) => d.revenue),
            backgroundColor: "rgba(108, 92, 231, 0.6)",
            borderColor: "rgba(108, 92, 231, 1)",
            borderWidth: 1,
            borderRadius: 4,
          },
          {
            label: "Earnings",
            data: data.map((d) => d.earnings),
            backgroundColor: "rgba(0, 206, 201, 0.6)",
            borderColor: "rgba(0, 206, 201, 1)",
            borderWidth: 1,
            borderRadius: 4,
          },
        ],
      },
      options: chartOptions("Quarterly Revenue & Earnings"),
    });
  }

  function renderYearlyChart(data) {
    const ctx = document.getElementById("yearlyChart").getContext("2d");
    if (yearlyChartInstance) yearlyChartInstance.destroy();
    if (!data.length) {
      yearlySection.style.display = "none";
      return;
    }
    yearlySection.style.display = "block";

    yearlyChartInstance = new Chart(ctx, {
      type: "bar",
      data: {
        labels: data.map((d) => d.period),
        datasets: [
          {
            label: "Revenue",
            data: data.map((d) => d.revenue),
            backgroundColor: "rgba(108, 92, 231, 0.6)",
            borderColor: "rgba(108, 92, 231, 1)",
            borderWidth: 1,
            borderRadius: 4,
          },
          {
            label: "Earnings",
            data: data.map((d) => d.earnings),
            backgroundColor: "rgba(0, 206, 201, 0.6)",
            borderColor: "rgba(0, 206, 201, 1)",
            borderWidth: 1,
            borderRadius: 4,
          },
        ],
      },
      options: chartOptions("Annual Revenue & Earnings"),
    });
  }

  function chartOptions(title) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          labels: { color: "#8b8fa8", font: { size: 12 } },
        },
        tooltip: {
          callbacks: {
            label: function (ctx) {
              const val = ctx.parsed.y;
              if (val === null || val === undefined) return ctx.dataset.label + ": N/A";
              return ctx.dataset.label + ": " + formatLargeNumber(val);
            },
          },
        },
      },
      scales: {
        x: {
          ticks: { color: "#8b8fa8" },
          grid: { color: "rgba(46, 49, 72, 0.5)" },
        },
        y: {
          ticks: {
            color: "#8b8fa8",
            callback: function (val) {
              return formatLargeNumber(val);
            },
          },
          grid: { color: "rgba(46, 49, 72, 0.5)" },
        },
      },
    };
  }

  // --- Helpers ---
  function formatDateNice(dt) {
    const months = [
      "Jan","Feb","Mar","Apr","May","Jun",
      "Jul","Aug","Sep","Oct","Nov","Dec",
    ];
    return `${months[dt.getMonth()]} ${dt.getDate()}, ${dt.getFullYear()}`;
  }

  function dayOfWeek(dt) {
    return ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"][dt.getDay()];
  }

  function formatLargeNumber(n) {
    if (n === null || n === undefined) return "N/A";
    const abs = Math.abs(n);
    const sign = n < 0 ? "-" : "";
    if (abs >= 1e12) return sign + "$" + (abs / 1e12).toFixed(1) + "T";
    if (abs >= 1e9) return sign + "$" + (abs / 1e9).toFixed(1) + "B";
    if (abs >= 1e6) return sign + "$" + (abs / 1e6).toFixed(1) + "M";
    if (abs >= 1e3) return sign + "$" + (abs / 1e3).toFixed(1) + "K";
    return sign + "$" + n.toFixed(2);
  }
})();
