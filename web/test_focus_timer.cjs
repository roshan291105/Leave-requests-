const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const code = fs.readFileSync(`${__dirname}/static/js/my_day.js`, 'utf8');

function openTimer(storage = new Map(), employee = '1', start = 10000000, brokenStorage = false) {
  let now = start;
  let tick;
  const elements = {};
  for (const selector of ['#focus-duration', '.focus-clock', '[data-focus-toggle]', '[data-focus-reset]', '.focus-message']) {
    elements[selector] = {textContent: '', value: '25', disabled: false, listeners: {},
      addEventListener(name, handler) { this.listeners[name] = handler; }};
  }
  const panel = {dataset: {employee}, querySelector: (selector) => elements[selector]};
  vm.runInNewContext(code, {
    document: {querySelector: () => panel, addEventListener() {}},
    window: {addEventListener() {}}, Date: {now: () => now},
    setInterval: (fn) => { tick = fn; },
    sessionStorage: {
      getItem(key) { if (brokenStorage) throw Error('Blocked'); return storage.get(key) || null; },
      setItem(key, value) { if (brokenStorage) throw Error('Blocked'); storage.set(key, value); },
    },
  });
  return {
    elements, advance(ms) { now += ms; tick(); },
    click(selector) { elements[selector].listeners.click(); },
    select(minutes) { elements['#focus-duration'].value = String(minutes); elements['#focus-duration'].listeners.change(); },
    text: () => elements['.focus-clock'].textContent,
  };
}

const storage = new Map();
let timer = openTimer(storage);
assert.equal(timer.text(), '25:00');
timer.click('[data-focus-toggle]');
timer.advance(60000);
assert.equal(timer.text(), '24:00');
assert.equal(timer.elements['#focus-duration'].disabled, true);
timer.click('[data-focus-toggle]');
timer.advance(60000);
assert.equal(timer.text(), '24:00');
timer = openTimer(storage, '1', 10120000);
assert.equal(timer.text(), '24:00');
timer.click('[data-focus-toggle]');
timer = openTimer(storage, '1', 10180000);
assert.equal(timer.text(), '23:00');
assert.equal(openTimer(storage, '2').text(), '25:00');
timer.advance(30 * 60000);
assert.equal(timer.text(), '00:00');
assert.match(timer.elements['.focus-message'].textContent, /Session complete/);
timer.click('[data-focus-toggle]');
assert.equal(timer.text(), '25:00');
timer.click('[data-focus-reset]');
timer.select(5);
timer.click('[data-focus-toggle]');
timer.advance(5 * 60000);
assert.match(timer.elements['.focus-message'].textContent, /Break complete/);
timer.select(50);
assert.equal(timer.text(), '50:00');
storage.set('dayora-focus-1', '{broken json');
assert.equal(openTimer(storage).text(), '25:00');
storage.set('dayora-focus-1', JSON.stringify({minutes: 25, remaining: -1, end: null}));
assert.equal(openTimer(storage).text(), '25:00');
timer = openTimer(new Map(), '1', 10000000, true);
timer.click('[data-focus-toggle]');
timer.advance(60000);
assert.equal(timer.text(), '24:00');
assert.match(timer.elements['.focus-message'].textContent, /cannot save/);
console.log('Focus timer checks passed: pause, resume, refresh, expiry, reset, breaks, account separation, storage fallback.');
