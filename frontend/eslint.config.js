import js from '@eslint/js'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import globals from 'globals'

export default [
  { ignores: ['dist', '.vite'] },
  {
    files: ['**/*.{js,jsx}'],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
      parserOptions: {
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    plugins: {
      'react-hooks': reactHooks,
      'react-refresh': reactRefresh,
    },
    rules: {
      ...js.configs.recommended.rules,
      // eslint-plugin-react-hooks v7의 recommended에는 React Compiler를 염두에 둔
      // set-state-in-effect 같은 새 규칙이 포함되어 있는데, 이 프로젝트 전반에서 쓰는
      // "마운트 시 fetch로 목록 불러오기"(useEffect(() => load(), [])) 패턴을 전부
      // 오탐으로 잡아낸다 — React Compiler를 쓰지 않는 이 프로젝트엔 안 맞아서, 안정적인
      // 두 규칙(rules-of-hooks/exhaustive-deps)만 선택적으로 켠다.
      'react-hooks/rules-of-hooks': 'error',
      'react-hooks/exhaustive-deps': 'warn',
      'react-refresh/only-export-components': ['warn', { allowConstantExport: true }],
      'no-unused-vars': ['warn', { varsIgnorePattern: '^[A-Z_]' }],
    },
  },
]
