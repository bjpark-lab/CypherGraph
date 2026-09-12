# 반도체 제조 데이터 LLM 연동 시스템 아키텍처 설계

## 1. 개요

### 1.1 목적

반도체 제조 데이터를 LLM에 연결하여 엔지니어들이 자연어만으로 아래 니즈를 해결할 수 있도록 한다.

| UC | 유스케이스 | 설명 |
|---|---|---|
| UC1 | 최신 웨이퍼 조회 | 타겟 공정을 진행한 최신 웨이퍼들 정보 조회 및 시각화 |
| UC2 | 조건부 필터링 + 통계 | 여러 조건들로 필터링 되는 웨이퍼들의 통계값, 이상치 제공 및 시각화 |
| UC3 | DOE/동시기 평가 그룹 | 같은 실험계획(DOE) 혹은 동일 시기에 같이 평가한 웨이퍼들의 부분집합 찾기 및 시각화 |
| UC4 | 공정 개발 이력 | 복수개의 실험 계획을 통해 공정 개발이 어떻게 진행되어 왔는지 이력 파악 |
| UC5 | 레시피→계측 예측 | 특정 레시피 파라미터를 바꿨을 때 예상되는 계측의 변화 예측 |
| UC6 | 계측→레시피 탐색 | 특정 계측을 변화시킬 수 있는 레시피 파라미터 찾기 |

### 1.2 설계 원칙

- **Hybrid DB**: RDB(PostgreSQL)와 Graph DB(Neo4j)를 질문 유형에 따라 선택적 활용
- **Multi-Agent**: 5개 전문 에이전트 + Tool 기반 구조로 기존 3-LLM(Coordinator → Cypher → QA) 확장
- **PostgreSQL = Single Source of Truth**: 원본 데이터는 PostgreSQL에 적재, Neo4j에는 관계 데이터만 동기화

---

## 2. 데이터 모델

### 2.1 원본 데이터 구조 (웨이퍼 단위)

하나의 웨이퍼에 대한 반도체 데이터(row: 웨이퍼, columns: 웨이퍼에 대한 정보)는 아래와 같이 분류된다.

#### 이전 공정 이력

타겟 공정까지 도달하기 전까지 거치는 공정들에 대한 정보.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `* TKIN TIME` | pd.Timestamp | 공정 시작 시간 |
| `* TKOUT TIME` | pd.Timestamp | 공정 종료 시간 |
| `* EQP` | str | 공정 진행 장비 |
| `* Chamber` | str | 공정 진행 챔버 |
| `* RF Time` | float | 챔버 PM 이후 진행한 RF Time |
| `* Stepseq` | str | 특정 제품이 전체 공정에서 어떤 단계인지 표시 (ex. UR123111, 앞2개는 제품을 특정, 뒤6개는 공정 순서) |
| `* PPID` | str | 공정을 어떤 방식으로 진행했는지 정의 (PPID가 같으면 레시피가 같을 가능성이 매우 높음) |

#### 타겟 공정 이력

엔지니어들이 관심 있어하는 주요 공정들 (주로 ETCH 공정). 이전 공정 이력의 모든 정보를 동일하게 포함하며, 추가 정보는 아래와 같다.

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `X * ETCH` | List[List[float]] | 해당 PPID에서 진행한 공정 레시피 (공정 스텝 × 레시피 파라미터) |
| `XNAMES * ETCH` | List[str] | 레시피 파라미터의 의미 |
| `* ETCH MAIN STEP` | List[str] | 레시피의 스텝 |

#### 계측 이력

**2D 계측:**

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `Y *` | List[List[float]] | 계측값 (웨이퍼 위치 × 계측 종류) |
| `YNAMES * ETCH` | List[str] | 계측 종류의 의미 |
| `SHOTS *` | List[str] | 웨이퍼의 위치 |

**3D 계측:**

| 컬럼 | 타입 | 설명 |
|---|---|---|
| `Y *` | List[List[List[float]]] | 계측값 (웨이퍼 위치 × 웨이퍼 높이 × 계측 종류) |
| `YNAMES * ETCH` | List[str] | 계측 종류의 의미 |
| `SHOTS *` | List[str] | 웨이퍼의 위치 정보 |
| `WLS *` | List[str] | 웨이퍼의 높이 정보 |

---

