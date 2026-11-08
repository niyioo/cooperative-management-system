module.exports = {
  root: true,
  env: { browser: true, es2022: true },
  parserOptions: { ecmaVersion: 'latest', sourceType: 'module', ecmaFeatures: { jsx: true } },
  settings: { react: { version: '18.2' } },
  extends: [
    'eslint:recommended',
    'plugin:react/recommended',
    'plugin:react/jsx-runtime',
    'plugin:react-hooks/recommended',
  ],
  plugins: ['react-refresh'],
  ignorePatterns: ['dist', 'node_modules', 'coverage'],
  rules: {
    // Props are documented in component comments; this codebase does not use PropTypes.
    'react/prop-types': 'off',
    // UI copy is prose; apostrophes and quotes in JSX text render correctly.
    'react/no-unescaped-entities': 'off',
    'react-refresh/only-export-components': 'off',
    'no-unused-vars': ['error', { argsIgnorePattern: '^_', varsIgnorePattern: '^_', ignoreRestSiblings: true }],
  },
  overrides: [
    { files: ['*.config.js', '.eslintrc.cjs'], env: { node: true } },
    { files: ['**/*.test.{js,jsx}'], env: { node: true } },
  ],
};
