const state = {
  dataRoot: "data",
  meta: null,
  catalog: null,
  atomIndex: new Map(),
  bookIndex: new Map(),
  atomsByBook: new Map(),
  atomCache: new Map(),
  currentBook: null,
  currentAtom: null,
};

const els = {};

function $(id) {
  return document.getElementById(id);
}

function dataUrl(path) {
  const root = state.dataRoot.endsWith("/") ? state.dataRoot : `${state.dataRoot}/`;
  return new URL(`${root}${path}`, document.baseURI).toString();
}

function fmtNumber(value) {
  return new Intl.NumberFormat("en-US").format(value);
}

function sectionLabel(section) {
  if (Array.isArray(section)) {
    return section.map((part) => String(part)).join(" / ");
  }
  if (section && typeof section === "object") {
    if (section.label) return section.label;
    return [section.book, section.chapter, section.verse].filter((value) => value !== null && value !== undefined).join(" ");
  }
  return String(section ?? "-");
}

function scoreLabel(score) {
  if (typeof score !== "number") return "-";
  return score.toFixed(4);
}

function candidateLabel(candidate) {
  const parts = [];
  if (candidate.predicted_rela) parts.push(candidate.predicted_rela);
  if (candidate.predicted_sub2 && candidate.predicted_sub2 !== ".") parts.push(candidate.predicted_sub2);
  if (candidate.parallel) parts.push("parallel");
  if (candidate.quotation) parts.push("quotation");
  return parts.length ? parts : ["no relation"];
}

async function fetchJson(path) {
  const response = await fetch(dataUrl(path), { cache: "no-cache" });
  if (!response.ok) {
    throw new Error(`Failed to load ${path}: ${response.status}`);
  }
  return response.json();
}

function setStatus(message) {
  els.statusLine.textContent = message;
}

function setMetaStatus(message) {
  els.metaStatus.textContent = message;
}

function buildIndexes() {
  state.atomIndex.clear();
  state.bookIndex.clear();
  state.atomsByBook.clear();

  for (const row of state.catalog.atoms) {
    const atomId = row.atom ?? row.daughter;
    state.atomIndex.set(String(atomId), row);

    if (!state.atomsByBook.has(row.book_slug)) {
      state.atomsByBook.set(row.book_slug, []);
    }
    state.atomsByBook.get(row.book_slug).push(row);
  }
  for (const book of state.catalog.books) {
    state.bookIndex.set(book.book_slug, book);
  }
}

function populateBooks() {
  els.bookSelect.innerHTML = "";
  for (const book of state.catalog.books) {
    const option = document.createElement("option");
    option.value = book.book_slug;
    option.textContent = `${book.book} (${fmtNumber(book.atom_count)})`;
    els.bookSelect.appendChild(option);
  }
}

function atomsForBook(bookSlug) {
  return state.atomsByBook.get(bookSlug) ?? [];
}

async function loadAtom(atomId) {
  const atomKey = String(atomId);
  if (!state.atomCache.has(atomKey)) {
    const detail = await fetchJson(`atoms/${atomKey}.json`);
    state.atomCache.set(atomKey, detail);
  }
  return state.atomCache.get(atomKey);
}

function renderBookList(bookSlug, activeId = null) {
  const atoms = atomsForBook(bookSlug);
  const book = state.bookIndex.get(bookSlug);
  els.atomList.innerHTML = "";

  if (!atoms.length) {
    els.atomList.innerHTML = '<p class="status">이 책에 표시할 atom이 없습니다.</p>';
    els.bookSummary.textContent = "-";
    return;
  }

  els.bookSummary.textContent = `${book?.book ?? "-"} / ${fmtNumber(book?.atom_count ?? atoms.length)} atoms`;

  for (const atom of atoms) {
    const button = document.createElement("button");
    button.type = "button";
    const atomId = atom.atom ?? atom.daughter;
    button.className = `atom-item${String(atomId) === String(activeId) ? " active" : ""}`;
    button.addEventListener("click", () => openAtom(atomId));

    const top = document.createElement("div");
    top.className = "atom-title";
    top.innerHTML = `<strong>${atomId}</strong><span>${sectionLabel(atom.section)}</span>`;

    const snippet = document.createElement("div");
    snippet.className = "atom-snippet";
    const prediction = atom.top_prediction;
    const predText = prediction ? `${prediction.mother} · ${scoreLabel(prediction.score)} · ${prediction.predicted_rela ?? "-"}` : "no prediction";
    snippet.textContent = `${atom.text} • ${predText}`;

    button.append(top, snippet);
    els.atomList.appendChild(button);
  }
}

