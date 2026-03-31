# Harness Engineering Plan for RCP Cypher

이 문서는 **사용자 질문에 더 안정적으로 만족하는 답변을 생성하도록** 이 프로젝트에 하네스 엔지니어링을 적용할 때,
어떤 부분을 바꾸고 그 변경의 효과를 어떻게 테스트/검증할지 정리한 계획서다.

---

## 1. 목표

현재 프로젝트는 이미 다음 요소를 갖고 있다.

- coordinator 기반 tool 호출 구조
- Neo4j / ClickHouse 분기 가능성
- query guard / sql guard
- streaming event 구조
- schema 기반 질의 생성

하지만 실제 사용자 만족도를 높이려면 다음이 더 중요해진다.

1. **질문 의도를 더 정확히 파악하는가**
2. **적절한 데이터 소스를 고르는가**
3. **너무 많은/너무 적은 데이터를 가져오지 않는가**
4. **답변이 실제 질문에 맞게 요약되는가**
5. **실패 시에도 납득 가능한 fallback을 제공하는가**
6. **위 동작을 반복 가능하게 검증할 수 있는가**

즉, 단순히 프롬프트를 고치는 게 아니라,
**모델이 일하는 실행 환경 전체를 설계하고 측정하는 것**이 목표다.

---

## 2. 변경 대상과 기대 효과

### A. 입력 하네스: 질문 분류/전처리 계층 추가

#### 변경할 부분
- coordinator 앞단에 **pre-router** 추가
- 사용자 질문을 먼저 아래 중 하나로 분류
  - graph_question
  - analytics_question
  - hybrid_question
  - ambiguous_question

#### 구현 위치 후보
- `backend/app/llm/router.py` (신규)
- `backend/app/llm/coordinator_v3.py` 호출 전 단계

#### 기대 효과
- 잘못된 DB 선택 감소
- 불필요한 tool 호출 감소
- 응답 속도 개선
- 혼합 질문 처리 일관성 증가

#### 검증 포인트
- 같은 질문에 대해 tool 선택이 더 안정적으로 반복되는가
- graph 질문이 ClickHouse로 잘못 가는 비율이 줄었는가
- analytics 질문이 Neo4j로 잘못 가는 비율이 줄었는가

---

### B. 스키마 하네스: schema grounding 개선

#### 변경할 부분
- 현재 schema 주입을 더 구조적으로 정리
- Neo4j schema와 ClickHouse schema를 질문별로 선택 주입
- 대형 schema는 축약 요약 + 중요 테이블/컬럼 우선 제공
- domain alias 사전 추가
  - 예: wafer id / wafer_id / wafer / wafer_no
  - metrology / metric / parameter / value

#### 구현 위치 후보
- `backend/app/llm/prompts.py`
- `backend/app/services/neo4j_service.py`
- `backend/app/services/clickhouse_service.py`
- `backend/app/llm/schema_context.py` (신규)

#### 기대 효과
- 존재하지 않는 컬럼/라벨 hallucination 감소
- 쿼리 성공률 증가
- 질문 의도와 schema 매핑 정확도 향상

#### 검증 포인트
- 생성된 Cypher/SQL이 실제 schema에 맞는 비율
- schema lookup 후 재시도 없이 성공하는 비율
- nonexistent column/table/label 오류 감소

---

### C. 실행 하네스: tool 호출 정책 정교화

#### 변경할 부분
- tool 호출 전에 명시적 정책 추가
  - 최대 tool 호출 횟수
  - 한 응답에서 허용할 DB 호출 수
  - 동일 tool 중복 호출 제한
  - schema tool → query tool 순서 권장
- hybrid 질문 처리 순서 명시
  - 관계 후보 추출 → 집계 분석 → 답변 합성

#### 구현 위치 후보
- `backend/app/llm/coordinator_v2.py`
- `backend/app/llm/coordinator_v3.py`
- `backend/app/llm/prompts.py`

#### 기대 효과
- 에이전트 루프 불안정성 감소
- 무한/중복 호출 방지
- 답변 구조 일관성 향상

#### 검증 포인트
- 평균 tool 호출 횟수
- 동일 질문에 대한 호출 순서의 재현성
- 불필요한 schema/tool 호출 수 감소

---

### D. 출력 하네스: 답변 합성 규칙 강화

#### 변경할 부분
- 최종 답변 formatter 계층 추가
- 답변을 아래 구조로 강제
  1. 질문에 대한 직접 답
  2. 근거 데이터 요약
  3. 사용한 소스 (Neo4j / ClickHouse)
  4. 불확실성 / 데이터 한계
  5. 필요시 다음 탐색 제안

#### 구현 위치 후보
- `backend/app/llm/answer_formatter.py` (신규)
- `backend/app/llm/prompts.py`
- `backend/app/llm/coordinator_v3.py`

#### 기대 효과
- 사용자 입장에서 "그래서 답이 뭐지?" 문제가 줄어듦
- 도구 결과 나열형 응답 감소
- 데이터 근거가 드러나는 답변 증가

#### 검증 포인트
- 질문에 대한 직접 답변 포함 여부
- 사용 데이터 소스 표기 여부
- 응답 길이 대비 정보 밀도
- 사람이 읽었을 때 만족도 점수 향상

---

### E. 실패 하네스: fallback / recovery 경로 추가

#### 변경할 부분
- query guard 실패 시 재작성 재시도
- schema mismatch 시 schema tool 선행 후 재시도
- 빈 결과 시 "조회 조건 재설정" fallback 답변 추가
- timeout 시 축약 쿼리로 degrade

