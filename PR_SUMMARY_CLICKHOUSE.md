# PR Summary - ClickHouse Foundation & Routing

## 제목 후보
feat: add ClickHouse foundation and multi-DB routing

## 요약
이번 변경은 기존 Neo4j 중심 구조에 ClickHouse를 보조 분석 데이터 소스로 추가하기 위한 기반 작업이다.
이제 coordinator는 질문 성격에 따라 Neo4j 또는 ClickHouse를 선택할 수 있는 방향으로 확장되었고,
ClickHouse 연결, SQL 안전장치, schema/query tool, 응답 구조 확장이 포함되었다.

## 주요 변경 사항

### 1. ClickHouse 연결 기반 추가
- `backend/app/core/config.py`
  - ClickHouse 설정 추가
  - `CLICKHOUSE_URI`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`, `CLICKHOUSE_DATABASE`, `CLICKHOUSE_SECURE`, `CLICKHOUSE_TIMEOUT`, `CLICKHOUSE_MAX_ROWS`
- `backend/app/services/clickhouse_service.py`
  - ClickHouse client singleton
  - 연결 확인
  - SQL 실행
  - schema 조회
- `backend/app/services/sql_guard.py`
  - read-only SQL 검증
  - 금지 키워드 차단
  - multi-statement 차단
  - LIMIT 강제
- `backend/app/api/routes/health.py`
  - Neo4j + ClickHouse 상태를 함께 반환하도록 확장

### 2. ClickHouse tool 추가
- `backend/app/llm/tools/clickhouse_schema_tool.py`
  - ClickHouse 테이블/컬럼 구조 조회
- `backend/app/llm/tools/clickhouse_query_tool.py`
  - 자연어 질문 → SQL 생성 → guard 검증 → ClickHouse 실행
- `backend/app/llm/models.py`
  - `get_sql_llm()` 추가
- `backend/app/llm/prompts.py`
  - ClickHouse SQL 생성 프롬프트 추가

### 3. coordinator 라우팅 확장
- coordinator prompt에 DB 선택 규칙 추가
  - 관계/경로/연결 → Neo4j 우선
  - 집계/분포/추세/기간 분석 → ClickHouse 우선
  - 혼합형 질문 → 두 DB 순차 사용 가능
- `backend/app/llm/coordinator_v2.py`
  - ClickHouse tool 결과 파싱 / merge 지원
- `backend/app/llm/coordinator_v3.py`
  - `analytics`, `sql`, `sources` 누적 지원

### 4. 응답 구조 확장
- `backend/app/schemas/chat.py`
  - `ToolResult`에 `analytics`, `sql`, `sources` 추가

### 5. 문서화
- `backend/.env.example`
  - ClickHouse / SQL LLM 설정 예시 추가
- `CLICKHOUSE_INTEGRATION_CHECKLIST.md`
  - 환경 설정, 실행 명령어, 테스트 질문 세트 정리
- `README.md`
  - 멀티 DB 구조 및 ClickHouse 관련 설정 반영

## 의도한 사용 분리
- **Neo4j**: wafer / recipe / step / metrology 간 관계 탐색
- **ClickHouse**: 평균, 분포, 추세, 기간별 변화, 상위 N 집계

## 테스트 포인트
- `/api/health`에서 `clickhouse_connected` 확인
- ClickHouse schema tool이 실제 테이블/컬럼 구조를 읽는지 확인
- ClickHouse query tool이 SELECT only SQL을 생성하는지 확인
- Neo4j 기존 흐름이 깨지지 않는지 회귀 테스트
- 혼합형 질문에서 두 DB를 순차 활용하는지 확인

## 알려진 제한 사항
- 실제 ClickHouse 스키마에 맞춘 prompt 튜닝은 추가로 필요할 수 있음
- 혼합형 질문은 아직 프롬프트 기반 라우팅 비중이 큼
- 필요하면 이후 단계에서 keyword/rule 기반 pre-router 추가 권장

## 브랜치
- `feat/clickhouse-foundation`
