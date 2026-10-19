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
