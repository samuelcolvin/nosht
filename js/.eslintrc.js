module.exports = {
  root: true,
  parser: 'babel-eslint',
  parserOptions: {
    sourceType: 'module',
    ecmaFeatures: {
      'jsx': true
    },
  },
  globals: {
    enz: true,
    xhr_calls: true,
  },
  plugins: [
    'react'
  ],
  extends: 'react-app',
  rules: {
    'semi': [2, 'never'],
    // allow paren-less arrow functions
    'arrow-parens': 0,
    // allow async-await
    'generator-star-spacing': 2,
    // allow debugger during development
    'no-debugger': 2,
    'comma-danglcd e': 0,
    'camelcase': 0,
    'no-alert': 2,
    'space-before-function-paren': 2,
    'react/jsx-uses-react': 2,
    'react/jsx-uses-vars': 2,
  }
}
