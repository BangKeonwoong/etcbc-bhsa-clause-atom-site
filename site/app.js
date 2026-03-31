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

const CODE_LABELS = {
  typ: "절 유형",
  tab: "배열 코드",
  sub1: "하위 분류 1",
  sub2: "하위 분류 2",
  instruction: "후보군 규칙",
  lex: "어휘형",
  vt: "동사 시제",
  vs: "동사 어간",
  ps: "인칭",
  nu: "수",
  gn: "성",
  prs: "접미 대명사",
  prs_ps: "접미 대명사 인칭",
  prs_nu: "접미 대명사 수",
  prs_gn: "접미 대명사 성",
};

const CODE_DESCRIPTIONS = {
  typ: "절의 큰 유형을 가리키는 BHSA/ETCBC 원본 코드입니다.",
  tab: "절이 문맥 안에서 어떻게 배열되는지 보여 주는 원본 코드입니다.",
  sub1: "절 분류의 1차 하위 범주를 나타내는 원본 코드입니다.",
  sub2: "절 분류의 2차 하위 범주를 나타내는 원본 코드입니다.",
  instruction: "어미절 후보군을 만들 때 사용한 규칙 코드입니다.",
  lex: "서술어의 기본 어휘형을 나타내는 원본 코드입니다.",
  vt: "서술어의 동사 시제 관련 코드를 보여 줍니다.",
  vs: "서술어의 동사 어간(stem) 코드를 보여 줍니다.",
  ps: "서술어의 인칭(person) 코드를 보여 줍니다.",
  nu: "서술어의 수(number) 코드를 보여 줍니다.",
  gn: "서술어의 성(gender) 코드를 보여 줍니다.",
  prs: "접미 대명사(pronominal suffix) 코드를 보여 줍니다.",
  prs_ps: "접미 대명사의 인칭 코드를 보여 줍니다.",
  prs_nu: "접미 대명사의 수 코드를 보여 줍니다.",
  prs_gn: "접미 대명사의 성 코드를 보여 줍니다.",
};

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
  if (candidate.parallel) parts.push("병렬");
  if (candidate.quotation) parts.push("인용");
  return parts.length ? parts : ["관계 없음"];
}

