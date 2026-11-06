'use strict';

function hasReviewFeedback(entry) {
  return entry.note.trim().length > 0 || entry.pins.length > 0;
}

function completeReviewedEntry(entry) {
  if (hasReviewFeedback(entry)) entry.status = 'change';
  else if (entry.status === 'pending') entry.status = 'done';
}

function updateReviewNote(entry, note) {
  const hadFeedback = hasReviewFeedback(entry);
  entry.note = note;
  if (hasReviewFeedback(entry)) entry.status = 'change';
  else if (hadFeedback && entry.status === 'change') entry.status = 'pending';
}

function clearReviewPins(entry) {
  const hadFeedback = hasReviewFeedback(entry);
  entry.pins = [];
  if (hasReviewFeedback(entry)) entry.status = 'change';
  else if (hadFeedback && entry.status === 'change') entry.status = 'pending';
}

if (typeof module !== 'undefined' && module.exports) {
  module.exports = {hasReviewFeedback, completeReviewedEntry, updateReviewNote, clearReviewPins};
}
