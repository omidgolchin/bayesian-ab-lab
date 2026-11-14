/* The AI assist's prompt configuration: what the model is asked to extract.
 * Shared by the page (app.js) and the extraction test (scripts/eval_assist.js),
 * so the test scores exactly the prompt visitors get. */
(function (g) {
  "use strict";
  var ASSIST_CONFIG = {
    title: "Fill from my notes.",
    lede: "Paste whatever you have: a dashboard export, an experiment doc, a Slack thread. The model only fills the form; every value shows the phrase it came from, and you choose what to keep.",
    placeholder: "e.g. Checkout test, day 9. Control: 18,204 sessions, 731 orders. New button: 18,110 sessions, 802 orders. We peek at it every morning. Avg order is about $62.",
    examples: [
      { label: "Slack thread", text: "Quick update on the pricing page test (started Monday 2 weeks ago, 50/50 split). Control: 18,204 visitors, 731 signups. Variant with annual toggle: 18,110 visitors, 802 signups. I've been checking the dashboard every morning. Each signup is worth roughly $62 to us. We'd only bother shipping for a lift of 5% or more." },
      { label: "Dashboard export", text: "Experiment: onboarding_v2 | Allocation 50% / 50% | Runtime: 9 days\nVariant | Users | Converted | CVR\ncontrol | 24,511 | 3,186 | 13.00%\ntreatment | 24,880 | 3,383 | 13.60%" }
    ],
    instructions: "The calculator compares two versions of a page or product: A (the original or control) and B (the new version). Extract visitors and conversions for each. If the text gives a conversion rate and a visitor count but no conversion count, compute conversions = round(rate x visitors) and quote the rate. If there are more than two versions, use the control as A and the version the text focuses on as B, and add a question about the others. 'Times checked' is how many times someone looked at results while the test ran (e.g. 'every morning' over 14 days = 14). 'Planned share to B' is a percentage (50 for a 50/50 split). 'Smallest lift' is a relative percentage (e.g. '5% lift' gives 5); if the text gives it in percentage points, convert it to a relative percentage of A's conversion rate.",
    fields: [
      { key: "nA", label: "A visitors", type: "number" },
      { key: "xA", label: "A conversions", type: "number" },
      { key: "nB", label: "B visitors", type: "number" },
      { key: "xB", label: "B conversions", type: "number" },
      { key: "checks", label: "Times checked", type: "number" },
      { key: "days", label: "Days run", type: "number" },
      { key: "share", label: "Planned share to B (%)", type: "number" },
      { key: "mde", label: "Smallest lift worth acting on (% relative)", type: "number" },
      { key: "value", label: "Value of one conversion ($)", type: "number" }
    ]
  };
  if (typeof module !== "undefined" && module.exports) module.exports = ASSIST_CONFIG;
  g.ASSIST_CONFIG = ASSIST_CONFIG;
})(typeof window !== "undefined" ? window : globalThis);
