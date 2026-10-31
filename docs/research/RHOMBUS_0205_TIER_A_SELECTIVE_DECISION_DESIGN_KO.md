# Rhombus 0205 — Tier A 선택적 판단의 위험·coverage 설계 계약

대상: `TIER_A_RETROSPECTIVE_LI_HOP_ENERGY_SPAN`. 게시자 관측량은 **이산 NEB 이미지의 비방향성** `max(E_images)−min(E_images)`이며, 전방 이온 활성화 장벽·3D percolation·전도도가 아니다.

## 이번 구현

- `rhombus/benchmark/tier_a_selective_design.py`는 검증된 비실행 비용 계약에 종속된 선택적 판단 프로토콜 **후보**를 생성한다. `ACCEPT`, `ABSTAIN`, `ESCALATE` 결정은 참조 target 조회 전의 적용성·불확실성 정보로만 결정하도록 규정한다.
- 실제 수치 선택은 **미설정**이다: `severe_error_delta_eV`, `maximum_false_accept_risk`, `minimum_coverage`, `uncertainty_threshold`, `escalation_cost_budget_cpu_seconds`. 이를 채워도 자동 동결되거나 계산 허가가 되지 않는다.
- `summarize_synthetic_paired_decisions`는 오직 명시적 `SYNTHETIC_ONLY_NO_REAL_LABELS` fixture로 평가 산술을 시험한다. 입력은 참조 에너지나 예측값을 받아들이지 않는다. 사전에 선언된 **전체 경로 집합과 두 arm 모두의 완전한 실행 기록**이 요구된다. 두 모델 중 하나의 실패·비수렴·에스컬레이션도 분모와 비용에서 빠지지 않는다.
- 실패한 실행 결과를 `ACCEPT`로 분류하거나 결과 누락을 조용히 제외하면 오류가 발생한다. 허용 수가 0이면 위험은 `None`/`UNDEFINED_NOT_ZERO`이며 0% 위험 달성으로 판정하지 않는다.
- **화학계(chemsys)** 를 최소 의존 군집 단위로 취급한다. 허용 집단의 각 군집에 하나라도 중대한 오류가 있으면 군집 기준 위험에 반영한다. 표시하는 Wilson 구간은 **설명적 진단**일 뿐 독립 source/prototype 검증이 없으므로 확증적 불확실성 구간이나 정확도 보증이 아니다.
- 서로 다른 두 모델의 허용 경로 집합이 같지 않으면 `matched_coverage_decision_sets=false`이다. 같은 비용/범위를 명시적으로 비교하기 전에는 모델 우위 주장이 불가능하다.
- `scripts/benchmark/prepare_tier_a_selective_design_0205.py`는 입력 계약을 strict JSON으로 검사한 뒤 저장소 밖의 새로운 폴더에만 비실행 후보·검사 기록을 만든다. 기존 파일 덮어쓰기를 허용하지 않는다.

## 남아 있는 과학·통합 필수 조건

1. 소유자는 모든 임계값, 데이터 선택, 실패 처리 및 비용 초과 정책을 **평가 전** 명시적으로 동결해야 한다. 선언한 조건 자체의 등록 시간·버전·독립 관리가 아직 없다.
2. 정확한 MACE 가중치 바이트, ASE/NEB 계산 조건, 동일 비용 상한, 실제 계산기 계측의 적합성·수렴을 별도 확인해야 한다. TRAIN 4경로는 기능·비용 파일럿일 뿐 모델 성능 우위 검증이 아니다.
3. 독립 DFT-NEB 참조와 모델 학습 노출 검증, 화학계 외 prototype/source 독립성에 따라 해석 가능한 과학적 주장의 범위가 정해진다. LiTraj 하나만으로 출처 독립은 증명되지 않는다.
4. `TIER_B_SOLID_ELECTROLYTE_SPECIFIC`은 별도의 재료 상·전기화학적 용도·실제 Li hop 근거가 생기기 전까지 `NOT_FROZEN`이다.

**판정:** `TIER_A_PROTOCOL_DRAFT_READY` / `BENCHMARK_NOT_FROZEN` / `TIER_B_NOT_FROZEN` / `SCIENTIFIC_NO_GO_ABSTAIN`. 이 변경은 데이터를 대상으로 한 성능 평가 또는 실행 승인이 아니다.
