import nextPlugin from 'eslint-config-next'
import prettierConfig from 'eslint-config-prettier'

export default [
  ...nextPlugin,
  prettierConfig,
  {
    rules: {
      'react/no-unescaped-entities': 'off',
      '@next/next/no-page-custom-font': 'off',
      // eslint-plugin-react-hooks v7 (pulled in by eslint-config-next 16, upgraded
      // to fix CVE-flagged transitive deps) added these two new rules. They flag
      // pre-existing patterns here (hydrate-from-storage-on-mount effects, and an
      // async SSE callback referencing a useCallback defined later in the same
      // component) that are safe in practice. Downgraded to warn rather than
      // rewritten, since useChat.ts's SSE handling is delicate — see CLAUDE.md's
      // "Bugs that bit us" history — and this dependency bump is about CVEs, not
      // a hook refactor.
      'react-hooks/set-state-in-effect': 'warn',
      'react-hooks/immutability': 'warn',
    },
  },
]
