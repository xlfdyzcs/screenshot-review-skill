'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const {hasReviewFeedback, completeReviewedEntry, updateReviewNote, clearReviewPins} = require('../screenshot-review/assets/review-state.js');

const fresh = () => ({status:'pending', note:'', pins:[]});

test('completing one reviewed item leaves the next item unreviewed', () => {
  const current = fresh(), next = fresh();
  completeReviewedEntry(current);
  assert.equal(current.status, 'done');
  assert.equal(next.status, 'pending');
  completeReviewedEntry(current);
  assert.equal(current.status, 'done');
});

test('nonblank comments require changes immediately and remain so on completion', () => {
  for (const status of ['pending','done']) {
    const entry = {...fresh(), status};
    updateReviewNote(entry, '  Please increase the label size.  ');
    assert.equal(entry.status, 'change');
    completeReviewedEntry(entry);
    assert.equal(entry.status, 'change');
    assert.equal(entry.note, '  Please increase the label size.  ');
  }
});

test('whitespace alone is not a modification request', () => {
  const entry = fresh();
  updateReviewNote(entry, ' \n\t ');
  assert.equal(entry.status, 'pending');
  assert.equal(hasReviewFeedback(entry), false);
  completeReviewedEntry(entry);
  assert.equal(entry.status, 'done');
});

test('cleared comments await completion and are checked when leaving', () => {
  const entry = fresh();
  updateReviewNote(entry, 'Needs work');
  updateReviewNote(entry, '');
  assert.equal(entry.status, 'pending');
  completeReviewedEntry(entry);
  assert.equal(entry.status, 'done');
});

test('remaining pins or comments prevent automatic approval', () => {
  const entry = {status:'change', note:'Needs work', pins:[{app:'after', shot:0, x:10, y:20}]};
  updateReviewNote(entry, '');
  assert.equal(entry.status, 'change');
  completeReviewedEntry(entry);
  assert.equal(entry.status, 'change');
  updateReviewNote(entry, 'Still needs work');
  clearReviewPins(entry);
  assert.equal(entry.status, 'change');
  assert.deepEqual(entry.pins, []);
});

test('clearing the final feedback allows approval on completion', () => {
  const entry = {status:'change', note:'', pins:[{app:'after', shot:0, x:10, y:20}]};
  clearReviewPins(entry);
  assert.equal(entry.status, 'pending');
  completeReviewedEntry(entry);
  assert.equal(entry.status, 'done');
});

test('an explicit needs-change flag without feedback remains flagged', () => {
  const entry = {...fresh(), status:'change'};
  completeReviewedEntry(entry);
  assert.equal(entry.status, 'change');
  clearReviewPins(entry);
  assert.equal(entry.status, 'change');
});

test('text and status survive a saved JSON roundtrip', () => {
  const entry = fresh();
  updateReviewNote(entry, '按钮间距减小');
  const restored = JSON.parse(JSON.stringify(entry));
  completeReviewedEntry(restored);
  assert.equal(restored.status, 'change');
  assert.equal(restored.note, '按钮间距减小');
});
