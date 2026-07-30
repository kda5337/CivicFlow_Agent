// 로컬 개발: 백엔드가 localhost:8000에 따로 떠 있으므로 절대주소를 기본값으로 쓴다.
// 배포 빌드: Dockerfile.frontend가 VITE_API_BASE_URL=""로 빌드해 상대경로가 되고,
// nginx가 같은 origin에서 /inquiries 등을 백엔드 컨테이너로 프록시한다.
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'
