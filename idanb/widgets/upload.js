/** @import { AnyModel, AnyWidget } from "@anywidget/types" */

import { Task, subscriber } from "./_utils.js";

/**
 * @typedef Traits
 * @property {number} chunk_size
 */

/**
 * @param {Blob} blob
 * @param {AbortSignal?} signal
 * @returns {Promise<ArrayBuffer>}
 */
async function readBlobAsync(blob, signal = null) {
  const reader = new FileReader();
  /** @type {Promise<ArrayBuffer>} */
  const promise = Task(signal, (resolve, reject) => {
    reader.onload = () => {
      resolve(/** @type{ArrayBuffer} */ (reader.result));
    };
    reader.onerror = () => {
      reject(/** @type{Error} */ (reader.error));
    };
  });
  reader.readAsArrayBuffer(blob);
  try {
    return await promise;
  } catch (e) {
    reader.abort();
    throw e;
  }
}

/**
 * @param {AnyModel<Traits>} model
 * @param {File} file
 * @param {AbortSignal?} signal
 */
async function uploadFile(model, file, signal = null) {
  console.log("uploadFile", file);
  const chunkSize = model.get("chunk_size");

  for (let start = 0, end = 0; end < file.size; start = end) {
    // Read next chunk.
    end = Math.min(start + chunkSize, file.size);
    const chunk = file.slice(start, end);
    const data = await readBlobAsync(chunk);

    // Send chunk to the back-end.
    model.send({ path: file.name, size: file.size }, null, [data]);

    // Wait until back-end is ready for the next chunk.
    const [sub, unsub] = subscriber(model);
    try {
      await Task(signal, (resolve, reject) => {
        sub(
          "msg:custom",
          /** @param {{path: string, size: number}} msg */
          ({ path, size }) => {
            if (path !== file.name) {
              return;
            }
            if (size < 0) {
              reject(Error("Upload rejected by server"));
            } else {
              resolve(undefined);
            }
          },
        );
      });
    } finally {
      unsub();
    }
  }

  // Signal EOF by sending without buffers.
  model.send({ path: file.name, size: file.size });
}

/** @type { AnyWidget<Traits> } */
export default {
  render({ model, el }) {
    const input = document.createElement("input");
    input.type = "file";
    input.multiple = true;

    const controller = new AbortController();

    input.addEventListener("change", () => {
      if (input.files === null || input.files.length === 0) {
        return;
      }

      input.disabled = true;

      Promise.all(
        [...input.files].map(async (file) => {
          await uploadFile(model, file, controller.signal);
        }),
      )
        .catch(console.error)
        .finally(() => {
          input.disabled = false;
          input.value = "";
          // Others can listen for when upload finishes.
          input.dispatchEvent(new Event("change", { bubbles: true }));
        });
    });

    el.append(input);

    return () => {
      console.log("destroying widget view");
      controller.abort(
        Error("Widget view was destroyed before upload could finish"),
      );
    };
  },
};
