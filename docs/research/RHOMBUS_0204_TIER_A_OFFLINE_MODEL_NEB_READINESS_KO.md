# Rhombus 0204 — Tier A 모델 정체성·공통 NEB 실행 전 오프라인 감사

**범위:** P0의 `TIER_A_RETROSPECTIVE_LI_HOP_DISCRETE_NEB_ENERGY_SPAN` 비실행 준비 검사. 실제 MLIP/DFT/NEB/MD, 검증용 target, 점수 계산, 원격 요청, GitHub 변경은 없음.

## 1. 과학적 경계

- `BENCHMARK_NOT_FROZEN`, `SCIENTIFIC_NO_GO_ABSTAIN`, `execution_authorized=false`를 변경하지 않는다.
- 관측량은 게시자 이산 NEB 이미지 에너지 범위 `max(E_images)−min(E_images)`다. 방향성 forward 장벽, 3D percolation, 확산, 이온전도도가 아니다.
- LiTraj 원본 ZIP SHA256 `b7a99d89337902e9e1da319f57547170fdb132bf15bf6ffef03a0140e2207d7f`는 사용자 전달 바이트 정체성. 게시자 독립 서명/해시는 확인되지 않았다.
- 데이터 참조 영수증은 4개 TRAIN `_init.xyz`의 내용 바이트를 고정하지만 모델 학습 누출, hop 물리적 정확성, DFT 수렴을 입증하지 않는다.

## 2. 구현된 비실행 검증기

신규 모듈 `rhombus/benchmark/tier_a_model_neb_preflight.py`:

- 기존 비용 계약의 정확한 필드·과학 경계·실행 거부 정책 검증.
- 기존 초기 경로 pin receipt와 비용 draft의 4개 edge ID·group ID·raw SHA256·바이트 수 대조. ZIP 재스캔 또는 XYZ 구조·에너지 디코딩 없음.
- 공개 MACE upstream 소스 매핑 기준으로 **MACE-MP-0 small**과 **MACE-MPA-0 medium**을 명시적으로 구별함. 해당 매핑은 2026-10-19 Git HEAD `e37c8583a8b1b586e5888fa6dca86e8f591e2606`에서 확인한 `mace/calculators/foundations_models.py`의 별칭 URL이다. 이것은 바이너리 서명·해시가 아니다.
- 모델 파일이 실제 제공된 경우에만 파일을 읽어 크기·SHA256을 비교하며, **MACE/torch import, checkpoint 역직렬화, 인터넷 다운로드, 실행이 없다**. Rhombus medium의 기존 SHA256 `75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638`와 과거 파일 길이 79,462,305 B는 역사적 기록으로 검증한다. 이번 환경에는 두 checkpoint 파일이 제공되지 않아 재해시하지 않았다.
- MACE small의 예상 SHA256은 아직 없다. 모델 파일을 제공받아 SHA256을 **관측**하더라도, 사전에 승인·고정된 checkpoint와 같다고 주장하지 않는다.
- 공통 FIRE + improved-tangent CI-NEB의 **숫자 후보** (endpoint/NEB fmax 0.1 eV/Å, 각각 max 100 단계, spring 5.0 eV/Å²)를 별도 `SUGGESTED_NEB_NOT_FROZEN` JSON으로 생성할 수 있다. 이는 게시자 예제에서 영감을 받은 *제안*일 뿐 행별 DFT 기준 설정이 아니고 owner freeze가 아니다. 특히 게시자 예제의 모든 FIRE 호출에 동일 fmax/steps가 전달되지는 않으므로 이를 단순 복제라고 표시하지 않는다.
- 실행 환경 정보가 있다면 Python, ASE, mace-torch, torch, numpy, MACE 소스 revision, adapter 바이트 해시, 계산 호출 계측 및 스레드 설정을 확인하지만 **사용자 선언은 독립 실행 증명이 아니다**.
- 보고서 출력에는 모델 경로가 없고, 원본 target 및 예측 값도 포함되지 않는다. 별도 승인 없이 `eligible_for_separate_owner_review`는 단지 검토 후보 여부, 계산 실행 권한과는 무관하다.

CLI `scripts/benchmark/inspect_tier_a_model_neb_0204.py`:

```bash
python -m scripts.benchmark.inspect_tier_a_model_neb_0204 \
  --draft tier_a_equal_budget_input_pinned_DRAFT_NOT_AUTHORIZED.json \
  --binding-receipt tier_a_four_init_xyz_byte_receipt.json \
  --candidate-neb-settings \
  --output tier_a_offline_model_neb_review_NON_EXECUTABLE.json
```

`--small-model`과 `--medium-model`은 정확한 로컬 바이트 파일이 있을 때만 선택적으로 지정한다. 기본값은 **모델 미제공**이고 `NOT_PROVIDED` 처리다. 소유자가 사전 승인하지 않은 가중치를 자동 내려받거나 실행하지 않는다. 기존 보고서/입력 파일 덮어쓰기를 거부한다.

## 3. 실제 이전 단계 receipt의 결과

오프라인 프로그램은 4개 TRAIN input receipt의 4개 raw SHA256과 총 1,050,883 B가 현재 draft와 맞는지 확인했다. 검증 대상은 이전 단계에서 생성된 **영수증 메타데이터의 자기 일관성**이며, 이번 작업에서 ZIP이나 각 XYZ를 다시 열지는 않았다.

- `paired_rows_required`: 8 (= 4 TRAIN edge × 2 model arm)
- `execution_authorized`: `false`
- `eligible_for_separate_owner_review`: `false`
- 모델 두 개 모두 파일 **미제공** (`NOT_PROVIDED`)
- upstream MACE small checkpoint SHA: **UNSET**
- NEB 숫자 설정: **UNSET** (별도 제안 JSON에만 후보값 기록)
- arm-edge 예산 6항목 / 총예산 2항목: **UNSET**
- runtime 버전·adapter 계측 증거: **UNSET**
- `UNKNOWN_TRAINING_OVERLAP`, `REFERENCE_TARGETS_SEALED`, 게시자 진위 미확인 계속 유지

## 4. 최초 실제 계산 승인 전에 필요한 최소 결론

1. 두 checkpoint의 실제 고정 바이트·SHA256, 모델 공급망/사용 라이선스와 불확실한 학습 overlap 기록 (small은 expected hash를 owner가 승인해야 한다).
2. 공통 초기 이미지 4개 SHA가 계산 입력과 동일함을 확인하고, endpoint/CI-NEB의 세부 숫자 규칙을 **사전 결정**.
3. CPU 2 thread/float64 등 통일된 실행 환경·계측 adapter, GPU/CPU 혼합 금지, wall/CPU/energy/force/call/RSS 총 예산 명시.
4. 한계 초과·비수렴·예외를 포함한 **8개 의무 기록**과 실패 분모 유지.
5. 소유자의 별도 명시적 계산 실행 승인. 소규모 TRAIN-only 파일럿은 비용 가능성 조사이며 과학적 성능 우위의 최종 확인이 아님.

## 5. 검증·한계

신규 단위 테스트: `22 passed`; 누적 Tier A 오프라인 테스트: `106 passed, 2 skipped, 1 expected zipfile duplicate-name warning`. 기존 Rhombus 전체 GitHub CI 실행이나 원격 PR 업데이트 없음. 이미 존재하는 0204 Fast CI 실패는 이 변경으로 해결되었다고 주장하지 않는다.

**최종 상태:** `TIER_A_PROTOCOL_DRAFT_READY`; `BENCHMARK_NOT_FROZEN`; `TIER_B_NOT_FROZEN`; `SCIENTIFIC_NO_GO_ABSTAIN`.
