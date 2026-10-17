const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const root = path.join(__dirname, '..');
const catalog = JSON.parse(fs.readFileSync(path.join(root, 'static/locales/catalog.json'), 'utf8'));
const element = {nodeType: 1, closest: () => false, getAttribute: () => null};
const storage = new Map();
const context = vm.createContext({
  document: {body: element, documentElement: {}, title: '', addEventListener: () => {}, querySelectorAll: () => [], createTreeWalker: () => ({nextNode: () => null})},
  Node: {TEXT_NODE: 3, ELEMENT_NODE: 1}, NodeFilter: {SHOW_ELEMENT: 1, SHOW_TEXT: 4},
  MutationObserver: class {observe() {}},
  localStorage: {getItem: key => storage.get(key), setItem: (key, value) => storage.set(key, value)},
  fetch: async () => ({ok: true, json: async () => catalog}),
});
vm.runInContext(fs.readFileSync(path.join(root, 'static/js/i18n.js'), 'utf8'), context);
const i18n = vm.runInContext('I18n', context);

test('all catalog messages have Russian and Kazakh translations', () => {
  for (const [source, translations] of Object.entries(catalog.messages)) {
    for (const language of ['ru', 'kk']) {
      assert.equal(typeof translations[language], 'string', `${source}: ${language}`);
      assert.ok(/[А-Яа-яӘәҒғҚқҢңӨөҰұҮүҺһІі]/u.test(translations[language]), `${source}: ${language}`);
    }
  }
});

test('every template compiles and preserves the same placeholders', () => {
  for (const rule of catalog.rules) {
    new RegExp(`^(?:${rule.pattern})$`, 'u');
    assert.deepEqual(rule.ru.match(/\{\d+\}/g), rule.kk.match(/\{\d+\}/g));
  }
});

test('Russian default, Kazakh preference, templates and dynamic DOM text', async () => {
  await i18n.load();
  assert.equal(i18n.savedLanguage(), 'ru');
  assert.equal(i18n.t('Sign in'), 'Войти');
  assert.equal(i18n.t('My profile', 'kz'), 'Менің профилім');
  assert.equal(i18n.t('Pending · Synthetic example'), 'На рассмотрении · Вымышленный пример');
  assert.equal(i18n.t('Request REQ-N000001 successfully created!', 'kz'), 'REQ-N000001 өтініші сәтті жасалды!');
  const node = {nodeType: 3, parentElement: {closest: () => false}, nodeValue: 'Pending'};
  i18n.render(node);
  assert.equal(node.nodeValue, 'На рассмотрении');
  i18n.apply('kz');
  i18n.render(node);
  assert.equal(node.nodeValue, 'Қаралуда');
  node.nodeValue = 'Approved';
  i18n.render(node);
  assert.equal(node.nodeValue, 'Мақұлданды');
  assert.equal(i18n.savedLanguage(), 'kz');
});

test('authored source text and proper identifiers remain untouched', () => {
  const node = {nodeType: 3, parentElement: {closest: () => true}, nodeValue: 'Approved'};
  i18n.render(node);
  assert.equal(node.nodeValue, 'Approved');
  assert.equal(i18n.t('REQ-N000042'), 'REQ-N000042');
  assert.equal(i18n.t('employee.demo@example.com'), 'employee.demo@example.com');
});

test('date labels use Russian and Kazakh month names even without browser ICU data', () => {
  vm.runInContext(fs.readFileSync(path.join(root, 'static/js/app.js'), 'utf8'), context);
  assert.equal(vm.runInContext("state.lang = 'ru'; formatDate('2026-10-30')", context), '30 октября 2026 г.');
  assert.equal(vm.runInContext("state.lang = 'kz'; formatDate('2026-10-30')", context), '30 қазан 2026 ж.');
});
