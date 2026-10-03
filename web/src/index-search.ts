// Client-side filter box for the members and entities index pages (progressive enhancement).
//
// The pages ship the full table and a hidden filter box: <div class="filter"
// data-filter-for="<table id>" hidden>. Without JavaScript the box stays hidden and the table
// is complete. With it, this module shows the box and hides the rows whose text does not
// contain every word typed (case and accents ignored). No network requests.

function fold(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

function setup(box: HTMLElement): void {
  const table = document.getElementById(box.dataset.filterFor ?? "");
  const input = box.querySelector<HTMLInputElement>("input[type=search]");
  const count = box.querySelector<HTMLElement>("[data-filter-count]");
  if (!(table instanceof HTMLTableElement) || !input) return;
  const rows = Array.from(table.tBodies[0]?.rows ?? []);
  const texts = rows.map((r) => fold(r.textContent ?? ""));
  const total = rows.length;

  const apply = (): void => {
    const words = fold(input.value).split(/\s+/).filter(Boolean);
    let shown = 0;
    rows.forEach((row, i) => {
      const hit = words.every((w) => texts[i].includes(w));
      row.hidden = !hit;
      if (hit) shown += 1;
    });
    if (count) {
      count.textContent = words.length
        ? `${shown.toLocaleString("en-AU")} of ${total.toLocaleString("en-AU")} rows match`
        : "";
    }
    table.dataset.shown = String(shown);
  };

  input.addEventListener("input", apply);
  box.hidden = false;
  if (input.value) apply();
}

document.querySelectorAll<HTMLElement>("[data-filter-for]").forEach(setup);
