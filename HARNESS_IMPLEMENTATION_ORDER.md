# Harness Implementation Order

이 문서는 하네스 엔지니어링을 실제로 구현할 때 **어떤 파일부터 어떤 순서로 바꾸는 게 가장 안전한지** 정리한 실행 가이드다.

---

## 목표

사용자 질문에 대해 더 만족도 높은 답변을 만들기 위해 다음을 개선한다.

- 질문 분류 정확도
- DB 선택 정확도
- tool 호출 일관성
- 답변 직관성
- 실패 복구 능력
- 측정 가능성

---

## 1단계 - Pre-router 추가

### 목적
질문을 먼저 graph / analytics / hybrid / ambiguous로 분류해
coordinator가 무작정 모든 걸 판단하지 않게 만든다.

### 변경 파일
- 신규: `backend/app/llm/router.py`
- 수정: `backend/app/llm/coordinator_v3.py`
- 수정: `backend/app/api/routes/chat.py` (필요 시 trace 전달)

### 구현 포인트
- 초기에 rule-based로 시작
- 키워드 예시:
  - graph: 관계, 연결, 경로, 거쳤는지, upstream, downstream
  - analytics: 평균, 분포, 추세, 기간, 상위, stddev, variance
  - hybrid: 관계 + 통계가 같이 포함된 경우
- ambiguous는 schema tool 또는 보수적 질문 응답으로 연결

### 기대 효과
- 잘못된 DB 선택 감소
- 불필요한 tool 호출 감소

---

## 2단계 - Answer formatter 추가

### 목적
최종 응답을 "질문에 대한 직접 답" 중심으로 재구성한다.

### 변경 파일
- 신규: `backend/app/llm/answer_formatter.py`
- 수정: `backend/app/llm/prompts.py`
- 수정: `backend/app/llm/coordinator_v3.py`

### 구현 포인트
- 출력 구조 강제
  1. 직접 답변
  2. 근거 데이터 요약
  3. 사용한 소스
  4. 한계/불확실성
- tool 결과를 그대로 나열하지 않게 함

### 기대 효과
- 사용자 만족도 증가
- 응답 가독성 향상

---

## 3단계 - Trace / 평가 로그 구조화

### 목적
변경이 실제로 좋아졌는지 측정 가능하게 만든다.

### 변경 파일
- 신규: `backend/app/core/tracing.py`
- 수정: `backend/app/llm/coordinator_v3.py`
- 수정: `backend/app/api/routes/chat.py`

### 기록 항목
- trace_id
- question_type
- selected_sources
- tools_called
- generated_query(sql/cypher)
- row_count
- latency_ms
- fallback_used
- final_answer_length

### 기대 효과
- baseline vs candidate 비교 가능
- 실패 원인 추적 가능

---

## 4단계 - Schema grounding 개선

### 목적
schema mismatch와 hallucination을 줄인다.

### 변경 파일
- 신규: `backend/app/llm/schema_context.py`
- 수정: `backend/app/llm/prompts.py`
- 수정: `backend/app/services/clickhouse_service.py`
- 수정: `backend/app/services/neo4j_service.py`

### 구현 포인트
- 질문 유형별로 필요한 schema만 축약 제공
- alias dictionary 추가
- 중요 컬럼/테이블 우선 노출

### 기대 효과
- 쿼리 성공률 증가
- guard failure 감소

---

## 5단계 - Failure recovery 추가

### 목적
한 번 실패했다고 바로 실패 응답을 내지 않게 만든다.

### 변경 파일
- 수정: `backend/app/llm/tools/graph_cypher_tool.py`
- 수정: `backend/app/llm/tools/clickhouse_query_tool.py`
- 수정: `backend/app/llm/coordinator_v3.py`

### 구현 포인트
- guard 실패 시 1회 재작성
- schema mismatch 시 schema tool 선행 후 재시도
- empty result 시 조건 완화 또는 안내 응답
- timeout 시 축약 쿼리 사용

### 기대 효과
- recoverable failure 감소
- 사용자 체감 안정성 증가

---

## 6단계 - Hybrid orchestration 개선

### 목적
관계 + 통계가 동시에 필요한 질문을 더 자연스럽게 처리한다.

### 변경 파일
- 수정: `backend/app/llm/coordinator_v3.py`
- 수정: `backend/app/llm/prompts.py`
- 필요 시 신규: `backend/app/llm/plans.py`

### 구현 포인트
- hybrid 질문의 기본 시퀀스 정의
  1. 관계 후보 조회
  2. 분석 대상 식별
  3. 집계/분포 실행
  4. 답변 합성

### 기대 효과
- 혼합형 질문 품질 향상
- DB 간 역할 분담 선명화

---

## 병행 산출물

구현과 함께 아래 문서를 업데이트한다.

- `EVAL_QUESTION_SET.md`
- `EVAL_RESULTS_BASELINE.md`
- `EVAL_RESULTS_CANDIDATE.md`

---

## 추천 실제 작업 순서

1. `router.py` 추가
2. `coordinator_v3.py`에 pre-router 연결
3. `answer_formatter.py` 추가
4. trace/log 구조화
5. baseline 측정
6. schema grounding 개선
7. failure recovery 추가
8. hybrid orchestration 개선
9. candidate 측정
10. 비교 후 추가 튜닝

---

## 첫 구현 스프린트 추천 범위

가장 먼저 손대기 좋은 범위:

- pre-router
- answer formatter
- trace/log 구조화

이 3개만 해도 실제 사용자 만족도와 디버깅 편의가 꽤 개선될 가능성이 높다.
