import js from '@eslint/js';
import globals from 'globals';

const config = [
  { ignores: ['.next/**', 'node_modules/**'] },
  {
    files: ['**/*.{js,mjs}'],
    languageOptions: {
      ecmaVersion: 'latest',
      sourceType: 'module',
      parserOptions: { ecmaFeatures: { jsx: true } },
      globals: { ...globals.browser, ...globals.node },
    },
    rules: js.configs.recommended.rules,
  },
];

export default config;
