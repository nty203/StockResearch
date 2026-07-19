---
name: project-status
description: 프로젝트 아키텍처, 현재 진행 상태, 파일 구조, 남은 작업 등 컨텍스트를 확인합니다.
---

# StockResearch 프로젝트 컨텍스트

이 문서는 프로젝트의 전체적인 아키텍처와 현재 진행 상태, 파일 구조를 담고 있습니다. 프로젝트의 전반적인 상황을 파악하거나 다음 할 일을 확인할 때 참조하세요.

## 프로젝트 개요 및 아키텍처
- 10배 상승주 조기 발굴 시스템. KOSPI/KOSDAQ/S&P1500 대상 정량 스크리닝 + 정성 분석 대시보드.
- `apps/web/` → Cloudflare Pages (Next.js 14, edge runtime)
- `apps/collector/` → GitHub Actions 크론 (Python 데이터 수집)
- Supabase Postgres (DB + Storage)

## 현재 진행 상태 (Phase 0~4 완료)
- 저장소 부트스트랩, 파이프라인, 정량 스크리닝, 시그널 탐지, 에이전트 큐 구성 완료
- Cloudflare Pages 빌드 성공 및 GitHub Actions 정상 동작 확인
- CF API 토큰, GitHub PAT, Supabase 기본 환경변수 설정 완료

## 미완료 설정 및 다음 작업 순서
1. **(수동) 환경/API 설정 마무리**: DART API Key (`DART_API_KEY`), Telegram Bot Token/Chat ID, Supabase Storage `analysis-prompts` 버킷 생성, 마이그레이션 확인 (`001_init.sql`), `.github/workflows/cf-build-test.yml` 파일 삭제
2. **Phase 5**: Next.js 대시보드 UI 폴리싱
3. **Phase 6-8**: 알림, 백테스트, 문서 작업

## 파일 구조 요약
- `apps/web/`: Next.js 대시보드 (CF Pages)
- `apps/collector/`: Python 수집/분석. `src/hundredx/` 하위에 코어 스캐너 및 시그널 추출 엔진 위치.
- `packages/shared/`: TypeScript 공유 타입
- `.github/workflows/`: 수집 주기별 크론 워크플로우 5개
