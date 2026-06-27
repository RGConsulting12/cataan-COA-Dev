/**
 * Session viewer UI — fetch sessions and COAs from REST API.
 */
(function () {
  const fixtureSelect = document.getElementById("fixture-select");
  const sessionSelect = document.getElementById("session-select");
  const createBtn = document.getElementById("create-session-btn");
  const reloadBtn = document.getElementById("reload-session-btn");
  const statusEl = document.getElementById("status-message");
  const headerSection = document.getElementById("session-header");
  const boardSvg = document.getElementById("board-svg");
  const timelineEl = document.getElementById("player-timeline");
  const coaCardsEl = document.getElementById("coa-cards");

  const knownSessions = new Set();

  function setStatus(msg, isError) {
    statusEl.textContent = msg || "";
    statusEl.className = isError ? "status-message error-banner" : "status-message";
  }

  function addSessionOption(id, label) {
    if (knownSessions.has(id)) return;
    knownSessions.add(id);
    const opt = document.createElement("option");
    opt.value = id;
    opt.textContent = label ? `${label} (${id.slice(0, 8)}…)` : id;
    sessionSelect.appendChild(opt);
  }

  function selectSession(id) {
    sessionSelect.value = id;
  }

  async function fetchJson(url, options) {
    const res = await fetch(url, options);
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      const detail = body.detail;
      const msg =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail)
            ? detail.map((e) => e.msg || JSON.stringify(e)).join("; ")
            : detail?.message || res.statusText;
      throw new Error(msg || `HTTP ${res.status}`);
    }
    return res.json();
  }

  function renderHeader(session) {
    headerSection.hidden = false;
    document.getElementById("hdr-session-id").textContent = session.id;
    document.getElementById("hdr-turn").textContent = String(session.turn_number);
    document.getElementById("hdr-phase").textContent = session.state.phase;
    document.getElementById("hdr-active-player").textContent = session.state.active_player;
    document.getElementById("hdr-label").textContent = session.label || "—";
  }

  function renderTimeline(session) {
    timelineEl.innerHTML = "";
    const players = session.state.players || [];
    const active = session.state.active_player;
    players.forEach((player) => {
      const li = document.createElement("li");
      li.className = "timeline-player" + (player.id === active ? " active" : "");
      const colorDot = document.createElement("span");
      colorDot.className = "player-color";
      colorDot.style.background = player.color || player.id;
      li.appendChild(colorDot);
      li.appendChild(document.createTextNode(`${player.id} (${player.victory_points} VP)`));
      timelineEl.appendChild(li);
    });
  }

  function renderCoas(recommendResponse) {
    coaCardsEl.innerHTML = "";
    (recommendResponse.recommendations || []).forEach((coa) => {
      const card = document.createElement("article");
      card.className = "coa-card";
      card.innerHTML = `
        <p class="action-type">#${coa.rank} · ${coa.action_type}</p>
        <h3>${escapeHtml(coa.summary)}</h3>
        <p><strong>Rationale:</strong> ${escapeHtml(coa.rationale)}</p>
      `;
      coaCardsEl.appendChild(card);
    });
  }

  function escapeHtml(text) {
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
  }

  async function loadSession(id) {
    if (!id) {
      setStatus("Select or create a session.");
      return;
    }
    setStatus("Loading session…");
    try {
      const session = await fetchJson(`/sessions/${id}`);
      renderHeader(session);
      window.BoardRenderer.renderBoard(boardSvg, session.state);
      renderTimeline(session);
      setStatus("Loading recommendations…");
      const recs = await fetchJson(`/sessions/${id}/recommend`, { method: "POST" });
      renderCoas(recs);
      setStatus(`Session ${id.slice(0, 8)}… loaded.`);
      const url = new URL(window.location.href);
      url.searchParams.set("session_id", id);
      window.history.replaceState({}, "", url);
    } catch (err) {
      setStatus(err.message || String(err), true);
      if (String(err.message).includes("404") || String(err.message).includes("not found")) {
        coaCardsEl.innerHTML = '<p class="error-banner">Session not found.</p>';
      }
    }
  }

  createBtn.addEventListener("click", async () => {
    const fixture = fixtureSelect.value;
    if (!fixture) {
      setStatus("Choose an example fixture first.", true);
      return;
    }
    setStatus("Creating session…");
    try {
      const session = await fetchJson("/sessions", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ fixture }),
      });
      addSessionOption(session.id, session.label);
      selectSession(session.id);
      await loadSession(session.id);
    } catch (err) {
      setStatus(err.message || String(err), true);
    }
  });

  sessionSelect.addEventListener("change", () => {
    loadSession(sessionSelect.value);
  });

  reloadBtn.addEventListener("click", () => {
    loadSession(sessionSelect.value);
  });

  async function loadFixtures() {
    try {
      const data = await fetchJson("/examples");
      (data.fixtures || []).forEach((name) => {
        const opt = document.createElement("option");
        opt.value = name;
        opt.textContent = name;
        fixtureSelect.appendChild(opt);
      });
    } catch (err) {
      setStatus("Could not load example fixtures.", true);
    }
  }

  const initial = new URLSearchParams(window.location.search).get("session_id");
  loadFixtures().then(() => {
    if (initial) {
      addSessionOption(initial);
      selectSession(initial);
      loadSession(initial);
    }
  });
})();
