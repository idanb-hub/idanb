/** @import { AnyModel } from "@anywidget/types" */

/**
 * Throw an `Error`.
 * @param {string} message
 * @returns {never}
 */
export function error(message = "") {
  throw Error(message);
}

/**
 * @template {Record<string, unknown>} Traits
 * @template {AnyModel<Traits>} Model
 * @param {Model} model
 * @returns {[Model["on"], () => void]}
 */
export function subscriber(model) {
  /** @type {Array<() => void>} */
  const cleanup = [];

  /**
   * @template {string} Event
   * @param {Event} event
   * @param {Parameters<Model["on"]>[1]} callback
   */
  function sub(event, callback) {
    model.on(event, callback);
    cleanup.push(() => {
      model.off(event, callback);
    });
  }

  function unsub() {
    cleanup.forEach((f) => {
      f();
    });
  }

  return [sub, unsub];
}

/**
 * Create a new `Promise` from `executor` that also rejects when `signal` aborts.
 * @template T
 * @param {AbortSignal?} signal
 * @param {(resolve: (value: T) => void, reject: (reason: Error) => void) => void} executor
 * @returns {Promise<T>}
 */
export function Task(signal, executor) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted === true) {
      // eslint-disable-next-line @typescript-eslint/prefer-promise-reject-errors
      reject(signal.reason);
    }
    /** @this {AbortSignal} */
    function onAbort() {
      // eslint-disable-next-line @typescript-eslint/prefer-promise-reject-errors
      reject(this.reason);
    }
    signal?.addEventListener("abort", onAbort, { once: true });
    executor(
      (value) => {
        signal?.removeEventListener("abort", onAbort);
        resolve(value);
      },
      (reason) => {
        signal?.removeEventListener("abort", onAbort);
        reject(reason);
      },
    );
  });
}
