// Download PDF: the browser's own print-to-PDF with the print layout in style.css. The answer
// never goes back to the server, so nothing about it is sent or stored. Before printing, the SQL
// is expanded (the PDF shows how every number was found) and the page title becomes the
// question, which browsers use as the PDF's file name.
document.addEventListener("click", (event) => {
  const button = event.target.closest("[data-pdf]");
  if (!button) return;
  const answer = button.closest("article");
  answer.querySelectorAll("details").forEach((d) => { d.open = true; });
  const title = document.title;
  document.title = button.dataset.title || title;
  window.addEventListener("afterprint", () => { document.title = title; }, { once: true });
  window.print();
});

// Rate limited: turn Ask off, count down from the server's Retry-After, then turn it back on.
// The server enforces the limit regardless; this just makes the wait visible.
let coolingUntil = 0;
let timer = null;

function cooldown(seconds, notice) {
  coolingUntil = Date.now() + seconds * 1000;
  const buttons = document.querySelectorAll(".ask button, .examples button");
  const tick = () => {
    const left = Math.max(0, Math.ceil((coolingUntil - Date.now()) / 1000));
    buttons.forEach((b) => { b.disabled = left > 0; });
    notice.textContent = left > 0
      ? `That's a lot of questions in a short time. You can ask again in ${left} s.`
      : "You can ask again now.";
    if (left > 0) timer = setTimeout(tick, 1000);
  };
  clearTimeout(timer);
  setTimeout(tick, 0);  // after htmx re-enables the button it disabled during the request
}

document.addEventListener("htmx:afterSettle", (event) => {
  const notice = event.detail.target.querySelector("[data-retry-after]");
  if (notice) cooldown(parseInt(notice.dataset.retryAfter, 10) || 30, notice);
});

document.addEventListener("htmx:beforeRequest", (event) => {
  if (Date.now() < coolingUntil) event.preventDefault();  // still waiting: don't send
});

// Server errors and lost connections: htmx shows nothing by default, so say what happened.
function failed(message) {
  const answer = document.getElementById("answer");
  if (!answer) return;
  const p = document.createElement("p");
  p.className = "notice error";
  p.setAttribute("role", "alert");
  p.textContent = message;
  answer.replaceChildren(p);
}
document.addEventListener("htmx:sendError", () => failed("Couldn't reach the server. Check your connection and try again."));
document.addEventListener("htmx:responseError", () => failed("Something went wrong on our side. Please try again in a moment."));

// The question box grows with the question (up to the CSS max-height). Enter asks; Shift+Enter
// starts a new line.
const question = document.getElementById("question");
if (question) {
  const grow = () => { question.style.height = "auto"; question.style.height = `${question.scrollHeight + 2}px`; };
  question.addEventListener("input", grow);
  question.addEventListener("keydown", (event) => {
    if (event.key !== "Enter" || event.shiftKey || event.isComposing) return;
    event.preventDefault();
    question.form.requestSubmit();
  });
}

// Once there's an answer, the page steps back: the intro and examples fold away (style.css), the
// box invites the next question, and the answer scrolls into view.
document.addEventListener("htmx:afterSettle", (event) => {
  if (event.detail.target.id !== "answer" || !event.detail.target.querySelector("article")) return;
  document.body.classList.add("has-answer");
  if (question) question.placeholder = "Ask another question…";
  const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  event.detail.target.scrollIntoView({ behavior: still ? "auto" : "smooth", block: "start" });
});
