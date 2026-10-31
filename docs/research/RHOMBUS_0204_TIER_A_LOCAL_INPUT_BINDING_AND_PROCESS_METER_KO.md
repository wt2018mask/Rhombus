# Rhombus 0204 — Tier A 초기 경로 바이트 고정 및 로컬 비용 계측 어댑터

2026-10-31 · 실행 전 검증용 개발 산출물 · **기존 과학적 판정 변경 없음**

## 과학적 상태

- `TIER_A_PROTOCOL_DRAFT_READY`; `BENCHMARK_NOT_FROZEN`; `TIER_B_NOT_FROZEN`; `SCIENTIFIC_NO_GO_ABSTAIN`.
- 여기서 사용하는 관측량은 **비방향성 이산 NEB 이미지 에너지 범위** `max(E_images)-min(E_images)`다. 전방 이온 활성화 장벽, 연속 saddle, 3D percolation 또는 전도도로 승격하지 않는다.
- DFT 참조의 개별 전자조건, Li 원자·vacancy 매핑, 사전학습 노출 및 source-out 독립성은 미확인이다. 원본 ZIP의 SHA256은 사용자가 제공한 바이트 연속성만 증명하며 출판자 인증이 아니다.

## 실제 수행한 작업

이전 0204 후보에서 메타데이터만으로 선택한, **서로 다른 화학계의 TRAIN 초기 경로 4건**을 변경하지 않고 사용했다.

입력은 사용자가 제공한 `nebDFT2k.zip`: **68,583,182 bytes**, SHA256 `b7a99d89337902e9e1da319f57547170fdb132bf15bf6ffef03a0140e2207d7f`.

신규 `tier_a_input_pin.py`는 ZIP 자체의 크기·해시를 확인한 다음 다음 **4개의 `_init.xyz` 멤버만** 스트리밍으로 압축 해제하여 바이트 길이와 SHA256을 기록한다. 내용의 XYZ 원자좌표·에너지·힘을 decode하거나 parse하지 않았으며, `_relaxed.xyz`, validation/test XYZ 및 index의 `em_dft`/`em_bvse` target을 열지 않았다. 전체 ZIP CRC나 반복적인 기하학 감사도 수행하지 않았다.

| TRAIN edge ID | raw 초기 XYZ 바이트 | SHA256 접두어 |
| --- | ---: | --- |
| `mp-777350_8_5_1_-1_0` | 295426 | `9cd0af56ab56` |
| `mp-1186148_1_2_0_0_1` | 312564 | `3ddd591517f6` |
| `mp-765219_4_7_0_0_0` | 199401 | `8d9ce7f8817a` |
| `mp-758202_0_1_1_1_0` | 243492 | `924ec08b528a` |
| 합계 | **1050883** | — |

각 파일의 **전체 SHA256**은 별도 `tier_a_four_init_xyz_byte_receipt.json`에 저장돼 있다. `initial_images_sha256` 필드는 *원시 `_init.xyz` 파일의 압축 해제 바이트*를 식별하는 값이다. 이 해시는 파서가 재구성한 원자 객체나 물리적 초기·끝점의 올바름에 관한 증명이 아니다.

`inspect_budget_draft` 확인 결과 `INITIAL_IMAGE_HASHES_MISSING`이 해소됐다. 나머지 목록은 `MODEL_CHECKPOINT_UNPINNED`, `NEB_NUMERIC_SETTINGS_MISSING`, `PER_ARM_PER_EDGE_CAPS_MISSING`, `TOTAL_PILOT_CAPS_MISSING`, `OWNER_RUN_AUTHORIZATION_MISSING`, `TRAINING_OVERLAP_UNKNOWN`, `REFERENCE_TARGETS_SEALED`이다. 마지막의 target 봉인은 **유지할 보호 조건**이며 실행 결손으로 해결해서는 안 된다.

## 비용 계측기 — 구현과 증거 경계

신규 `tier_a_local_meter.py`는 *과학 계산을 수행하지 않는*, 실행기에 나중에 통합할 로컬 프로세스 계측 인터페이스다.

