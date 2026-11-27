(() => {
  "use strict";

  const dialog = document.getElementById("quick-search");
  if (typeof dialog?.showModal !== "function") return;

  const trigger = document.getElementById("quick-search-trigger");
  const query = document.getElementById("quick-search-query");
  const status = document.getElementById("quick-search-status");
  const films = document.getElementById("quick-search-films");
  let returnFocus;
  let timer;
  let pending;

  function resetSuggestions() {
    clearTimeout(timer);
    pending?.abort();
    pending = undefined;
    films.replaceChildren();
    films.hidden = true;
    status.textContent = "";
  }

  function openSearch() {
    if (dialog.open) return;
    const active = document.activeElement;
    returnFocus = active instanceof HTMLElement && active !== document.body ? active : trigger;
    dialog.showModal();
    query.select();
    scheduleSearch();
  }

  function filmLink(film) {
    const item = document.createElement("li");
    const link = document.createElement("a");
    const title = document.createElement("strong");
    const credit = document.createElement("span");
    link.href = film.url;
    title.textContent = film.title;
    credit.textContent = film.director + " · " + film.year;
    link.append(title, credit);
    item.append(link);
    return item;
  }

  function resultMessage(total, shown) {
    if (total === 0) return "Aucun film trouvé.";
    if (total === 1) return "1 film trouvé.";
    if (total > shown) return shown + " suggestions sur " + total + " films.";
    return total + " films trouvés.";
  }

  async function requestSuggestions(term) {
    if (!dialog.open) return;
    const controller = new AbortController();
    pending = controller;
    status.textContent = "Recherche en cours…";
    const url = new URL(dialog.dataset.suggestions, window.location.origin);
    url.searchParams.set("q", term);
    try {
      const response = await fetch(url, { signal: controller.signal });
      if (!response.ok) throw new Error("Recherche indisponible");
      const result = await response.json();
      if (pending !== controller || !dialog.open) return;
      films.replaceChildren(...result.films.map(filmLink));
      films.hidden = !result.films.length;
      status.textContent = resultMessage(result.total, result.films.length);
    } catch {
      if (pending === controller && dialog.open) {
        status.textContent = "Suggestions indisponibles. Vous pouvez lancer la recherche dans le catalogue.";
      }
    } finally {
      if (pending === controller) pending = undefined;
    }
  }

  function scheduleSearch() {
    resetSuggestions();
    const term = query.value.trim();
    if ([...term].length >= 2) {
      timer = setTimeout(() => requestSuggestions(term), 250);
    }
  }

  query.addEventListener("input", (event) => {
    if (event.isComposing) resetSuggestions();
    else scheduleSearch();
  });
  query.addEventListener("compositionend", scheduleSearch);
  function plainArrow(event) {
    return !event.isComposing && !event.ctrlKey && !event.metaKey && !event.altKey && !event.shiftKey;
  }

  query.addEventListener("keydown", (event) => {
    const first = films.querySelector("a");
    if (event.key !== "ArrowDown" || !plainArrow(event) || !first) return;
    event.preventDefault();
    first.focus();
  });
  films.addEventListener("keydown", (event) => {
    if (!plainArrow(event)) return;
    const item = event.target.closest("li");
    if (event.key === "ArrowDown") {
      event.preventDefault();
      item?.nextElementSibling?.querySelector("a")?.focus();
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      (item?.previousElementSibling?.querySelector("a") || query).focus();
    }
  });
  trigger.addEventListener("click", openSearch);
  dialog.querySelector("[data-close]").addEventListener("click", () => dialog.close());
  dialog.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !event.isComposing) {
      event.preventDefault();
      dialog.close();
    }
  });
  dialog.addEventListener("close", () => {
    if (dialog.open) return;
    resetSuggestions();
    (returnFocus?.isConnected ? returnFocus : trigger).focus();
  });
  document.addEventListener("keydown", (event) => {
    if (event.defaultPrevented || event.isComposing || event.altKey || event.shiftKey ||
        event.ctrlKey === event.metaKey || event.key.toLowerCase() !== "k") return;
    event.preventDefault();
    if (!event.repeat) openSearch();
  });

  if (navigator.platform.startsWith("Mac")) trigger.querySelector("kbd").textContent = "⌘ K";
  trigger.hidden = false;
  document.getElementById("quick-search-fallback").hidden = true;
})();
