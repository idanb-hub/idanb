import { subscriber } from "./_utils.js";

/** @import { AnyWidget } from "@anywidget/types" */

/**
 * @typedef Traits
 * @property {boolean} html
 * @property {string} _snapshot
 */

/** @type {AnyWidget<Traits>} */
export default {
  render({ model, el }) {
    const [sub, unsub] = subscriber(model);

    // Render and append new content as it comes in.
    sub("msg:custom", (text) => {
      if (typeof text !== "string") {
        return;
      }

      if (model.get("html")) {
        el.insertAdjacentHTML("beforeend", text);
      } else {
        el.insertAdjacentText("beforeend", text);
      }
    });

    // Re-render all contents when snapshot updates.
    sub("change:_snapshot", () => {
      const snapshot = model.get("_snapshot");
      if (model.get("html")) {
        el.innerHTML = snapshot;
      } else {
        el.textContent = snapshot;
      }
    });

    // Request a new snapshot to get contents added before this render.
    model.send("sync");

    // In the meantime, render the latest snapshot.
    const snapshot = model.get("_snapshot");
    if (model.get("html")) {
      el.innerHTML = snapshot;
    } else {
      el.textContent = snapshot;
    }

    return () => {
      unsub();
    };
  },
};