### 2.2 PostgreSQL 스키마

정형 쿼리(필터링, 통계 집계, 시계열 정렬)에 최적화된 RDB 설계.

#### 테이블 구조

```sql
-- 웨이퍼 기본 정보
CREATE TABLE wafer (
    wafer_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lot_id      VARCHAR(50) NOT NULL,
    product_code VARCHAR(20),
    created_at  TIMESTAMP DEFAULT NOW()
);

-- 이전 공정 이력
CREATE TABLE process_history (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wafer_id    UUID REFERENCES wafer(wafer_id),
    stepseq     VARCHAR(20) NOT NULL,
    ppid        VARCHAR(50) NOT NULL,
    eqp         VARCHAR(50),
    chamber     VARCHAR(50),
    rf_time     FLOAT,
    tkin_time   TIMESTAMP,
    tkout_time  TIMESTAMP,
    step_order  INTEGER          -- 공정 순서
);

-- 타겟 공정 이력
CREATE TABLE target_process (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wafer_id    UUID REFERENCES wafer(wafer_id),
    stepseq     VARCHAR(20) NOT NULL,
    ppid        VARCHAR(50) NOT NULL,
    eqp         VARCHAR(50),
    chamber     VARCHAR(50),
    rf_time     FLOAT,
    tkin_time   TIMESTAMP,
    tkout_time  TIMESTAMP,
    main_steps  JSONB            -- 원본 스텝 구조 보존 (List[str])
);

-- 레시피 파라미터 (EAV 패턴으로 풀어서 저장)
CREATE TABLE recipe_param (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    target_process_id UUID REFERENCES target_process(id),
    step_name         VARCHAR(50),   -- 공정 스텝명
    param_name        VARCHAR(100),  -- 레시피 파라미터명 (XNAMES에서 추출)
    param_value       FLOAT
);

-- 2D 계측
CREATE TABLE metrology_2d (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wafer_id      UUID REFERENCES wafer(wafer_id),
    metric_name   VARCHAR(100),   -- 계측 종류 (YNAMES에서 추출)
    shot_position VARCHAR(20),    -- 웨이퍼 위치 (SHOTS에서 추출)
    value         FLOAT
);

-- 3D 계측
CREATE TABLE metrology_3d (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    wafer_id      UUID REFERENCES wafer(wafer_id),
    metric_name   VARCHAR(100),
    shot_position VARCHAR(20),
    wl_position   VARCHAR(20),    -- 높이 정보 (WLS에서 추출)
    value         FLOAT
);
```

#### 핵심 인덱스

```sql
-- UC1: 타겟 공정의 최신 웨이퍼 빠른 조회
CREATE INDEX idx_target_stepseq_time ON target_process (stepseq, tkin_time DESC);

-- UC2: 장비/챔버별 필터링
CREATE INDEX idx_target_eqp_chamber ON target_process (eqp, chamber);

-- UC2: PPID(레시피) 그룹핑
CREATE INDEX idx_target_ppid ON target_process (ppid);

-- UC5/UC6: 레시피 파라미터 검색
CREATE INDEX idx_recipe_param_name ON recipe_param (param_name, param_value);

-- 계측 검색
CREATE INDEX idx_metrology_2d_metric ON metrology_2d (wafer_id, metric_name);
CREATE INDEX idx_metrology_3d_metric ON metrology_3d (wafer_id, metric_name);
```

#### 설계 포인트

| 설계 결정 | 이유 |
|---|---|
| 레시피를 EAV 패턴으로 풀어 저장 | `WHERE param_name = 'RF_Power' AND param_value > 500` 같은 SQL 필터링 가능 |
| `main_steps`는 JSONB로 보존 | 전체 레시피 조회 시 원본 구조 그대로 반환 가능 |
| 계측을 위치별로 행 분리 | `AVG`, `STDDEV`, `PERCENTILE_CONT` 등 SQL 집계 함수 바로 사용 가능 |
| 2D/3D 계측 테이블 분리 | 3D는 `wl_position` 차원이 추가되므로 별도 관리 |

---

### 2.3 Neo4j 그래프 모델

관계 탐색, 계보 추적, 그룹핑에 최적화된 Graph DB 설계.

#### 노드 (Node)

