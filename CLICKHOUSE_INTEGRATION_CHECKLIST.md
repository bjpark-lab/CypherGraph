# ClickHouse 통합 체크리스트

이 문서는 `feat/clickhouse-foundation` 브랜치에서 추가한 ClickHouse 통합 기능을
실제로 연결·검증할 때 사용할 체크리스트, 실행 명령어, 테스트 질문 세트를 정리한 문서다.

---

## 1. 현재 반영된 범위

### 완료된 작업
- ClickHouse 설정값 추가 (`CLICKHOUSE_URI`, `CLICKHOUSE_USER` 등)
- ClickHouse 연결 서비스 추가
- ClickHouse SQL guard 추가
- 헬스체크에 ClickHouse 연결 상태 추가
- ClickHouse schema 조회 tool 추가
- ClickHouse query tool 추가
- coordinator에 Neo4j / ClickHouse 라우팅 규칙 추가
- 채팅 응답 구조에 `analytics`, `sql`, `sources` 필드 추가

### 아직 검증이 필요한 항목
- 실제 ClickHouse URI로 연결되는지
- 실제 스키마를 tool이 제대로 읽는지
- 자연어 질문이 ClickHouse로 잘 라우팅되는지
- 혼합형 질문에서 Neo4j + ClickHouse를 순차 사용 가능한지

---

## 2. 환경 설정 체크리스트

### `.env` 설정
- [ ] `backend/.env`에 ClickHouse 접속 정보 입력
- [ ] `CLICKHOUSE_DATABASE`가 실제 DB와 일치하는지 확인
- [ ] `SQL_MODEL`, `SQL_API_KEY`, `SQL_BASE_URL` 확인
- [ ] 기존 `NEO4J_*`, `COORDINATOR_*`, `CYPHER_*`, `ANSWER_*` 설정 유지 확인

### 예시
```env
CLICKHOUSE_URI=https://username:password@clickhouse-host:8443/default
CLICKHOUSE_USER=default
CLICKHOUSE_PASSWORD=your_clickhouse_password_here
CLICKHOUSE_DATABASE=default
CLICKHOUSE_SECURE=true
CLICKHOUSE_TIMEOUT=10
CLICKHOUSE_MAX_ROWS=1000

SQL_MODEL=minimax/minimax-m2.5:free
SQL_API_KEY=your_openrouter_api_key_here
SQL_BASE_URL=https://openrouter.ai/api/v1
```

---

## 3. 실행 명령어 세트

### 3-1. 의존성 설치
```bash
cd /home/bjpark/projects/cypher-graph/backend
uv sync
```

### 3-2. 백엔드 실행
```bash
cd /home/bjpark/projects/cypher-graph/backend
uv run fastapi dev app/main.py
```

### 3-3. 헬스체크 확인
```bash
curl -s http://localhost:8000/api/health | jq
```

기대 결과 예시:
```json
{
  "status": "ok",
  "neo4j_connected": true,
  "clickhouse_connected": true,
  "version": "1.0.0"
}
```

### 3-4. API 문서 확인
```bash
xdg-open http://localhost:8000/docs
```

---

## 4. ClickHouse 연결/스키마 확인 절차

### 목표
- ClickHouse 접속이 실제로 되는지 확인
- 어떤 테이블/컬럼이 있는지 파악
- SQL 생성 품질에 필요한 핵심 컬럼명을 정리

### 확인할 핵심 컬럼
- [ ] 메인 fact table 이름
- [ ] 시간 컬럼 이름 (`event_time`, `measured_at`, `created_at` 등)
- [ ] wafer 식별 컬럼
- [ ] lot 식별 컬럼
- [ ] chamber 식별 컬럼
- [ ] parameter / metric 식별 컬럼
- [ ] 측정값(value) 컬럼

### 추천 조사 방식
1. 백엔드 실행
2. 채팅 API 또는 프론트에서 schema 관련 질문
3. `clickhouse_schema_tool` 결과 확인
4. 테이블 구조를 문서화

---

## 5. 테스트 질문 세트

### A. ClickHouse 단독 테스트 질문
집계 / 분포 / 추세 / 기간 필터 질문은 ClickHouse로 가야 한다.

