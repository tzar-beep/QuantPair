import { dirname } from "path";
import { fileURLToPath } from "url";
import { FlatCompat } from "@eslint/eslintrc";

const __dirname = dirname(fileURLToPath(import.meta.url));
const compat = new FlatCompat({ baseDirectory: __dirname });

export default [
  ...compat.extends("next/core-web-vitals", "next/typescript"),
  { ignores: ["node_modules/**", ".next/**", "components/charts/**", "components/ui/**"] },
  { rules: { "@typescript-eslint/no-explicit-any": "off", "react-hooks/exhaustive-deps": "off" } },
];
