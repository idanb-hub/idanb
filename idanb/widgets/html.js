/** @import { AnyWidget } from "@anywidget/types" */

import { subscriber } from "./_utils.js";

/**
 * @typedef Traits
 * @property {string} html
 */

/** @type { AnyWidget<Traits> } */
export default {
  render({ model, el }) {
    const [sub, unsub] = subscriber(model);

    sub("change:html", () => {
      el.innerHTML = model.get("html");
    });

    el.innerHTML = model.get("html");

    return unsub;
  },
};