function renderPhrases(phrases) {
  els.phraseList.innerHTML = "";
  if (!phrases?.length) {
    els.phraseList.innerHTML = '<p class="status">표시할 phrase 정보가 없습니다.</p>';
    return;
  }

  for (const phrase of phrases) {
    const chip = document.createElement("div");
    chip.className = "phrase-chip";
    chip.innerHTML = `<strong>${phrase.function ?? "-"} / ${phrase.typ ?? "-"}</strong><span>${phrase.text ?? "-"}</span><span>${(phrase.lexemes ?? []).join(", ") || "-"}</span>`;
    els.phraseList.appendChild(chip);
  }
}

function renderDetail(atom) {
  state.currentAtom = atom;
  state.currentBook = atom.book_slug ?? state.currentBook;

  els.detailTitle.textContent = `${atom.atom}`;
  els.detailText.textContent = atom.text || "-";
  els.detailMeta.textContent = `${sectionLabel(atom.section)} · ${atom.book ?? "-"} · relation ${atom.gold_relation ?? "-"} · pool ${fmtNumber(atom.pool_size ?? 0)}`;

  if (atom.gold_mother === null || atom.gold_mother === undefined) {
    els.detailGold.textContent = "root";
  } else {
    els.detailGold.textContent = `${atom.gold_mother} ${atom.gold_mother_text ? `· ${atom.gold_mother_text}` : ""}`;
  }

  els.detailBadges.innerHTML = "";
  const badges = [
    `atom ${atom.atom}`,
    atom.book ?? "-",
    `tab ${atom.view?.tab ?? "-"}`,
    `instruction ${atom.view?.instruction ?? "--"}`,
    `${atom.predictions?.length ?? 0} candidates`,
  ];
  for (const label of badges) {
    const span = document.createElement("span");
    span.className = "badge";
    span.textContent = label;
    els.detailBadges.appendChild(span);
  }

  renderPhrases(atom.view?.phrases ?? []);
  renderCandidates(atom.predictions ?? []);
  renderUrl(atom.atom);
}

function renderCandidates(predictions) {
  els.candidateList.innerHTML = "";
  if (!predictions.length) {
    els.candidateList.innerHTML = '<p class="status">표시할 candidate가 없습니다.</p>';
    return;
  }

  predictions.forEach((candidate, index) => {
    const card = document.createElement("div");
    card.className = "candidate";
    const top = document.createElement("div");
    top.className = "candidate-top";
    top.innerHTML = `<strong>#${index + 1} mother ${candidate.mother}</strong><span class="candidate-score">${scoreLabel(candidate.score)}</span>`;

    const text = document.createElement("div");
    text.className = "candidate-meta";
    text.innerHTML = `<span>${candidate.mother_text ?? "-"}</span><span>${sectionLabel(candidate.mother_section)}</span>`;

    const labels = document.createElement("div");
    labels.className = "candidate-labels";
    const labelsToRender = candidateLabel(candidate);
    if (candidate.is_gold) {
      labelsToRender.push("gold");
    }
    for (const label of labelsToRender) {
      const pill = document.createElement("span");
      pill.className = "pill";
      pill.textContent = label;
      labels.appendChild(pill);
    }

    const evidence = document.createElement("div");
    evidence.className = "evidence-list";
    for (const ev of candidate.evidences ?? []) {
      const chip = document.createElement("span");
      chip.className = "evidence";
      chip.textContent = ev.label;
      evidence.appendChild(chip);
    }

    card.append(top, text, labels, evidence);
    els.candidateList.appendChild(card);
  });
}

function renderUrl(atomId) {
  const url = new URL(window.location.href);
  url.searchParams.set("atom", String(atomId));
  if (state.currentBook) {
    url.searchParams.set("book", state.currentBook);
  }
  window.history.replaceState({}, "", url);
}

async function openAtom(atomId) {
  const atomKey = String(atomId);
  const catalogRow = state.atomIndex.get(atomKey);
  if (!catalogRow) {
    setStatus(`clause atom ${atomId} 을(를) 찾지 못했습니다.`);
    return;
  }

  els.atomInput.value = atomKey;
  els.bookSelect.value = catalogRow.book_slug;
  setStatus(`clause atom ${atomKey} 를 불러오는 중...`);

  let atom;
  try {
    atom = await loadAtom(atomKey);
  } catch (error) {
    console.error(error);
    setStatus(`clause atom ${atomKey} 상세 JSON을 불러오지 못했습니다.`);
    return;
  }

  renderBookList(catalogRow.book_slug, atomKey);
  renderDetail(atom);
  setStatus(`clause atom ${atomKey} 를 표시 중입니다.`);
}

