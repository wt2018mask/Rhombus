# RHOMBUS 0204 — Tier A 동일 예산·실행 영수증 계약 개발 결과

기준일: 2026-10-31. **실제 DFT/MACE/NEB/MD를 실행한 기록이 아니다.**

## 최종 상태

- `TIER_A_PROTOCOL_DRAFT_READY`; `BENCHMARK_NOT_FROZEN`.
- `TIER_B_NOT_FROZEN`; `SCIENTIFIC_NO_GO_ABSTAIN`.
- `MODEL_OVERLAP=UNKNOWN`; `BASELINE_COST=UNQUALIFIED`.
- `execution_authorized=false`는 코드 내부의 불변 조건이다. 개발용 예산 숫자나 합성 영수증이 채워져도 실행을 승인하지 않는다.
- 원본 ZIP은 소유자 제공 바이트의 연속성이 검증된 것이며, 독립적인 게시자 서명은 아니다.

## 무엇을 만들었는가

`rhombus/benchmark/tier_a_budget_contract.py`에는 세 가지 순수 함수가 있다.

1. `make_execution_disabled_budget_draft(registry, pilot, protocol)`: 앞선 Tier A 그룹 registry의 SHA256과 TRAIN 4건의 선정 내역을 검증하고, 두 MACE 후보와 동일 계산 예산의 **미동결 초안**을 구성한다. 목표 물리량은 오직 LiTraj의 이산 NEB 이미지 `max(E_images)-min(E_images)` 에너지 span이다.
2. `inspect_budget_draft(draft)`: 엄격한 필드·source hash·model ID/weight SHA·CPU 2 스레드 float64·같은 BVSE-preconditioned 초기 경로·양 끝점 완화·FIRE/improved-tangent/climbing·수치 게이트를 검사하고, 남은 차단 요인 목록을 반환한다. 결코 `execution_authorized=true`를 반환하지 않는다.
3. `audit_paired_receipts(draft, receipts)`: **합성 영수증 테스트 또는 향후 별도 승인 후 생산된 텔레메트리의 형식 검사** 용도다. 4개 경로 × 2개 모델의 전체 조합을 강제한다. `CONVERGED`, `NONCONVERGED`, `TIMEOUT`, `OUT_OF_MEMORY`, `MODEL_ERROR`, `INPUT_INVALID`를 모두 분모에 남긴다. 미기록된 실패·중복 쌍·원본 이미지 불일치·숨긴 시간·비유한 값·변조된 모델·부정확한 수렴 판정을 거부한다. 예산 초과는 분모에서 제외하지 않고 위반으로 기록한다.

비용 기록은 각 경로·모델별로 `(input_read, model_load, endpoint_relax, neb_optimize, other_overhead)` 단계의 실제 wall/CPU 시간, 에너지 호출 수, force 호출 수, **모델 평가 수를 별도 계측**, peak RSS와 fixed force threshold를 요구한다. 실제 계측 도구가 연결되지 않았으므로 이런 값은 현재 존재하지 않는다. 코드만으로 관측값의 정직성이나 출처 인증을 증명할 수 없다.

BVSE로 준비된 경로의 **과거 생성 비용은 미확인**이다. 따라서 이 계약이 추후 실행되어도 '이미 주어진 초기 경로부터 시작한 post-preconditioning 비용'만 비교할 수 있다. 전체 end-to-end 비용의 동등성으로 확대하면 안 된다.

## 실제 소유자 메타데이터에 적용한 결과

다음 입력에 대해 `prepare_tier_a_budget_draft_0204.py`를 직접 실행했다.

- 기존 registry 1,681개: material 867개, chemsys 277개; label 사용 없음.
- 기존 화학계 충돌 제거 후보: Train 619 / Val 165 / Test 220; 677개 제외. Test target과 XYZ 에너지 미접근.
- TRAIN만의 4개 사전 선정 경로: `mp-777350_8_5_1_-1_0`, `mp-1186148_1_2_0_0_1`, `mp-765219_4_7_0_0_0`, `mp-758202_0_1_1_1_0`.
- 서로 다른 두 후보: 게시자 `MACE_MP_0_SMALL_PUBLISHER_EXAMPLE`과 Rhombus `MACE_MPA_0_MEDIUM_RHOMBUS`.
- 두 모델의 정확한 binary SHA가 모두 확정된 것은 아니다. Medium은 기존 0200 해시를 사용했으나 이번 환경에서 모델을 새로 내려받거나 실행해 재검증하지 않았다.