1. 최근 7일간 chamber별 평균 측정값을 보여줘
2. 최근 30일간 parameter별 평균과 표준편차 상위 10개를 보여줘
3. lot별 측정 건수 상위 20개를 보여줘
4. wafer별 특정 parameter의 평균값을 비교해줘
5. 최근 일주일간 step별 측정값 추이를 보여줘
6. 이상치가 많은 chamber 순으로 정리해줘
7. 특정 parameter의 분포를 요약해줘
8. 최근 3일간 lot별 최대값/최소값/평균값을 보여줘

### B. Neo4j 단독 테스트 질문
관계 / 연결 / 경로 / 공정 흐름 질문은 Neo4j로 가야 한다.

1. wafer A가 어떤 recipe step을 거쳤는지 보여줘
2. 이 wafer와 연결된 metrology 노드를 찾아줘
3. 특정 chamber와 연결된 wafer 흐름을 보여줘
4. 이 lot에 속한 wafer들이 어떤 공정 관계를 가지는지 설명해줘
5. 특정 이상치 wafer와 연결된 upstream step을 찾아줘

### C. 혼합형 테스트 질문
관계 + 집계가 동시에 필요하므로 Neo4j와 ClickHouse를 순차 사용하는지 본다.

1. 이상치 wafer들의 공정 경로와 parameter 분포를 같이 보여줘
2. 특정 chamber와 연결된 wafer들을 찾고, 그 wafer들의 최근 측정 평균을 비교해줘
3. lot A의 wafer 관계를 보고, 동시에 step별 측정 추이도 요약해줘
4. 문제 step과 연결된 wafer들을 찾고 각 wafer의 통계값을 비교해줘

---

## 6. 테스트 시 기대하는 동작

### ClickHouse 질문
- [ ] `clickhouse_query_tool`이 호출된다
- [ ] 생성된 SQL이 `SELECT` 또는 `WITH ... SELECT`다
- [ ] `LIMIT`이 포함된다
- [ ] 응답의 `sources`에 `clickhouse`가 담긴다
- [ ] `tool_results.table` 또는 `tool_results.analytics`에 결과가 들어간다

### Neo4j 질문
- [ ] `graph_cypher_qa_tool`이 호출된다
- [ ] 응답의 `sources`에 `neo4j`가 담긴다
- [ ] graph/table 결과가 유지된다

### 혼합 질문
- [ ] 필요 시 schema tool을 먼저 부를 수 있다
- [ ] Neo4j → ClickHouse 순서 또는 그 반대 순서로 tool이 2회 이상 호출된다
- [ ] 최종 응답이 두 결과를 종합한다

---

## 7. 실패 시 점검 포인트

### ClickHouse 연결 실패
- [ ] URI 스킴이 `http`/`https` 중 맞는지
- [ ] 포트가 8123/8443 중 맞는지
- [ ] username/password가 맞는지
- [ ] 외부 서버 방화벽이 열려 있는지
- [ ] 해당 서버가 HTTP 인터페이스를 허용하는지

### SQL 생성 품질이 나쁠 때
- [ ] 실제 테이블/컬럼명이 prompt에 충분히 노출되는지
- [ ] `clickhouse_schema_tool` 결과가 너무 장황하거나 너무 빈약하지 않은지
- [ ] time/value/wafer/chamber/lot 관련 컬럼명을 프롬프트에 더 명확히 넣어야 하는지

### 라우팅이 어긋날 때
- [ ] coordinator prompt의 라우팅 규칙 보강 필요
- [ ] keyword 기반 pre-router 추가 검토
- [ ] 혼합 질문은 1차엔 지나친 자동화보다 순차 호출에 집중

---

## 8. 추천 실행 순서

1. [ ] `.env`에 ClickHouse 설정 입력
2. [ ] `uv sync`
3. [ ] 백엔드 실행
4. [ ] `/api/health` 확인
5. [ ] schema 조회 질문으로 ClickHouse 구조 확인
6. [ ] ClickHouse 단독 질문 2~3개 테스트
7. [ ] Neo4j 회귀 테스트
8. [ ] 혼합 질문 테스트
9. [ ] 로그 확인 후 prompt / router 튜닝 포인트 정리

---

## 9. 다음 단계 후보

실제 테스트 후 다음 개선을 고려한다.

- ClickHouse schema 요약 형식 개선
- SQL prompt few-shot 예시 추가
- coordinator pre-router(rule-based) 추가
- ClickHouse를 optional health source로 처리할지 검토
- 혼합형 질문의 결과 결합 포맷 개선
