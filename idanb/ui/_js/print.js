/// <reference path="print.d.ts" />

// Neither `@media print` CSS rules nor `beforeprint` JS events work because
// page layout doesn't update before being captured for printing.

const sheet = new CSSStyleSheet();
// eslint-disable-next-line no-undef
sheet.replaceSync(css);

// Apply styles for print.
const sheets = document.adoptedStyleSheets;
sheets.push(sheet);

// Recompute layout after ^ modifies page dimensions.
window.dispatchEvent(new Event("resize"));
for (const frame of document.querySelectorAll("iframe")) {
  frame.contentWindow?.dispatchEvent(new Event("resize"));
}

// It takes a bit for the layout to update.
setTimeout(() => {
  print();
  // Restore layout and style.
  sheets.splice(sheets.indexOf(sheet));
  window.dispatchEvent(new Event("resize"));
}, 100);
