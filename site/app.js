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
  requestSeq: 0,
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

function clearElement(node) {
  node.replaceChildren();
}

function makeToken(text, className) {
  const span = document.createElement("span");
  span.className = className;
  span.textContent = text;
  return span;
}

function renderStatusBlock(container, message) {
  clearElement(container);
  const paragraph = document.createElement("p");
  paragraph.className = "status";
  paragraph.textContent = message;
  container.appendChild(paragraph);
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

function updateNavigationButtons() {
  const atoms = currentBookAtoms();
  const currentId = String(state.currentAtom?.atom ?? "");
  const currentIndex = atoms.findIndex((atom) => String(atom.atom ?? atom.daughter) === currentId);
  els.prevButton.disabled = currentIndex <= 0;
  els.nextButton.disabled = currentIndex === -1 || currentIndex >= atoms.length - 1;
}

function renderBookList(bookSlug, activeId = null) {
  const atoms = atomsForBook(bookSlug);
  const book = state.bookIndex.get(bookSlug);
  clearElement(els.atomList);

  if (!atoms.length) {
    renderStatusBlock(els.atomList, "이 책에 표시할 atom이 없습니다.");
    els.bookSummary.textContent = "-";
    return;
  }

  const firstAtom = atoms[0]?.atom ?? atoms[0]?.daughter;
  const lastAtom = atoms[atoms.length - 1]?.atom ?? atoms[atoms.length - 1]?.daughter;
  els.bookSummary.textContent = `${book?.book ?? "-"} · ${fmtNumber(book?.atom_count ?? atoms.length)} atoms · ${firstAtom ?? "-"}-${lastAtom ?? "-"}`;

  for (const atom of atoms) {
    const button = document.createElement("button");
    button.type = "button";
    const atomId = atom.atom ?? atom.daughter;
    button.className = `atom-item${String(atomId) === String(activeId) ? " active" : ""}`;
    button.setAttribute("aria-current", String(atomId) === String(activeId) ? "true" : "false");
    button.addEventListener("click", () => openAtom(atomId));

    const header = document.createElement("div");
    header.className = "atom-item-head";

    const atomLabel = document.createElement("strong");
    atomLabel.textContent = `atom ${atomId}`;

    const section = document.createElement("span");
    section.textContent = sectionLabel(atom.section);

    header.append(atomLabel, section);

    const snippet = document.createElement("p");
    snippet.className = "atom-item-snippet";
    snippet.textContent = atom.text || "-";

    const footer = document.createElement("div");
    footer.className = "atom-item-foot";
    const prediction = atom.top_prediction;
    if (prediction) {
      footer.append(
        makeToken(`m ${prediction.mother}`, "mini-badge"),
        makeToken(prediction.predicted_rela ?? "relation ?", "mini-badge"),
        makeToken(scoreLabel(prediction.score), "mini-badge"),
      );
    } else {
      footer.append(makeToken("no prediction", "mini-badge"));
    }

    button.append(header, snippet, footer);
    els.atomList.appendChild(button);
  }

  updateNavigationButtons();
}

function renderFlags(atom) {
  clearElement(els.detailFlags);
  const view = atom.view ?? {};
  const flags = [
    view.typ ? `typ ${view.typ}` : null,
    view.sub1 ? `sub1 ${view.sub1}` : null,
    view.sub2 && view.sub2 !== "." ? `sub2 ${view.sub2}` : null,
    view.instruction ? `instr ${view.instruction}` : null,
    view.explicit_subject ? "explicit subject" : null,
    view.has_fronting ? "fronting" : null,
    view.has_vocative ? "vocative" : null,
    view.question_marked ? "question" : null,
    view.relative_marker ? "relative marker" : null,
    view.quote_verb ? "quote verb" : null,
    view.coordinating_conjunction ? `coord ${view.coordinating_conjunction}` : null,
    view.subordinating_conjunction ? `subord ${view.subordinating_conjunction}` : null,
  ].filter(Boolean);

  if (!flags.length) {
    els.detailFlags.appendChild(makeToken("표식 없음", "flag"));
    return;
  }

  for (const flag of flags) {
    els.detailFlags.appendChild(makeToken(flag, "flag"));
  }
}

function renderPredicate(view) {
  clearElement(els.predicateCard);
  const predicate = view?.predicate;
  const metrics = predicate
    ? [
        ["lex", predicate.lex],
        ["vt", predicate.vt],
        ["vs", predicate.vs],
        ["ps", predicate.ps],
        ["nu", predicate.nu],
        ["gn", predicate.gn],
        ["prs", predicate.prs],
        ["prs_ps", predicate.prs_ps],
        ["prs_nu", predicate.prs_nu],
        ["prs_gn", predicate.prs_gn],
      ].filter(([, value]) => value !== null && value !== undefined && value !== "")
    : [];

  if (!metrics.length) {
    renderStatusBlock(els.predicateCard, "predicate 정보가 없습니다.");
  } else {
    for (const [label, value] of metrics) {
      const tile = document.createElement("div");
      tile.className = "predicate-metric";
      const labelNode = document.createElement("span");
      labelNode.className = "metric-label";
      labelNode.textContent = label;
      const valueNode = document.createElement("span");
      valueNode.className = "metric-value";
      valueNode.textContent = String(value);
      tile.append(labelNode, valueNode);
      els.predicateCard.appendChild(tile);
    }
  }

  const summaryParts = [
    view?.predicate?.lex ? `predicate ${view.predicate.lex}` : "predicate -",
    view?.tab ? `tab ${view.tab}` : null,
    view?.sub1 ? `sub1 ${view.sub1}` : null,
    view?.sub2 && view.sub2 !== "." ? `sub2 ${view.sub2}` : null,
  ].filter(Boolean);
  els.predicateSummary.textContent = summaryParts.join(" · ");
}

function renderPhraseGroups(view) {
  clearElement(els.phraseGroups);
  const opening = view?.opening_phrases ?? [];
  const preverbal = view?.preverbal_phrases ?? [];
  const postverbal = view?.postverbal_phrases ?? [];
  const groupedIds = new Set([...opening, ...preverbal, ...postverbal].map((phrase) => phrase.node));
  const other = (view?.phrases ?? []).filter((phrase) => !groupedIds.has(phrase.node));
  const groups = [
    ["Opening phrases", opening],
    ["Preverbal phrases", preverbal],
    ["Postverbal phrases", postverbal],
    ["Other phrases", other],
  ];

  const visibleGroups = groups.filter(([, phrases]) => phrases.length);
  if (!visibleGroups.length) {
    renderStatusBlock(els.phraseGroups, "표시할 phrase 그룹이 없습니다.");
    return;
  }

  for (const [title, phrases] of visibleGroups) {
    const group = document.createElement("section");
    group.className = "phrase-group";

    const header = document.createElement("div");
    header.className = "phrase-group-header";

    const overline = document.createElement("span");
    overline.className = "phrase-overline";
    overline.textContent = title;

    const count = document.createElement("span");
    count.className = "metric-value";
    count.textContent = `${phrases.length} phrase${phrases.length === 1 ? "" : "s"}`;

    header.append(overline, count);
    group.appendChild(header);

    const track = document.createElement("div");
    track.className = "phrase-track";
    for (const phrase of phrases) {
      const card = document.createElement("article");
      card.className = "phrase-card";

      const meta = document.createElement("div");
      meta.className = "phrase-meta";
      const left = document.createElement("strong");
      left.textContent = phrase.function ?? "-";
      const right = document.createElement("span");
      right.textContent = phrase.typ ?? "-";
      meta.append(left, right);

      const text = document.createElement("p");
      text.className = "phrase-text";
      text.textContent = phrase.text ?? "-";

      const lexemes = document.createElement("p");
      lexemes.className = "phrase-lexemes";
      lexemes.textContent = (phrase.lexemes ?? []).join(", ") || "-";

      card.append(meta, text, lexemes);
      track.appendChild(card);
    }

    group.appendChild(track);
    els.phraseGroups.appendChild(group);
  }
}

function renderDetail(atom) {
  state.currentAtom = atom;
  state.currentBook = atom.book_slug ?? state.currentBook;
  const topPrediction = atom.predictions?.[0] ?? null;
  const view = atom.view ?? {};

  els.detailTitle.textContent = `atom ${atom.atom}`;
  els.detailLocation.textContent = `${sectionLabel(atom.section)} · ${atom.book ?? "-"} · gold relation ${atom.gold_relation ?? "-"}`;
  els.detailText.textContent = atom.text || view.text || "-";

  if (atom.gold_mother === null || atom.gold_mother === undefined) {
    els.detailGold.textContent = "root";
  } else {
    els.detailGold.textContent = `${atom.gold_mother} ${atom.gold_mother_text ? `· ${atom.gold_mother_text}` : ""}`;
  }

  els.detailSummary.textContent = topPrediction
    ? `mother ${topPrediction.mother} · ${scoreLabel(topPrediction.score)} · ${topPrediction.predicted_rela ?? "relation ?"}`
    : "예측 후보가 없습니다.";

  clearElement(els.detailBadges);
  const badges = [
    `atom ${atom.atom}`,
    atom.book ?? "-",
    `tab ${view.tab ?? "-"}`,
    `instruction ${view.instruction ?? "--"}`,
    `${atom.predictions?.length ?? 0} candidates`,
  ];
  for (const label of badges) {
    els.detailBadges.appendChild(makeToken(label, "badge"));
  }

  renderFlags(atom);
  renderPredicate(view);
  renderPhraseGroups(view);
  renderCandidates(atom.predictions ?? []);
  els.detailContextLocation.textContent = sectionLabel(atom.section);
  els.detailContextPool.textContent = fmtNumber(atom.pool_size ?? 0);
  els.detailContextNav.textContent = `${atom.prev_atom ?? "root"} / ${atom.next_atom ?? "end"}`;
  els.detailContextTopk.textContent = fmtNumber(atom.predictions?.length ?? 0);
  const noteParts = [
    view.explicit_subject ? "explicit subject" : null,
    view.has_fronting ? "fronting" : null,
    view.question_marked ? "question marked" : null,
    view.relative_marker ? `relative ${view.relative_marker}` : null,
    view.opening_conjunction_lexemes?.length ? `opening conj ${view.opening_conjunction_lexemes.join(", ")}` : null,
    view.opening_preposition_lexemes?.length ? `opening prep ${view.opening_preposition_lexemes.join(", ")}` : null,
  ].filter(Boolean);
  els.detailContextNote.textContent = noteParts.join(" · ") || "추가 메모가 없습니다.";
  renderUrl(atom.atom);
  updateNavigationButtons();
}

function renderCandidates(predictions) {
  clearElement(els.candidateList);
  if (!predictions.length) {
    renderStatusBlock(els.candidateList, "표시할 candidate가 없습니다.");
    els.candidateSummary.textContent = "후보가 없습니다.";
    return;
  }

  const maxScore = Math.max(...predictions.map((candidate) => Number(candidate.score) || 0), 1);
  const goldText =
    state.currentAtom?.gold_mother === null || state.currentAtom?.gold_mother === undefined
      ? "root"
      : `mother ${state.currentAtom.gold_mother}`;
  els.candidateSummary.textContent = `${predictions.length} candidates · pool ${fmtNumber(state.currentAtom?.pool_size ?? 0)} · gold ${goldText}`;

  predictions.forEach((candidate, index) => {
    const clickable = state.atomIndex.has(String(candidate.mother));
    const card = document.createElement(clickable ? "button" : "article");
    if (clickable) {
      card.type = "button";
      card.addEventListener("click", () => openAtom(candidate.mother));
      card.className = "candidate is-clickable";
    } else {
      card.className = "candidate";
    }
    if (index === 0) card.classList.add("is-top");
    if (candidate.is_gold) card.classList.add("is-gold");
    const ratio = Math.max(0, Math.min(1, (Number(candidate.score) || 0) / maxScore));
    card.style.setProperty("--score-ratio", ratio.toFixed(4));
    card.style.animationDelay = `${index * 36}ms`;

    const top = document.createElement("div");
    top.className = "candidate-top";
    const title = document.createElement("strong");
    title.textContent = `#${index + 1} mother ${candidate.mother}`;
    const score = document.createElement("span");
    score.className = "candidate-score";
    score.textContent = scoreLabel(candidate.score);
    top.append(title, score);

    const meta = document.createElement("div");
    meta.className = "candidate-meta";
    const metaText = document.createElement("span");
    metaText.textContent = candidate.mother_text ?? "-";
    const metaSection = document.createElement("span");
    metaSection.textContent = sectionLabel(candidate.mother_section);
    meta.append(metaText, metaSection);

    const meter = document.createElement("div");
    meter.className = "candidate-meter";
    const bar = document.createElement("span");
    meter.appendChild(bar);

    const labels = document.createElement("div");
    labels.className = "candidate-labels";
    const labelsToRender = candidateLabel(candidate);
    if (candidate.is_gold) {
      labelsToRender.push("gold");
    }
    for (const label of labelsToRender) {
      labels.appendChild(makeToken(label, "pill"));
    }
    if (clickable) {
      labels.appendChild(makeToken("open mother atom", "pill"));
    }

    const evidence = document.createElement("div");
    evidence.className = "evidence-list";
    for (const ev of candidate.evidences ?? []) {
      evidence.appendChild(makeToken(ev.label ?? "evidence", "evidence"));
    }

    card.append(top, meta, meter, labels, evidence);
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
  const requestSeq = ++state.requestSeq;

  let atom;
  try {
    atom = await loadAtom(atomKey);
  } catch (error) {
    console.error(error);
    setStatus(`clause atom ${atomKey} 상세 JSON을 불러오지 못했습니다.`);
    return;
  }
  if (requestSeq !== state.requestSeq) {
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
  els.detailLocation = $("detail-location");
  els.detailText = $("detail-text");
  els.detailGold = $("detail-gold");
  els.detailSummary = $("detail-summary");
  els.detailBadges = $("detail-badges");
  els.detailFlags = $("detail-flags");
  els.predicateSummary = $("predicate-summary");
  els.predicateCard = $("predicate-card");
  els.phraseGroups = $("phrase-groups");
  els.detailContextLocation = $("detail-context-location");
  els.detailContextPool = $("detail-context-pool");
  els.detailContextNav = $("detail-context-nav");
  els.detailContextTopk = $("detail-context-topk");
  els.detailContextNote = $("detail-context-note");
  els.candidateSummary = $("candidate-summary");
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
    renderStatusBlock(els.atomList, error.message);
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

  document.addEventListener("keydown", async (event) => {
    if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) return;
    const tag = document.activeElement?.tagName ?? "";
    if (tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA") return;
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      await goPrevious();
    }
    if (event.key === "ArrowRight") {
      event.preventDefault();
      await goNext();
    }
  });
}

document.addEventListener("DOMContentLoaded", init);
