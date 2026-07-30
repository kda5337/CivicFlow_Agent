import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    // 기본값은 IPv6(::1)에만 바인딩되어, 브라우저가 localhost를 IPv4(127.0.0.1)로
    // 먼저 풀면 접속이 거부될 수 있다 — 0.0.0.0(모든 IPv4 인터페이스)에도 명시적으로 붙인다.
    host: true,
  },
})
