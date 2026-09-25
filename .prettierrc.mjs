/** @type {import("prettier").Config} */
export default {
  overrides: [
    {
      files: "tsconfig.json",
      options: { parser: "jsonc" },
    },
  ],
};
