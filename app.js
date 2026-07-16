/* تمرین جای خالی — منطق سایت (بدون سرور) */
(function () {
  "use strict";

  var DATA = window.KETAB_DATA;
  var content = document.getElementById("content");
  var pageSelect = document.getElementById("pageSelect");
  var score = document.getElementById("score");
  var progress = document.getElementById("progress");

  if (!DATA || !DATA.pages || !DATA.pages.length) {
    content.innerHTML =
      '<div class="card">داده‌ای یافت نشد. ابتدا <code>build.py</code> را اجرا کنید تا <code>data.js</code> ساخته شود.</div>';
    return;
  }

  var pages = DATA.pages;
  var current = parseInt(localStorage.getItem("zist3_page") || "0", 10);
  if (isNaN(current) || current < 0 || current >= pages.length) current = 0;

  /* ---------- نرمال‌سازی برای مقایسه‌ی پاسخ ---------- */
  function norm(s) {
    if (!s) return "";
    return s
      .replace(/‌/g, "")          // نیم‌فاصله
      .replace(/[يﻱﻲ]/g, "ی")
      .replace(/[كﻙ]/g, "ک")
      .replace(/[ًٌٍَُِّْٰ]/g, "")       // اعراب
      .replace(/[.،؛:!؟«»"'()\[\]\-–—…]/g, "")
      .replace(/\s+/g, "")
      .trim()
      .toLowerCase();
  }

  /* ---------- ساخت یک کارت جمله ---------- */
  function renderSentence(sent, i) {
    var card = document.createElement("div");
    card.className = "card";

    var num = document.createElement("span");
    num.className = "num";
    num.textContent = i + 1;
    card.appendChild(num);

    var box = document.createElement("span");
    box.className = "sentence";

    var blankSet = {};
    sent.b.forEach(function (idx) { blankSet[idx] = true; });

    sent.t.forEach(function (tok, idx) {
      if (blankSet[idx]) {
        var inp = document.createElement("input");
        inp.className = "blank";
        inp.type = "text";
        inp.dataset.answer = tok;
        inp.setAttribute("autocomplete", "off");
        inp.setAttribute("spellcheck", "false");
        inp.style.width = Math.max(70, tok.length * 14) + "px";
        inp.addEventListener("keydown", onEnterNext);
        box.appendChild(inp);
      } else {
        box.appendChild(document.createTextNode(tok));
      }
      box.appendChild(document.createTextNode(" "));
    });

    card.appendChild(box);
    return card;
  }

  function onEnterNext(e) {
    if (e.key !== "Enter") return;
    e.preventDefault();
    var all = Array.prototype.slice.call(document.querySelectorAll(".blank"));
    var i = all.indexOf(e.target);
    if (i > -1 && i + 1 < all.length) all[i + 1].focus();
    else checkPage();
  }

  /* ---------- رندر صفحه ---------- */
  function renderPage() {
    content.innerHTML = "";
    var p = pages[current];
    var head = document.createElement("div");
    head.className = "card";
    head.style.background = "transparent";
    head.style.border = "none";
    head.style.boxShadow = "none";
    head.style.padding = "0 4px";
    head.innerHTML =
      "<b>صفحه " + p.page + "</b> — " + p.sentences.length + " جمله" +
      " &nbsp;|&nbsp; " + (current + 1) + " از " + pages.length + " صفحه";
    content.appendChild(head);

    p.sentences.forEach(function (s, i) {
      content.appendChild(renderSentence(s, i));
    });

    pageSelect.value = String(current);
    score.textContent = "";
    var pct = ((current + 1) / pages.length) * 100;
    progress.style.width = pct.toFixed(1) + "%";
    localStorage.setItem("zist3_page", String(current));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  /* ---------- بررسی ---------- */
  function checkPage() {
    var blanks = document.querySelectorAll(".blank");
    var ok = 0, total = blanks.length;
    blanks.forEach(function (inp) {
      inp.classList.remove("correct", "wrong");
      var val = norm(inp.value);
      if (!val) return;
      if (val === norm(inp.dataset.answer)) {
        inp.classList.add("correct"); ok++;
      } else {
        inp.classList.add("wrong");
      }
    });
    var pctOk = total ? Math.round((ok / total) * 100) : 0;
    score.innerHTML = "امتیاز: <b>" + ok + "</b> از " + total + " (" + pctOk + "٪)";
  }

  function reveal() {
    var blanks = document.querySelectorAll(".blank");
    blanks.forEach(function (inp) {
      inp.value = inp.dataset.answer.replace(/‌/g, "‌");
      inp.classList.remove("wrong");
      inp.classList.add("correct");
    });
    score.innerHTML = "پاسخ‌ها نمایش داده شد.";
  }

  function clearPage() {
    document.querySelectorAll(".blank").forEach(function (inp) {
      inp.value = "";
      inp.classList.remove("correct", "wrong");
    });
    score.textContent = "";
  }

  /* ---------- ناوبری ---------- */
  function go(delta) {
    current = Math.min(pages.length - 1, Math.max(0, current + delta));
    renderPage();
  }

  pages.forEach(function (p, i) {
    var o = document.createElement("option");
    o.value = String(i);
    o.textContent = "صفحه " + p.page;
    pageSelect.appendChild(o);
  });

  document.getElementById("prevBtn").onclick = function () { go(-1); };
  document.getElementById("nextBtn").onclick = function () { go(1); };
  pageSelect.onchange = function () { current = parseInt(this.value, 10); renderPage(); };
  document.getElementById("checkBtn").onclick = checkPage;
  document.getElementById("revealBtn").onclick = reveal;
  document.getElementById("clearBtn").onclick = clearPage;

  document.getElementById("search").addEventListener("change", function () {
    var n = parseInt(this.value.replace(/[^\d]/g, ""), 10);
    if (isNaN(n)) return;
    for (var i = 0; i < pages.length; i++) {
      if (pages[i].page === n) { current = i; renderPage(); return; }
    }
    alert("صفحه‌ی " + n + " محتوای تمرینی ندارد.");
  });

  /* ---------- تم شب/روز ---------- */
  var themeBtn = document.getElementById("themeBtn");
  function applyTheme(t) {
    document.documentElement.setAttribute("data-theme", t);
    themeBtn.textContent = t === "dark" ? "☀️" : "🌙";
    localStorage.setItem("zist3_theme", t);
  }
  applyTheme(localStorage.getItem("zist3_theme") || "light");
  themeBtn.onclick = function () {
    applyTheme(document.documentElement.getAttribute("data-theme") === "dark" ? "light" : "dark");
  };

  /* ---------- میان‌بر صفحه‌کلید ---------- */
  document.addEventListener("keydown", function (e) {
    if (e.target.classList && e.target.classList.contains("blank")) return;
    if (e.key === "ArrowLeft") go(1);       // چپ = بعدی (RTL)
    if (e.key === "ArrowRight") go(-1);
  });

  renderPage();
})();
