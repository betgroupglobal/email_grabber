"use strict";

const MAX_TERMINAL_LINES = 500;

function appendTerminalLine(engagements, engId, line) {
  const eng = engagements.get(engId);
  if (!eng || !line?.content) return;
  if (!eng.terminal_history) eng.terminal_history = [];
  eng.terminal_history.push(line);
  if (eng.terminal_history.length > MAX_TERMINAL_LINES) {
    eng.terminal_history.splice(0, eng.terminal_history.length - MAX_TERMINAL_LINES);
  }
}

function getTerminalHistory(engagements, engId, limit = 200) {
  const eng = engagements.get(engId);
  if (!eng?.terminal_history?.length) return [];
  const cap = Math.min(Math.max(1, limit), MAX_TERMINAL_LINES);
  return eng.terminal_history.slice(-cap);
}

module.exports = {
  appendTerminalLine,
  getTerminalHistory,
  MAX_TERMINAL_LINES,
};
