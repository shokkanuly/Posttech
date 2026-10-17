/** Complete presentation localization. API enums, IDs and authored source text are preserved. */
const I18n = (() => {
  let catalog = {messages: {}, rules: []};
  let language = "ru";
  let reverse = new Map();
  const originals = new WeakMap();
  const attributes = new WeakMap();
  const excluded = "script,style,code,[data-verbatim],#citationSnippet,#citationDocTitle,#citationSecTitle";
  const normalize = value => String(value).replace(/\s+/g, " ").trim();
  function savedLanguage() {
    try { return ["kk", "kz"].includes(localStorage.getItem("janamen-language")) ? "kz" : "ru"; }
    catch { return "ru"; }
  }
  function t(value, selected = language, depth = 0) {
    const raw = String(value ?? "");
    if (depth > 5) return raw;
    const locale = selected === "kz" ? "kk" : selected;
    const key = reverse.get(normalize(raw)) || normalize(raw);
    const exact = catalog.messages[key]?.[locale];
    if (exact !== undefined) return exact;
    for (const rule of catalog.rules) {
      const match = new RegExp(`^(?:${rule.pattern})$`, "u").exec(key);
      if (match) return rule[locale].replace(/\{(\d+)\}/g, (_, index) => t(match[Number(index) + 1] || "", selected, depth + 1));
    }
    if (key.includes(" · ")) return key.split(" · ").map(part => t(part, selected, depth + 1)).join(" · ");
    return raw;
  }
  function textNode(node) {
    if (!node.parentElement || node.parentElement.closest(excluded) || !node.nodeValue.trim()) return;
    const previous = originals.get(node);
    const source = previous && node.nodeValue === previous.rendered ? previous.source : node.nodeValue;
    const whitespace = source.match(/^(\s*)([\s\S]*?)(\s*)$/);
    const rendered = whitespace[1] + t(whitespace[2]) + whitespace[3];
    originals.set(node, {source, rendered});
    if (node.nodeValue !== rendered) node.nodeValue = rendered;
  }
  function elementAttributes(element) {
    if (element.closest(excluded)) return;
    const saved = attributes.get(element) || {};
    for (const name of ["placeholder", "aria-label", "title", "data-question"]) {
      const value = element.getAttribute(name);
      if (value === null) continue;
      const previous = saved[name];
      const source = previous && value === previous.rendered ? previous.source : value;
      const rendered = t(source);
      saved[name] = {source, rendered};
      if (value !== rendered) element.setAttribute(name, rendered);
    }
    attributes.set(element, saved);
  }
  function render(root = document.body) {
    if (root.nodeType === Node.TEXT_NODE) { textNode(root); return; }
    if (root.nodeType !== Node.ELEMENT_NODE) return;
    elementAttributes(root);
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) {
      if (node.nodeType === Node.TEXT_NODE) textNode(node);
      else elementAttributes(node);
    }
  }
  async function load() {
    const response = await fetch("/static/locales/catalog.json", {cache: "no-cache"});
    if (!response.ok) throw new Error("Не удалось загрузить переводы. Обновите страницу.");
    catalog = await response.json();
    for (const [source, translations] of Object.entries(catalog.messages)) {
      for (const value of Object.values(translations)) if (!reverse.has(normalize(value))) reverse.set(normalize(value), source);
    }
    language = savedLanguage();
    apply(language);
    new MutationObserver(records => {
      for (const record of records) {
        if (record.type === "characterData") textNode(record.target);
        else if (record.type === "attributes") elementAttributes(record.target);
        else for (const node of record.addedNodes) render(node);
      }
    }).observe(document.body, {subtree: true, childList: true, characterData: true, attributes: true,
      attributeFilter: ["placeholder", "aria-label", "title", "data-question"]});
    document.querySelectorAll("input,textarea,select").forEach(input => {
      input.addEventListener("invalid", () => input.setCustomValidity(t(input.validity.valueMissing ? "Please fill out this field." : "Please enter a valid value.")));
      input.addEventListener("input", () => input.setCustomValidity(""));
      input.addEventListener("change", () => input.setCustomValidity(""));
    });
  }
  function apply(value) {
    language = value === "kz" || value === "kk" ? "kz" : "ru";
    document.documentElement.lang = language === "kz" ? "kk" : "ru";
    document.title = t("JanaМен · People Workspace | Jana Post");
    document.querySelectorAll("[data-language-select]").forEach(select => { select.value = language; });
    document.querySelectorAll("input,textarea,select").forEach(input => input.setCustomValidity(""));
    render();
    try { localStorage.setItem("janamen-language", language); } catch { /* preference storage may be disabled */ }
  }
  return {load, apply, t, render, savedLanguage};
})();