#### 구현 위치 후보
- `backend/app/llm/coordinator_v2.py`
- `backend/app/llm/coordinator_v3.py`
- `backend/app/llm/tools/graph_cypher_tool.py`
- `backend/app/llm/tools/clickhouse_query_tool.py`

#### 기대 효과
- 실패를 바로 사용자 오류 메시지로 노출하는 빈도 감소
- 부분 성공률 증가
- 사용자 신뢰도 향상

#### 검증 포인트
- 단순 실패율 감소
- recoverable error에서 재시도 성공률
- 빈 결과 응답의 유용성 평가

---

### F. 관측 하네스: 평가 가능한 로그/trace 확장

#### 변경할 부분
- 질문 단위 trace id 부여
- 아래 메타데이터 로깅
  - 질문 유형
  - 선택된 DB
  - 호출된 tool 순서
  - 생성된 SQL/Cypher
  - row_count
  - latency
  - fallback 발생 여부
  - 최종 sources

#### 구현 위치 후보
- `backend/app/llm/coordinator_v3.py`
- `backend/app/api/routes/chat.py`
- 별도 `backend/app/core/tracing.py` 추가 가능

#### 기대 효과
- 어떤 변경이 실제로 좋아졌는지 측정 가능
- 실패 원인 분석이 쉬워짐
- prompt 문제와 harness 문제를 분리 가능

#### 검증 포인트
- 로그만 보고 실패 원인을 재현 가능한가
- 변경 전/후 latency, tool count, success rate 비교 가능 여부

---

## 3. 권장 구현 우선순위

### 1순위
- pre-router 추가
- 출력 formatter 추가
- trace/log 구조화

### 2순위
- schema grounding 개선
- fallback / recovery 경로 추가

### 3순위
- hybrid 질문 전용 orchestration 개선
- rule 기반 DB selection + model selection 병행

---

## 4. 테스트/검증 전략

하네스 엔지니어링은 "좋아진 것 같다" 수준이면 안 되고,
**질문 세트와 측정 항목을 고정해 비교 가능**해야 한다.

### A. 평가용 질문 세트 고정
질문을 4종류로 나눠 평가한다.

#### 1) Graph 질문
- wafer A가 어떤 step을 거쳤는지 보여줘
- 특정 이상치 wafer와 연결된 upstream step을 찾아줘

#### 2) Analytics 질문
- 최근 7일간 chamber별 평균 측정값을 보여줘
- parameter별 평균과 표준편차 상위 10개를 보여줘

#### 3) Hybrid 질문
- 이상치 wafer들의 공정 경로와 parameter 분포를 같이 보여줘
- 특정 chamber와 연결된 wafer들을 찾고 최근 측정 평균을 비교해줘

#### 4) Ambiguous 질문
- wafer 상태를 분석해줘
- 문제가 있는 공정을 찾아줘

---

### B. 자동 평가 항목
각 질문에 대해 다음을 기록한다.

- 질문 유형 분류 결과
- 실제 호출 tool 목록
- selected sources
- first successful answer 여부
- total latency
- total tool calls
- guard failure 여부
- empty result 여부
- final answer length

---

### C. 수동 평가 항목
사람이 직접 1~5점으로 채점한다.

#### 평가 기준
1. **정답성** — 질문에 맞는 답을 했는가
2. **근거성** — 데이터 근거가 드러나는가
3. **직접성** — 장황하지 않고 바로 답하는가
4. **유용성** — 다음 행동에 도움이 되는가
5. **신뢰성** — 모르면 모른다고 솔직하게 말하는가

#### 추천 방식
- 변경 전 baseline 20문항
- 변경 후 same 20문항
- 평균 점수 비교

---

### D. A/B 비교 방식
하네스 변경 전후를 비교한다.

#### baseline
- 현재 main 브랜치 구조

#### candidate
- pre-router + formatter + trace 추가된 브랜치

#### 비교 지표 예시
- correct source selection rate
- first-answer success rate
- average latency
- average tool calls
- user-rated satisfaction score
- query failure rate

---

## 5. 권장 산출물

하네스 엔지니어링을 제대로 운영하려면 아래 산출물을 남기는 것이 좋다.

### 문서
- `HARNESS_ENGINEERING_PLAN.md` — 현재 문서
- `EVAL_QUESTION_SET.md` — 고정 질문 세트
- `EVAL_RESULTS_BASELINE.md` — 변경 전 결과
- `EVAL_RESULTS_CANDIDATE.md` — 변경 후 결과

### 코드
- `backend/app/llm/router.py`
- `backend/app/llm/answer_formatter.py`
- `backend/app/core/tracing.py`

---

## 6. 실행 순서 제안

1. pre-router 추가
2. formatter 추가
3. trace/log 구조화
4. baseline 질문 세트 작성
5. baseline 측정
6. candidate 적용
7. 동일 질문 세트 재측정
8. 결과 비교 및 반복 개선

---

## 7. 핵심 결론

이 프로젝트에서 하네스 엔지니어링은 단순히 프롬프트를 길게 쓰는 일이 아니다.
핵심은 아래를 함께 설계하는 것이다.

- 질문 분류
- DB 선택
- tool 호출 순서
- 안전 검증
- 답변 형식화
- 실패 복구
- 로그와 평가 체계

즉,
**"모델이 답을 잘하게 만드는 것"이 아니라**
**"모델이 답을 잘하게 될 수밖에 없는 실행 환경을 만드는 것"**이 목표다.
