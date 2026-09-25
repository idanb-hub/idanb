/** @import { AnyModel, AnyWidget } from "@anywidget/types" */
/** @import { HTMLPerspectiveViewerElement, HTMLPerspectiveViewerPluginElement } from "@perspective-dev/viewer" */
/** @import { HTMLPerspectiveViewerDatagridPluginElement } from "@perspective-dev/viewer-datagrid" */
/** @import { RegularTableElement } from "regular-table" */

/**
 * Not exported from `@anywidget/types`.
 * @typedef {Exclude<AnyWidget, () => any>} WidgetDef
 */

/**
 * @typedef Traits
 * @property {string} _perspective_widget_esm
 * @property {Record<string, string>} styles
 * @property {{[colname: string]: string}} templates
 */

/**
 * Get `PerspectiveWidget` frontend widget definition.
 * @param {AnyModel<Traits>} model
 * @returns {Promise<WidgetDef>}
 */
async function getPerspectiveWidget(model) {
  const url = model.get("_perspective_widget_esm");
  /** @type {{ default: AnyWidget }} */
  const mod = await import(url);
  let widget = mod.default;
  return typeof widget === "function" ? await widget() : widget;
}

/**
 * Apply custom CSS styles to viewer's plugins.
 * @param {HTMLPerspectiveViewerElement} viewer
 * @param {Traits["styles"]} styles
 */
function applyStyles(viewer, styles) {
  for (const [name, style] of Object.entries(styles)) {
    /** @type {HTMLPerspectiveViewerPluginElement | null} */
    let plugin = null;

    try {
      plugin = viewer.getPlugin(name);
    } catch {} // eslint-disable-line no-empty

    if (plugin == null) {
      console.warn("Cannot apply custom style for '%s' plugin.", plugin);
      continue;
    }

    const sheet = new CSSStyleSheet();
    if (plugin.shadowRoot != null) {
      sheet.replaceSync(style);
      plugin.shadowRoot.adoptedStyleSheets.push(sheet);
    } else {
      // Add sheet globally, but scope its rules to the `plugin` element.
      const id = Math.random().toString(36).replace(/^0\./, "_");
      plugin.classList.add(id);
      sheet.replaceSync(`@scope (${plugin.tagName}.${id}) { ${style} }`);
      document.adoptedStyleSheets.push(sheet);
    }
  }
}

/**
 * Allow selecting text inside datagrid table.
 * @param {HTMLPerspectiveViewerDatagridPluginElement} datagrid
 */
function makeTableDataSelectable(datagrid) {
  const sheet = new CSSStyleSheet();
  sheet.replaceSync(`
    td {
      user-select: text !important;
    }
  `);
  datagrid.shadowRoot?.adoptedStyleSheets.push(sheet);

  // Select entire cell contents on double click.
  datagrid.regular_table.addEventListener("mousedown", (e) => {
    if (e.detail !== 2) {
      // Not double click.
      return;
    }

    if (!(e.target instanceof Node)) {
      return;
    }

    const selection = window.getSelection();
    if (selection === null) {
      return;
    }

    const range = document.createRange();
    range.selectNodeContents(e.target);
    selection.removeAllRanges();
    selection.addRange(range);

    e.preventDefault();
  });
}

/**
 * Apply data rendering templates to `<regular-table>`.
 * @param {RegularTableElement} table
 * @param {Traits["templates"]} templates
 */
function applyTemplates(table, templates) {
  const renderers = Object.fromEntries(
    // prettier-ignore
    Object.entries(templates).map(([key, value]) => [
      key,
      /** @type {((value: unknown) => string) | undefined} */
      // eslint-disable-next-line @typescript-eslint/no-implied-eval
      (new Function("$", `return \`${value}\``)),
    ]),
  );

  table.addStyleListener(() => {
    for (const td of table.querySelectorAll("td")) {
      const meta = table.getMeta(td);
      if (meta?.type !== "body") {
        continue;
      }

      const [column] = meta.column_header;
      if (typeof column !== "string") {
        continue;
      }

      // Can be target of attribute selectors in CSS.
      td.dataset["column"] = column;

      const render = renderers[column];
      if (render !== undefined) {
        td.innerHTML = render(meta.value);
        td.title = td.innerText;
      } else {
        td.title = meta.value?.toString() ?? "";
      }
    }
  });
}

/** @type { AnyWidget<Traits> } */
export default {
  async initialize(props) {
    const { model } = props;
    const widget = await getPerspectiveWidget(model);
    return await widget.initialize?.(props);
  },
  async render(props) {
    const { model, el } = props;
    const widget = await getPerspectiveWidget(model);
    const cleanup = await widget.render?.(props);

    /** @type{HTMLPerspectiveViewerElement?} */
    const viewer = el.querySelector("perspective-viewer");
    if (viewer === null) {
      throw Error("`perspective-viewer` element not found.");
    }

    applyStyles(viewer, model.get("styles"));
    /** @type {HTMLPerspectiveViewerDatagridPluginElement} */
    const datagrid = viewer.getPlugin("datagrid");
    makeTableDataSelectable(datagrid);
    applyTemplates(datagrid.regular_table, model.get("templates"));

    return cleanup;
  },
};