async function fetchJson(path) {
  const response = await fetch(dataUrl(path), { cache: "no-cache" });
  if (!response.ok) {
    throw new Error(`${path} 로드 실패: ${response.status}`);
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

function codeLabel(key) {
  return CODE_LABELS[key] ?? key;
}

function codeDescription(key) {
  return CODE_DESCRIPTIONS[key] ?? "원본 기술 코드를 그대로 보여 주는 항목입니다.";
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
    renderStatusBlock(els.atomList, "이 책에 표시할 절원자가 없습니다.");
    els.bookSummary.textContent = "-";
    return;
  }

  const firstAtom = atoms[0]?.atom ?? atoms[0]?.daughter;
  const lastAtom = atoms[atoms.length - 1]?.atom ?? atoms[atoms.length - 1]?.daughter;
  els.bookSummary.textContent = `${book?.book ?? "-"} · ${fmtNumber(book?.atom_count ?? atoms.length)}개 절원자 · ${firstAtom ?? "-"}-${lastAtom ?? "-"}`;

  for (const atom of atoms) {
    const button = document.createElement("button");
    button.type = "button";
    const atomId = atom.atom ?? atom.daughter;
    button.className = `atom-item${String(atomId) === String(activeId) ? " active" : ""}`;
    button.setAttribute("aria-current", String(atomId) === String(activeId) ? "true" : "false");
    button.addEventListener("click", () => openAtom(atomId));

    const row = document.createElement("div");
    row.className = "ledger-row";

    const atomCell = document.createElement("div");
    atomCell.className = "ledger-cell ledger-cell-atom";
    const atomLabel = document.createElement("strong");
    atomLabel.textContent = `절원자 ${atomId}`;
    atomCell.appendChild(atomLabel);

    const sectionCell = document.createElement("div");
    sectionCell.className = "ledger-cell ledger-cell-section";
    sectionCell.textContent = sectionLabel(atom.section);

    const hebrewCell = document.createElement("div");
    hebrewCell.className = "ledger-cell ledger-cell-hebrew hebrew-text";
    hebrewCell.textContent = atom.text || "-";

    const predictionCell = document.createElement("div");
    predictionCell.className = "ledger-cell ledger-cell-prediction";
    const prediction = atom.top_prediction;
    if (prediction) {
      predictionCell.append(
        makeToken(`어미 ${prediction.mother}`, "mini-badge"),
        makeToken(prediction.predicted_rela ?? "관계 미상", "mini-badge"),
        makeToken(scoreLabel(prediction.score), "mini-badge"),
      );
    } else {
      predictionCell.append(makeToken("예측 없음", "mini-badge"));
    }

    row.append(atomCell, sectionCell, hebrewCell, predictionCell);
    button.append(row);
    els.atomList.appendChild(button);
  }

  updateNavigationButtons();
}

function renderFlags(atom) {
  clearElement(els.detailFlags);
  const view = atom.view ?? {};
  const flags = [
    view.typ ? `절 유형 ${view.typ}` : null,
    view.sub1 ? `하위 분류 1 ${view.sub1}` : null,
    view.sub2 && view.sub2 !== "." ? `하위 분류 2 ${view.sub2}` : null,
    view.instruction ? `지시 ${view.instruction}` : null,
    view.explicit_subject ? "명시적 주어" : null,
    view.has_fronting ? "전위" : null,
    view.has_vocative ? "호격" : null,
    view.question_marked ? "의문 표지" : null,
    view.relative_marker ? "관계 표지" : null,
    view.quote_verb ? "인용 동사" : null,
    view.coordinating_conjunction ? `등위 ${view.coordinating_conjunction}` : null,
    view.subordinating_conjunction ? `종속 ${view.subordinating_conjunction}` : null,
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
    renderStatusBlock(els.predicateCard, "서술어 정보가 없습니다.");
  } else {
    for (const [label, value] of metrics) {
      const tile = document.createElement("div");
      tile.className = "predicate-metric";
      const labelNode = document.createElement("span");
      labelNode.className = "metric-label";
      labelNode.textContent = codeLabel(label);
      const codeNode = document.createElement("span");
      codeNode.className = "metric-code";
      codeNode.textContent = label;
      const valueNode = document.createElement("span");
      valueNode.className = "metric-value";
      valueNode.textContent = String(value);
      tile.append(labelNode, codeNode, valueNode);
      els.predicateCard.appendChild(tile);
    }
  }

  const summaryParts = [
    view?.predicate?.lex ? `서술어 ${view.predicate.lex}` : "서술어 -",
    view?.tab ? `배열 ${view.tab}` : null,
    view?.sub1 ? `하위 분류 1 ${view.sub1}` : null,
    view?.sub2 && view.sub2 !== "." ? `하위 분류 2 ${view.sub2}` : null,
  ].filter(Boolean);
  els.predicateSummary.textContent = summaryParts.join(" · ");
}

function renderCodeGuide(view) {
  clearElement(els.codeGuide);
  const predicate = view?.predicate ?? null;
  const entries = [
    view?.typ ? ["typ", view.typ] : null,
    view?.tab ? ["tab", view.tab] : null,
    view?.sub1 ? ["sub1", view.sub1] : null,
    view?.sub2 && view.sub2 !== "." ? ["sub2", view.sub2] : null,
    view?.instruction ? ["instruction", view.instruction] : null,
    predicate?.lex ? ["lex", predicate.lex] : null,
    predicate?.vt ? ["vt", predicate.vt] : null,
    predicate?.vs ? ["vs", predicate.vs] : null,
    predicate?.ps ? ["ps", predicate.ps] : null,
    predicate?.nu ? ["nu", predicate.nu] : null,
    predicate?.gn ? ["gn", predicate.gn] : null,
    predicate?.prs ? ["prs", predicate.prs] : null,
    predicate?.prs_ps ? ["prs_ps", predicate.prs_ps] : null,
    predicate?.prs_nu ? ["prs_nu", predicate.prs_nu] : null,
    predicate?.prs_gn ? ["prs_gn", predicate.prs_gn] : null,
  ].filter(Boolean);

  if (!entries.length) {
    renderStatusBlock(els.codeGuide, "설명할 기술 코드가 없습니다.");
    return;
  }

  const intro = document.createElement("p");
  intro.className = "code-guide-intro";
  intro.textContent = "아래 값은 BHSA/ETCBC 원본 표식을 그대로 보여 주며, 각 항목이 무엇을 뜻하는지 짧게 설명합니다.";
  els.codeGuide.appendChild(intro);

  const grid = document.createElement("div");
  grid.className = "code-guide-grid";

  for (const [key, value] of entries) {
    const item = document.createElement("article");
    item.className = "code-guide-item";

    const head = document.createElement("div");
    head.className = "code-guide-head";

    const title = document.createElement("strong");
    title.textContent = codeLabel(key);

    const raw = document.createElement("span");
    raw.className = "code-guide-key";
    raw.textContent = key;

    head.append(title, raw);

    const current = document.createElement("p");
    current.className = "code-guide-value";
    current.textContent = `현재 값: ${value}`;

    const description = document.createElement("p");
    description.className = "code-guide-description";
    description.textContent = codeDescription(key);

    item.append(head, current, description);
    grid.appendChild(item);
  }

  els.codeGuide.appendChild(grid);
}

function renderPhraseGroups(view) {
  clearElement(els.phraseGroups);
  const opening = view?.opening_phrases ?? [];
  const preverbal = view?.preverbal_phrases ?? [];
  const postverbal = view?.postverbal_phrases ?? [];
  const groupedIds = new Set([...opening, ...preverbal, ...postverbal].map((phrase) => phrase.node));
  const other = (view?.phrases ?? []).filter((phrase) => !groupedIds.has(phrase.node));
  const groups = [
    ["도입 구", opening],
    ["서술어 앞 구", preverbal],
    ["서술어 뒤 구", postverbal],
    ["기타 구", other],
  ];

  const visibleGroups = groups.filter(([, phrases]) => phrases.length);
  if (!visibleGroups.length) {
    renderStatusBlock(els.phraseGroups, "표시할 구문 그룹이 없습니다.");
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
    count.textContent = `${phrases.length}개`;

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

  els.detailTitle.textContent = `절원자 ${atom.atom}`;
  els.detailLocation.textContent = `${sectionLabel(atom.section)} · ${atom.book ?? "-"} · 정답 관계 ${atom.gold_relation ?? "-"}`;
  els.detailText.textContent = atom.text || view.text || "-";

  if (atom.gold_mother === null || atom.gold_mother === undefined) {
    els.detailGold.textContent = "최상위 절(root)";
  } else {
    els.detailGold.textContent = `어미절 ${atom.gold_mother}${atom.gold_mother_text ? ` · ${atom.gold_mother_text}` : ""}`;
  }

  els.detailSummary.textContent = topPrediction
    ? `어미절 ${topPrediction.mother} · 점수 ${scoreLabel(topPrediction.score)} · 관계 ${topPrediction.predicted_rela ?? "미상"}`
    : "예측 후보가 없습니다.";

  clearElement(els.detailBadges);
  const badges = [
    `절원자 ${atom.atom}`,
    atom.book ?? "-",
    `배열 ${view.tab ?? "-"}`,
    `후보군 규칙 ${view.instruction ?? "--"}`,
    `${atom.predictions?.length ?? 0}개 후보`,
  ];
  for (const label of badges) {
    els.detailBadges.appendChild(makeToken(label, "badge"));
  }

  renderFlags(atom);
  renderPredicate(view);
  renderCodeGuide(view);
  renderPhraseGroups(view);
  renderCandidates(atom.predictions ?? []);
  els.detailContextLocation.textContent = sectionLabel(atom.section);
  els.detailContextPool.textContent = fmtNumber(atom.pool_size ?? 0);
  els.detailContextNav.textContent = `${atom.prev_atom ?? "시작"} / ${atom.next_atom ?? "끝"}`;
  els.detailContextTopk.textContent = fmtNumber(atom.predictions?.length ?? 0);
  const noteParts = [
    view.explicit_subject ? "명시적 주어" : null,
    view.has_fronting ? "전위" : null,
    view.question_marked ? "의문 표지" : null,
    view.relative_marker ? `관계 ${view.relative_marker}` : null,
    view.opening_conjunction_lexemes?.length ? `도입 접속사 ${view.opening_conjunction_lexemes.join(", ")}` : null,
    view.opening_preposition_lexemes?.length ? `도입 전치사 ${view.opening_preposition_lexemes.join(", ")}` : null,
  ].filter(Boolean);
  els.detailContextNote.textContent = noteParts.join(" · ") || "추가 메모가 없습니다.";
  renderUrl(atom.atom);
  updateNavigationButtons();
}

function renderCandidates(predictions) {
  clearElement(els.candidateList);
  if (!predictions.length) {
    renderStatusBlock(els.candidateList, "표시할 후보가 없습니다.");
    els.candidateSummary.textContent = "후보가 없습니다.";
    return;
  }

  const maxScore = Math.max(...predictions.map((candidate) => Number(candidate.score) || 0), 1);
  const goldText =
    state.currentAtom?.gold_mother === null || state.currentAtom?.gold_mother === undefined
      ? "최상위 절(root)"
      : `어미절 ${state.currentAtom.gold_mother}`;
  els.candidateSummary.textContent = `${predictions.length}개 후보 · 후보군 ${fmtNumber(state.currentAtom?.pool_size ?? 0)} · 정답 ${goldText}`;

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
    title.textContent = `#${index + 1} 어미절 ${candidate.mother}`;
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
      labelsToRender.push("정답");
    }
    for (const label of labelsToRender) {
      labels.appendChild(makeToken(label, "pill"));
    }
    if (clickable) {
      labels.appendChild(makeToken("어미절 열기", "pill"));
    }

    const evidence = document.createElement("div");
    evidence.className = "evidence-list";
    for (const ev of candidate.evidences ?? []) {
      evidence.appendChild(makeToken(ev.label ?? "근거", "evidence"));
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
    setStatus(`절원자 ${atomId} 을(를) 찾지 못했습니다.`);
    return;
  }

  els.atomInput.value = atomKey;
  els.bookSelect.value = catalogRow.book_slug;
  setStatus(`절원자 ${atomKey} 를 불러오는 중...`);
  const requestSeq = ++state.requestSeq;

  let atom;
  try {
    atom = await loadAtom(atomKey);
  } catch (error) {
    console.error(error);
    setStatus(`절원자 ${atomKey} 상세 JSON을 불러오지 못했습니다.`);
    return;
  }
  if (requestSeq !== state.requestSeq) {
    return;
  }

  renderBookList(catalogRow.book_slug, atomKey);
  renderDetail(atom);
  setStatus(`절원자 ${atomKey} 를 표시 중입니다.`);
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
  els.codeGuide = $("code-guide");
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

    setMetaStatus(`생성 ${meta.generated_at} · ${fmtNumber(meta.atom_count ?? catalog.atoms.length)}개 절원자 · 상위 ${meta.top_k}개 후보`);

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
      setStatus("유효한 절원자 ID를 입력하세요.");
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