생성된 JSON은 실행이 중단된 채로 다음을 나타낸다.

- `paired_rows_required=8`.
- `execution_authorized=false`.
- `INITIAL_IMAGE_HASHES_MISSING`.
- `MODEL_CHECKPOINT_UNPINNED` (publisher small).
- `NEB_NUMERIC_SETTINGS_MISSING`.
- `PER_ARM_PER_EDGE_CAPS_MISSING`, `TOTAL_PILOT_CAPS_MISSING`.
- `OWNER_RUN_AUTHORIZATION_MISSING`.
- `TRAINING_OVERLAP_UNKNOWN`, `REFERENCE_TARGETS_SEALED`.

## 테스트 및 재현

이 개발 단위의 새 테스트와 이전 Tier A preflight를 합쳐 **64 passed, 2 skipped** (선택적 외부 artifact 입력 없음). 앞선 메타데이터 그룹 검사 독립 테스트 **9 passed**. 실제 이전 registry/pilot/protocol JSON으로 CLI 실행 성공. **실제 MACE, DFT, NEB, MD 또는 예측 오차 계산 없음.**

```bash
python -m pytest -q tests/test_tier_a_budget_contract_0204.py tests/test_tier_a_preflight_0204.py
python -m scripts.benchmark.prepare_tier_a_budget_draft_0204 \
  --registry /trusted/tier_a_metadata_registry_draft.json \
  --pilot /trusted/tier_a_tiny_train_pilot_draft.json \
  --protocol /trusted/tier_a_protocol_candidate.json \
  --out-dir /tmp/NEW-0204-budget-draft
```

출력은 저장소 외부의 새 경로에만 생성한다. 기존 증거, `CURRENT`, `HANDOFF`, checkpoints를 수정하거나 덮어쓰지 않는다.

## 다음 Gate — 실행 이전에 꼭 필요한 것

- 저자가 배포한 small 모델의 정확한 binary hash와 허용되는 모델 license, medium 모델의 현재 실행 환경 재검증.
- 4개 TRAIN 경로의 동일 initial-image 바이트 SHA256 및 초기 상태 geometry 합치 확인. 이때 held-out 에너지값은 열지 않는다.
- endpoint/NEB fmax, 최대 steps, spring constant, 수렴 실패 분류를 수치로 고정. 예제 notebook의 기본 fmax 누락 여부에 주의한다.
- **모델별·경로별** wall·CPU·energy/force requests·실제 model evaluations·peak RSS의 정확한 상한과 **전체** 예산·자원에 대해 사용자 별도 승인.
- preconditioning의 기존 계산 비용 미확인, pretrained overlap UNKNOWN, 전해질 Tier B 미확인, 해당 소규모 실험의 통계적 검정력 부족을 반드시 인정한다.

사용자가 뒤에 별도 실행 승인을 내리더라도 이 파일은 직접 실행 프로그램이 아니다. 물리적 실행기와 해당 권한은 별도 구현·검증을 요구한다. 4건 TRAIN 파일럿은 공학적 계측 시험이며 우월성이나 독립적인 model generalization 검증이 아니다.

## GitHub와 CI

현재 새 코드는 GitHub에 push·commit·merge하지 않았다. GitHub의 0204 Draft PR #376에서 기존 Fast CI `test_compaction_preserves_effective_state_and_rejects_tamper` 실패는 0204 테스트가 0203 상태와 완전 동일함을 요구하는 오래된 가정과 관련해 따로 조사된 사항이다. 이번 개발 단위로 해당 CI 통과를 주장하지 않는다. 별도 수정안은 과거 산출물로 유지한다.
