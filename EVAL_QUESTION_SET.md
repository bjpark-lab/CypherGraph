# Evaluation Question Set

이 문서는 RCP Cypher의 하네스 엔지니어링 전/후를 비교하기 위한 **고정 평가 질문 세트**다.
동일한 질문 세트를 baseline / candidate 양쪽에 반복 적용해서 결과를 비교한다.

---

## 사용 원칙

- 질문 문구는 가능하면 동일하게 유지한다.
- 각 질문마다 아래를 기록한다.
  - 분류 결과 (graph / analytics / hybrid / ambiguous)
  - 호출된 tool 목록
  - selected sources
  - 응답 시간
  - 성공/실패
  - 수동 평가 점수
- 응답 품질뿐 아니라 **tool 선택과 실행 안정성**도 함께 본다.

---

## A. Graph 질문

### G1
wafer A가 어떤 recipe step을 거쳤는지 보여줘

### G2
이 wafer와 연결된 metrology 노드를 찾아줘

### G3
특정 chamber와 연결된 wafer 흐름을 보여줘

### G4
lot A에 속한 wafer들이 어떤 공정 관계를 가지는지 설명해줘

### G5
특정 이상치 wafer와 연결된 upstream step을 찾아줘

### 기대 성향
- Neo4j 우선
- graph_cypher_qa_tool 사용
- 관계/경로 중심 응답

---

## B. Analytics 질문

### A1
최근 7일간 chamber별 평균 측정값을 보여줘

### A2
최근 30일간 parameter별 평균과 표준편차 상위 10개를 보여줘

### A3
lot별 측정 건수 상위 20개를 보여줘

### A4
wafer별 특정 parameter의 평균값을 비교해줘

### A5
최근 일주일간 step별 측정값 추이를 보여줘

### A6
이상치가 많은 chamber 순으로 정리해줘

### A7
특정 parameter의 분포를 요약해줘

### A8
최근 3일간 lot별 최대값/최소값/평균값을 보여줘

### 기대 성향
- ClickHouse 우선
- clickhouse_query_tool 사용
- 집계/분포/추세 중심 응답

---

## C. Hybrid 질문

### H1
이상치 wafer들의 공정 경로와 parameter 분포를 같이 보여줘

### H2
특정 chamber와 연결된 wafer들을 찾고, 그 wafer들의 최근 측정 평균을 비교해줘

### H3
lot A의 wafer 관계를 보고, 동시에 step별 측정 추이도 요약해줘

### H4
문제 step과 연결된 wafer들을 찾고 각 wafer의 통계값을 비교해줘

### 기대 성향
- Neo4j + ClickHouse 순차 사용
- 필요시 schema tool 선행
- 답변에서 관계 + 통계가 함께 드러남

---

## D. Ambiguous 질문

### X1
wafer 상태를 분석해줘

### X2
문제가 있는 공정을 찾아줘

### X3
최근 데이터에서 이상한 패턴이 있는지 봐줘

### X4
이 lot에 대해 중요한 인사이트를 알려줘

### 기대 성향
- router의 분류 품질 테스트용
- schema tool 또는 clarifying 전략 검증 가능
- 한 DB만 고집하지 않는지 확인

---

## E. 수동 평가 폼

각 질문마다 아래 5개 항목을 1~5점으로 평가한다.

1. 정답성
2. 근거성
3. 직접성
4. 유용성
5. 신뢰성

총점 예시:
- 21~25: 매우 만족
- 16~20: 대체로 만족
- 11~15: 애매함
- 10 이하: 개선 필요

---

## F. 자동 기록 항목 템플릿

각 질문마다 다음 형식으로 기록한다.

```md
### Question: G1
- classification:
- tools:
- sources:
- latency_ms:
- success:
- guard_failure:
- empty_result:
- answer_length:
- score_accuracy:
- score_groundedness:
- score_directness:
- score_usefulness:
- score_trustworthiness:
- notes:
```

---

## G. 비교 원칙

- baseline과 candidate에 **동일 질문 세트** 사용
- 가능하면 동일 데이터 상태에서 실행
- 응답 길이보다 **적절한 DB 선택과 질문 만족도**를 우선 평가