async function syncBookSelection(bookSlug) {
  renderBookList(bookSlug, state.currentAtom?.atom ?? null);
  const atoms = atomsForBook(bookSlug);
  const hasCurrent = state.currentAtom && state.currentAtom.book_slug === bookSlug;
  const first = atoms[0];
  if (first && !hasCurrent) {
    await openAtom(first.atom ?? first.daughter);
  }
}

function currentAtomId() {
  const value = Number(els.atomInput.value);
  return Number.isFinite(value) && value > 0 ? value : null;
}

function currentBookAtoms() {
  return atomsForBook(els.bookSelect.value);
}

async function goPrevious() {
  const atoms = currentBookAtoms();
  if (!atoms.length) return;
  const currentId = String(state.currentAtom?.atom ?? "");
  const currentIndex = atoms.findIndex((atom) => String(atom.atom ?? atom.daughter) === currentId);
  const nextAtom = atoms[Math.max(0, currentIndex - 1)];
  if (nextAtom) {
    await openAtom(nextAtom.atom ?? nextAtom.daughter);
  }
}

async function goNext() {
  const atoms = currentBookAtoms();
  if (!atoms.length) return;
  const currentId = String(state.currentAtom?.atom ?? "");
  const currentIndex = atoms.findIndex((atom) => String(atom.atom ?? atom.daughter) === currentId);
  const nextAtom = atoms[Math.min(atoms.length - 1, currentIndex + 1)];
  if (nextAtom) {
    await openAtom(nextAtom.atom ?? nextAtom.daughter);
  }
}

async function init() {
  els.metaStatus = $("meta-status");
  els.statusLine = $("status-line");
  els.bookSelect = $("book-select");
  els.atomInput = $("atom-input");
  els.openButton = $("open-button");
  els.prevButton = $("prev-button");
  els.nextButton = $("next-button");
  els.atomList = $("atom-list");
  els.bookSummary = $("book-summary");
  els.detailTitle = $("detail-title");
  els.detailText = $("detail-text");
  els.detailMeta = $("detail-meta");
  els.detailGold = $("detail-gold");
  els.detailBadges = $("detail-badges");
  els.phraseList = $("phrase-list");
  els.candidateList = $("candidate-list");

  try {
    const params = new URL(window.location.href).searchParams;
    const dataRoot = params.get("data");
    if (dataRoot) {
      state.dataRoot = dataRoot.replace(/\/+$/, "");
    }

    const [meta, catalog] = await Promise.all([fetchJson("meta.json"), fetchJson("catalog.json")]);
    state.meta = meta;
    state.catalog = catalog;
    buildIndexes();
    populateBooks();

    setMetaStatus(`generated ${meta.generated_at} · ${fmtNumber(meta.atom_count ?? catalog.atoms.length)} atoms · top-k ${meta.top_k}`);

    const requestedAtom = params.get("atom");
    const requestedBook = params.get("book");
    const defaultBook = requestedBook && state.bookIndex.has(requestedBook) ? requestedBook : catalog.books[0]?.book_slug ?? null;

    if (defaultBook) {
      els.bookSelect.value = defaultBook;
      await syncBookSelection(defaultBook);
    }

    if (requestedAtom && state.atomIndex.has(requestedAtom)) {
      await openAtom(requestedAtom);
    } else if (defaultBook && state.currentAtom) {
      renderUrl(state.currentAtom.atom);
    } else if (defaultBook) {
      const first = currentBookAtoms()[0];
      if (first) {
        await openAtom(first.atom ?? first.daughter);
      }
    }

    setStatus("데이터 로드가 완료되었습니다.");
  } catch (error) {
    console.error(error);
    setMetaStatus("데이터를 불러오지 못했습니다.");
    setStatus("정적 JSON을 로드할 수 없습니다. `site/data/` 생성 여부를 확인하세요.");
    els.atomList.innerHTML = `<p class="status">${error.message}</p>`;
  }

  els.bookSelect.addEventListener("change", async () => {
    await syncBookSelection(els.bookSelect.value);
  });

  els.openButton.addEventListener("click", async () => {
    const atomId = currentAtomId();
    if (atomId === null) {
      setStatus("유효한 clause atom ID를 입력하세요.");
      return;
    }
    await openAtom(atomId);
  });

  els.atomInput.addEventListener("keydown", async (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      const atomId = currentAtomId();
      if (atomId !== null) {
        await openAtom(atomId);
      }
    }
  });

  els.prevButton.addEventListener("click", goPrevious);
  els.nextButton.addEventListener("click", goNext);
}

document.addEventListener("DOMContentLoaded", init);