| 노드 라벨 | 주요 속성 | 설명 |
|---|---|---|
| `Wafer` | wafer_id, lot_id, product_code | 웨이퍼 |
| `Lot` | lot_id | 로트 |
| `DOE` | doe_id, doe_name, created_at | 실험계획 |
| `Equipment` | eqp_id, eqp_name | 장비 |
| `Chamber` | chamber_id, eqp_id | 챔버 |
| `Recipe` | ppid, stepseq, version, created_at | 레시피(PPID) |
| `ProcessStep` | stepseq, step_name | 공정 단계 |
| `Metrology` | metric_type, wafer_id | 계측 |

#### 관계 (Relationship)

| 관계 | 패턴 | 활용 유스케이스 |
|---|---|---|
| `BELONGS_TO` | `(Wafer)-[:BELONGS_TO]->(DOE)` | UC3: DOE 그룹핑, 같은 DOE의 웨이퍼들을 한번에 조회 |
| `CONTAINS` | `(Lot)-[:CONTAINS]->(Wafer)` | 로트 단위 조회 |
| `PROCESSED` | `(Equipment)-[:PROCESSED]->(Wafer)` | UC2: 장비별 웨이퍼 이력 |
| `HAS` | `(Equipment)-[:HAS]->(Chamber)` | 장비-챔버 계층 구조 |
| `APPLIED_TO` | `(Recipe)-[:APPLIED_TO]->(Wafer)` | 레시피-웨이퍼 매핑 |
| `EVOLVED_TO` | `(Recipe)-[:EVOLVED_TO]->(Recipe)` | UC4: 레시피 버전 이력, 공정 개발 진행 추적 |
| `AT_STEP` | `(Wafer)-[:AT_STEP]->(ProcessStep)` | 웨이퍼가 어떤 공정 단계에 있는지 |
| `NEXT` | `(ProcessStep)-[:NEXT]->(ProcessStep)` | 공정 순서 그래프 |
| `MEASURED` | `(Wafer)-[:MEASURED]->(Metrology)` | 계측 연결 |

#### 주요 Cypher 패턴

```cypher
-- UC3: DOE 그룹 조회
MATCH (w:Wafer)-[:BELONGS_TO]->(d:DOE {doe_id: 'DOE-2024-A'})
RETURN w, d

-- UC3: 동일 시기 평가 웨이퍼 (시간 범위 기반)
MATCH (w1:Wafer)-[:AT_STEP]->(s:ProcessStep {stepseq: 'UR123111'}),
      (w2:Wafer)-[:AT_STEP]->(s)
WHERE w1.tkin_time >= datetime('2024-01-01')
  AND w1.tkin_time <= datetime('2024-01-31')
  AND w2.tkin_time >= datetime('2024-01-01')
  AND w2.tkin_time <= datetime('2024-01-31')
RETURN w1, w2, s

-- UC4: 레시피 진화 이력 (가변 길이 패턴 매칭)
MATCH path = (r1:Recipe)-[:EVOLVED_TO*]->(rN:Recipe)
WHERE r1.stepseq = 'UR123111'
RETURN path
ORDER BY r1.created_at

-- UC4: 복수 DOE에 걸친 공정 개발 이력
MATCH (d:DOE)<-[:BELONGS_TO]-(w:Wafer)-[:AT_STEP]->(s:ProcessStep),
      (r:Recipe)-[:APPLIED_TO]->(w)
WHERE s.stepseq = 'UR123111'
RETURN d.doe_name, r.ppid, r.version, count(w) AS wafer_count
ORDER BY d.created_at

-- 공통 공정 경로 탐색
MATCH (w1:Wafer)-[:AT_STEP]->(s:ProcessStep)<-[:AT_STEP]-(w2:Wafer)
WHERE w1.wafer_id IN $wafer_ids
RETURN s, count(DISTINCT w1) AS shared_count
ORDER BY shared_count DESC
```

---

### 2.4 DB 간 동기화 전략

| 항목 | 내용 |
|---|---|
| Single Source of Truth | PostgreSQL |
| 동기화 방식 | CDC(Change Data Capture) 또는 배치 동기화 |
| 추천 스택 | Debezium(CDC) + Kafka → Neo4j Sink Connector |
| 동기화 주기 | 실시간 불필요 시 30분~1시간 배치도 가능 |
| Neo4j 저장 범위 | 관계 구조와 최소한의 속성만 저장 (상세 수치는 PostgreSQL 참조) |
| 공통 키 | `wafer_id`를 공통 키로 cross-DB join 가능 |

