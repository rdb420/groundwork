import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

// Design system adherence, translated from design-system/_adherence.oxlintrc.json: colours, sizes
// and fonts come from design-system tokens, not literals in components.
const TOKENS = [
  { selector: "Literal[value=/#[0-9a-fA-F]{3,8}\\b/]", message: "Raw hex colour. Use a design-system colour token via var()." },
  { selector: "TemplateElement[value.raw=/#[0-9a-fA-F]{3,8}\\b/]", message: "Raw hex colour. Use a design-system colour token via var()." },
  { selector: "Literal[value=/\\b\\d+px\\b/]", message: "Raw px value. Use a design-system token via var(), or a class in styles.css." },
  { selector: "Literal[value=/font-family\\s*:\\s*(?!['\\\"]?(?:Atkinson Hyperlegible|Montserrat))/i]", message: "Font not provided by the design system. Available: Atkinson Hyperlegible, Montserrat." },
];
// Outside src/ui, controls come from the component layer so every one carries the design system's classes.
const CONTROLS = [
  { selector: "JSXOpeningElement[name.name=/^(button|select|textarea|table|label)$/]", message: "Use the matching component from src/ui (Button, Select, Field, Check, Table…)." },
  { selector: "JSXOpeningElement[name.name='input']:not(:has(JSXAttribute[name.name='type'][value.value=/^(checkbox|file)$/]))", message: "Use Input or Field from src/ui." },
];

export default tseslint.config(
  { ignores: ["dist"] },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: { ecmaVersion: 2022, globals: globals.browser },
    plugins: { "react-hooks": reactHooks },
    rules: {
      "react-hooks/rules-of-hooks": "error",
      // Effects here deliberately read the latest canvas through refs; the dependency lists are chosen.
      "react-hooks/exhaustive-deps": "off",
      // Canvas node data is free-form JSON from React Flow and the server.
      "@typescript-eslint/no-explicit-any": "off",
      "@typescript-eslint/no-unused-vars": ["error", { argsIgnorePattern: "^_", varsIgnorePattern: "^_", destructuredArrayIgnorePattern: "^_" }],
      "no-restricted-syntax": ["error", ...TOKENS, ...CONTROLS],
      "no-restricted-imports": ["error", { patterns: [{ group: ["**/design-system/components/**"], message: "The design system's .jsx files are a reference. Import from src/ui." }] }],
    },
  },
  {
    files: ["src/ui/**/*.{ts,tsx}"],
    rules: { "no-restricted-syntax": ["error", ...TOKENS] },
  },
);
