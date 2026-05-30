"use strict";

const LIVE_COUNCIL_DEFAULT =
  process.env.LIVE_COUNCIL_DEFAULT === "true" ||
  process.env.LIVE_COUNCIL_DEFAULT === "1";

function isLiveCouncilEnabled(eng, reqBody = {}) {
  if (reqBody.live_council === false) return false;
  if (reqBody.live_council === true) return true;
  if (eng.live_council?.enabled) return true;
  if (eng.source === "guided_autonomous") return true;
  return LIVE_COUNCIL_DEFAULT;
}

module.exports = {
  isLiveCouncilEnabled,
  LIVE_COUNCIL_DEFAULT,
};