---

## 3. 에이전트 아키텍처

### 3.1 전체 구조

기존 3-LLM 구조(Coordinator → Cypher → QA)에서 **5-에이전트 + Tool** 구조로 확장.

```
[Engineer - Natural Language Query]
          │
          ▼
┌─────────────────────────┐
│     Router Agent        │  Phase 1: 의도 분류 + 실행 계획 생성
│  (Intent → Plan JSON)   │
└─────────┬───────────────┘
          │
    ┌─────┼─────┬──────────┐
    ▼     ▼     ▼          ▼
┌──────┐┌──────┐┌────────┐┌──────┐
│ SQL  ││Cypher││Analytics││ Viz  │  Phase 2: 병렬/직렬 실행
│Agent ││Agent ││ Agent  ││Agent │
└──┬───┘└──┬───┘└───┬────┘└──┬───┘
   │       │        │        │
   ▼       ▼        │        │
┌──────┐┌──────┐    │        │     Phase 2: DB 접근
│Postgr││Neo4j │    │        │
│ SQL  ││      │    │        │
└──────┘└──────┘    │        │
          │         │        │
          ▼         ▼        ▼
┌─────────────────────────────────┐
│       Synthesis Agent           │  Phase 3: 결과 종합 + 답변 생성
│  (Data + Viz → Domain Answer)   │
└─────────────────────────────────┘
```

### 3.2 유스케이스별 DB·에이전트 매핑

| UC | 유스케이스 | 사용 DB | 사용 에이전트 | 쿼리 예시 |
|---|---|---|---|---|
| UC1 | 최신 웨이퍼 조회 | PostgreSQL | SQL Agent → Viz Agent | `SELECT * FROM wafer w JOIN target_process tp ON ... WHERE tp.stepseq LIKE 'UR123%' ORDER BY tp.tkin_time DESC LIMIT 50` |
| UC2 | 조건부 필터링 + 통계 | PostgreSQL | SQL Agent → Analytics Agent → Viz Agent | `SELECT metric_name, AVG(value), STDDEV(value), PERCENTILE_CONT(0.99) ... WHERE eqp = 'EQP_A' GROUP BY metric_name` |
| UC3 | DOE/동시기 평가 그룹 | Neo4j | Cypher Agent → Viz Agent | `MATCH (w:Wafer)-[:BELONGS_TO]->(d:DOE {doe_id: 'DOE-2024-A'}) RETURN w, d` |
| UC4 | 공정 개발 이력 | Neo4j + PostgreSQL | Cypher Agent → SQL Agent → Viz Agent | `MATCH path=(r1:Recipe)-[:EVOLVED_TO*]->(rN:Recipe) WHERE r1.stepseq='...' RETURN path` |
| UC5 | 레시피→계측 예측 | PostgreSQL | SQL Agent → Analytics Agent → Viz Agent | Regression model (RF_Power, Gas_Flow → CD, Depth) |
| UC6 | 계측→레시피 탐색 | PostgreSQL | SQL Agent → Analytics Agent → Viz Agent | Feature importance / correlation analysis |

---

### 3.3 각 에이전트 상세 설계

#### Router Agent

| 항목 | 내용 |
|---|---|
| 역할 | 자연어 질문 → 실행 계획(execution plan) 변환 |
| 핵심 차이점 | 기존 Coordinator는 단순 의도 분류. Router는 어떤 에이전트를, 어떤 순서로, 어떤 파라미터로 호출할지 구조화된 JSON 출력 |
| 프롬프트 구성 | 반도체 도메인 용어 사전(stepseq 패턴, PPID 규칙, DOE 개념) + few-shot 예제 10~15개 |

**Output 예시:**

```json
{
  "intent": "recipe_impact_prediction",
  "agents": ["sql_agent", "analytics_agent", "viz_agent"],
  "params": {
    "stepseq": "UR123111",
    "target_param": "RF_Power",
    "target_metric": "CD"
  },
  "execution_order": "serial",
  "description": "RF_Power 변경 시 CD 변화 예측"
}
```

#### SQL Agent

