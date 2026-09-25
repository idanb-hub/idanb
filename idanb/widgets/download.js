/** @import { AnyWidget } from "@anywidget/types" */

import { subscriber } from "./_utils.js";

/**
 * @typedef Traits
 * @property {string} label
 * @property {string} path
 * @property {string | null} download
 * @property {string} _baseurl
 */

/**
 * @param {string} name
 * @returns {string | undefined}
 */
function getCookie(name) {
  for (const cookie of document.cookie.split(";")) {
    const [key, ...value] = cookie.split("=");
    if (key?.trim() === name) {
      return value.join("=");
    }
  }
  return undefined;
}

/**
 * @param {string} path
 * @param {string} baseurl
 * @returns {string}
 */
function getDownloadURL(path, baseurl) {
  const base = new URL(baseurl, window.location.origin);
  const url = new URL(`files/${path}`, base);

  const xsrf = getCookie("_xsrf");
  if (xsrf) {
    url.searchParams.append("_xsrf", xsrf);
  } else {
    console.warn("Can't get XSRF cookie");
  }

  return url.toString();
}

/** @type { AnyWidget<Traits> } */
export default {
  render({ model, el }) {
    const [sub, unsub] = subscriber(model);

    const anchor = document.createElement("a");
    anchor.textContent = model.get("label");
    anchor.href = getDownloadURL(model.get("path"), model.get("_baseurl"));
    anchor.target = "_blank";
    const download = model.get("download");
    if (download !== null) {
      anchor.download = download;
    }

    sub("change:path", () => {
      anchor.href = getDownloadURL(model.get("path"), model.get("_baseurl"));
    });
    sub("change:_baseurl", () => {
      anchor.href = getDownloadURL(model.get("path"), model.get("_baseurl"));
    });
    sub("change:label", () => {
      anchor.textContent = model.get("label");
    });
    sub("change:download", () => {
      const download = model.get("download");
      if (download === null) {
        anchor.removeAttribute("download");
      } else {
        anchor.download = download;
      }
    });

    el.append(anchor);

    return unsub;
  },
};
