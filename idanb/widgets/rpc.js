/** @import { AnyModel, AnyWidget } from "@anywidget/types" */

/**
 * @typedef Pack
 * @property {string} type
 * @property {unknown} value
 */

/**
 * @param {AnyModel} model
 * @param {Pack} pack
 * @returns {unknown}
 */
function unpack(model, { type, value }) {
  switch (type) {
    case "function":
      /** @param {unknown[]} params */
      return (...params) => {
        model.send({ func: value, params });
      };
    case "object":
      return value;
    default:
      throw new Error(`unexpected variable type: ${type}`);
  }
}

/** @type { AnyWidget } */
export default {
  initialize({ model }) {
    model.on(
      "msg:custom",
      /** @param {{expr: string, vars: {[name: string]: Pack }}} msg */
      ({ expr, vars }) => {
        const func = /** @type {(...params: unknown[]) => unknown} */ (
          // eslint-disable-next-line @typescript-eslint/no-implied-eval
          new Function(...Object.keys(vars), expr)
        );
        const params = Object.values(vars).map((pack) => unpack(model, pack));
        func(...params);
      },
    );
  },
};