| 항목 | 내용 |
|---|---|
| 역할 | 자연어 → PostgreSQL 쿼리 생성 및 실행 |
| 시스템 프롬프트 | PostgreSQL 스키마 전체 + 도메인 매핑 테이블 (장비명·챔버명·stepseq의 자연어-코드 매핑) |
| Tools | `execute_sql(query)`, `get_schema_info(table_name)` |
| 출력 | pandas DataFrame 형태로 후속 에이전트에 전달 |
| 에러 처리 | 에러 메시지를 LLM에 피드백하여 쿼리 자동 수정 (최대 3회 retry) |

**도메인 매핑 예시:**

```
"ETCH 1번 장비" → eqp = 'ETCH_EQP_01'
"3번 챔버"      → chamber = 'CH_03'
"UR123 제품"    → stepseq LIKE 'UR123%'
```

#### Cypher Agent

| 항목 | 내용 |
|---|---|
| 역할 | 자연어 → Cypher 쿼리 생성 및 실행 |
| 시스템 프롬프트 | 노드/관계 스키마 + 자주 사용되는 Cypher 패턴 라이브러리 |
| Tools | `execute_cypher(query)`, `get_graph_schema()` |
| 핵심 패턴 | DOE 탐색, 레시피 진화(`-[:EVOLVED_TO*]->`), 공통 공정 경로, 장비 이력 |

#### Analytics Agent

| 항목 | 내용 |
|---|---|
| 역할 | SQL/Cypher 에이전트가 가져온 데이터를 받아 통계 분석 수행 |
| 실행 방식 | LLM이 직접 계산하지 않고, 사전 정의된 Python 함수(Tool)를 호출 |

**사용 가능 Tools:**

| Tool | 기능 | 활용 UC |
|---|---|---|
| `run_statistics(df, columns)` | 기술통계, 이상치 탐지 (IQR, Z-score) | UC2 |
| `run_correlation(df, x_cols, y_cols)` | Spearman/Pearson 상관분석, Mutual Information | UC6 |
| `run_regression(df, features, target)` | Ridge/Lasso 회귀로 레시피→계측 예측 모델 | UC5 |
| `run_feature_importance(df, features, target)` | 계측에 영향 미치는 레시피 파라미터 순위 | UC6 |

**UC5/UC6 관계:** 본질적으로 같은 데이터의 정방향(레시피→계측)/역방향(계측→레시피) 분석. 히스토리컬 데이터로 회귀 모델 학습, 교차검증 + 신뢰구간 함께 리포팅.

#### Visualization Agent

| 항목 | 내용 |
|---|---|
| 역할 | 데이터 특성에 따라 적절한 차트 유형 선택 및 생성 |
| Tools | `wafer_map()`, `box_plot()`, `trend_chart()`, `scatter_plot()`, `recipe_comparison()` |

**차트 유형 선택 기준:**

| 차트 | 데이터 특성 | 활용 |
|---|---|---|
| Wafer Map | 2D 계측 → shot 위치별 히트맵 | 위치 기반 균일성 분석 |
| Box Plot | 조건별 그룹의 분포 비교 | 장비별, 챔버별, DOE별 비교 |
| Trend Chart | 시간 순서 계측값 | 시계열 변화 추이 |
| Scatter Plot | 레시피 파라미터 vs 계측값 | 상관관계 시각화 |
| Recipe Comparison | 두 레시피의 파라미터 차이 | 레이더 차트 |

#### Synthesis Agent

| 항목 | 내용 |
|---|---|
| 역할 | 모든 에이전트의 결과를 종합하여 도메인 맥락이 반영된 최종 답변 생성 |
| 입력 | SQL/Cypher 쿼리 결과 + Analytics 분석 결과 + Visualization 차트 |
| 출력 | 자연어 답변 + 시각화 결과 |
| 프롬프트 | 반도체 공정 도메인 지식 포함 (공정별 주요 관심 지표, 일반적인 파라미터-계측 관계 등) |

---

### 3.4 에이전트 간 데이터 흐름

```
Router Output (Plan JSON)
    │
    ├── sql_agent.execute()
    │       └── result: DataFrame (wafer metadata + recipe + metrology)
    │
    ├── cypher_agent.execute()
    │       └── result: Graph paths / node lists
    │
    ├── analytics_agent.execute(sql_result, cypher_result)
    │       └── result: Statistics / Model predictions / Feature rankings
    │
    ├── viz_agent.execute(all_results)
    │       └── result: Chart objects (wafer map, box plot, scatter, etc.)
    │
    └── synthesis_agent.synthesize(all_results, all_charts)
            └── result: Final answer (text + visualizations)
```