- `LocalProcessMeter.phase(...)`: `input_read`, `model_load`, `endpoint_relax`, `neb_optimize`의 단조 증가 순서·비중첩을 강제하고 `time.perf_counter_ns` 및 `time.process_time_ns`를 측정한다. 나머지 시간은 `other_overhead`에 포함한다.
- `record_call('energy' | 'force' | 'model_calculation')`: 적법한 계산 단계에서의 *호출자 보고 이벤트*만 계산한다. **실제 신경망 forward pass의 전부를 독립적으로 계수한 증거가 아니다.** 향후 권한 있는 러너에서는 원자 계산기 경계에서 후킹해야 한다.
- Linux/macOS의 `resource.RUSAGE_SELF` 및 Windows에서 사용 가능한 `psutil`의 `peak_wset` 등으로 **프로세스 전체 high-water 메모리**를 취급한다. 이전 메모리·공유 환경을 포함할 수 있고 child process 메모리는 대표하지 않는다. Windows의 `psutil`이 설치되지 않았거나 peak field가 없으면 보수적으로 실패한다.
- `finish(...)`: 실패·비수렴을 명시하고 기존 `tier_a_budget_contract.py` 영수증 형식에 맞는 출력과 비인증 계측 envelope를 생성한다. 에너지값·예측오차·참조 target을 저장하지 않는다.
- `audit_local_meter_envelopes(...)`: 요구되는 모든 4×2=8 쌍, 이벤트 순서·해시·요청 수·비용 계약 등을 교차 검사한다. **로컬 이벤트 로그는 위조 불가능한 독립적 실행 증명이 아니다.**
- 실제 모델/NEB 메서드나 라이브러리를 import하거나 호출하지 않았다. 합성 counter hook만 테스트했다.

## 검증 방법 및 한계

`PYTHONPATH=<개발 코드 루트> python -m pytest -q <개발 코드 루트>/tests`

- 본 개발 디렉터리의 오프라인/합성 테스트: **84 passed, 2 skipped**; 2 skip은 사용자 원본 ZIP이 자동 제공되지 않는 기존 테스트 경로이다.
- 이전 비용 검증·누출 방지 모듈 2개, 이번 원본 경로 고정·계측 모듈 2개에 대한 테스트로 구성한다. 원본 ZIP 입력 바이트의 확인은 아래 실제 명령으로 수행했다.
- 신설 입력-pin CLI: `python scripts/benchmark/pin_tier_a_initial_xyz_0204.py --owner-zip <원본> --budget-draft <이전 draft.json> --out-dir <새 디렉터리>`; 기존 출력 폴더 덮어쓰기 금지.
- `CURRENT.json`, `docs/DEVELOPMENT_HANDOFF.md`, 체크포인트, G1 및 원본 ZIP 증거는 불변. 실제 MLIP·DFT·NEB·MD·성능 scoring·GitHub 배포 없음.

## 실제 성능 검증까지 남은 최소 필수사항

1. MACE-MP small의 **실제 가중치 바이트** 및 정확한 hash 고정. Rhombus MACE-MPA-0 medium의 기존 해시 `75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638`은 기록됐으나 이 개발 단계에서 실행 바이너리를 독립 재검증하지 않았다.
2. 동일 endpoint relaxation, NEB 수렴·최대 step·spring, force tolerance 및 실패 처리 기준을 소유자 승인 전 사전 고정.
3. 모델 × 경로별 **숫자로 정한** wall/CPU 시간, force·energy·model call 상한, 프로세스 메모리, 파일럿 전체 한도 및 운용 환경 고정.
4. 4개 TRAIN 경로의 초기 **raw XYZ hash와 실제 파서 구조 fingerprint 대응**은 향후 권한 있는 실행기에서 확인. XYZ parser semantics의 정합성은 이 hashing 단계에서 다루지 않았다.
5. 실제 모델 실행은 별도 소유자 승인이 있을 때만 하고, 첫 파일럿은 속도·재현성·비수렴·비용 feasibility 점검으로 제한. 성능 우위를 주장하지 않는다.
6. 공식 비교는 추가로 사전 동결된 `delta_eV`, false-acceptance risk, coverage, 화학계·출처군 uncertainty, cheapest/no-information baseline, 동일 전체 예산 정책, 숨긴 target의 엄격한 평가 격리를 요구한다.

## 영구 판정

`TIER_A_PROTOCOL_DRAFT_READY` / `BENCHMARK_NOT_FROZEN` / `TIER_B_NOT_FROZEN` / `SCIENTIFIC_NO_GO_ABSTAIN`.