**Shared Memory 구조:** 에이전트 간 결과 전달은 구조화된 context 객체를 통해 이루어짐.

```python
class AgentContext:
    plan: dict              # Router의 실행 계획
    sql_results: dict       # SQL Agent 결과 {query: str, df: DataFrame}
    cypher_results: dict    # Cypher Agent 결과 {query: str, paths: list}
    analytics_results: dict # Analytics 결과 {stats: dict, model: dict}
    viz_results: dict       # Viz 결과 {charts: list}
    errors: list            # 에러 로그
```

---

## 4. 구현 가이드

### 4.1 추천 기술 스택

| 구성 요소 | 추천 기술 | 비고 |
|---|---|---|
| 에이전트 프레임워크 | LangGraph | 상태 기반 그래프로 에이전트 간 데이터 흐름 명시적 정의 가능 |
| RDB | PostgreSQL 16+ | JSONB, 고급 통계 함수, 파티셔닝 지원 |
| Graph DB | Neo4j 5.x | 가변 길이 패턴 매칭, APOC 라이브러리 |
| CDC/동기화 | Debezium + Kafka → Neo4j Sink | 실시간 불필요 시 30분~1시간 배치도 가능 |
| Analytics | Python (scikit-learn, scipy, pandas) | 사전 정의된 Tool 함수로 제공 |
| Visualization | Plotly / Matplotlib | Wafer map은 커스텀 구현 필요 |

### 4.2 LLM 모델 선택 전략

| 에이전트 | 모델 요구사항 | 추천 |
|---|---|---|
| Router Agent | 높은 reasoning 능력 | 고성능 모델 (Claude Sonnet 이상) |
| SQL Agent | SQL 코드 생성 특화 | 코드 생성 모델 |
| Cypher Agent | Cypher 코드 생성 특화 | 코드 생성 모델 |
| Analytics Agent | 안정적 function calling | Function calling 지원 모델 |
| Synthesis Agent | 도메인 지식 + 요약 능력 | 고성능 모델 (Claude Sonnet 이상) |
| Viz Agent | 차트 유형 선택 판단 | 중급 모델 가능 |

### 4.3 메타데이터 관리 (장기 운영 핵심)

| 관리 대상 | 내용 | 업데이트 시점 |
|---|---|---|
| DB 스키마 정보 | 테이블 정의, 컬럼 타입, 인덱스 | 스키마 변경 시 |
| 도메인 용어 사전 | 장비명·챔버명·stepseq 자연어-코드 매핑 | 신규 장비/공정 추가 시 |
| 예제 쿼리 라이브러리 | SQL/Cypher few-shot 예제 | 신규 유스케이스 추가 시 |
| Graph 스키마 | 노드/관계 정의 | 신규 관계 유형 추가 시 |

**자동화 포인트:** 새로운 공정이나 장비가 추가될 때 에이전트 프롬프트가 자동 업데이트되도록 메타데이터 관리 파이프라인 구성 필요.

---

## 5. 기존 대비 개선점 요약

| 항목 | 기존 (Graph DB + 3 LLM) | 신규 (Hybrid DB + 5 Agent) |
|---|---|---|
| DB | Neo4j 단일 | PostgreSQL + Neo4j 하이브리드 |
| 질문 라우팅 | Coordinator가 단순 분류 | Router가 실행 계획(JSON) 생성 |
| 통계/분석 | 별도 없음 (QA LLM이 직접 계산 시도) | Analytics Agent + 사전 정의 Python Tool |
| 시각화 | 별도 없음 | Viz Agent가 데이터 특성에 맞는 차트 자동 선택 |
| 필터링 쿼리 | Cypher로 처리 (비효율적) | SQL Agent가 PostgreSQL로 처리 (인덱스 활용) |
| 관계/계보 탐색 | Cypher로 처리 (적합) | Cypher Agent 유지 (Neo4j 활용) |
| 에러 처리 | 없음 | 에이전트별 retry 로직 + 에러 피드백 |
| 확장성 | 새 질문 유형 추가 어려움 | 새 에이전트/Tool 추가로 확장 용이 |
