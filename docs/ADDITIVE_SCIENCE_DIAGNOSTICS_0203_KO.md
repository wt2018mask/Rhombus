# 전방 진단 확장 — 2026-10-28

이 구현은 동결 0200/0201/0202 결과나 provisional gate를 변경하지 않는다. 모든 새 수치
도구는 ABSTAIN이며 계산 제출·물질 선별을 승인하지 않는다.

## 상태 압축

CURRENT 4071 bytes에는 기존 0118 baseline에 없는 값만 남아 있어 단순 중복 제거로는
줄일 수 없었다. baseline descriptor를 그대로 두고 추가 `continuation`이 해시로 결속된
`data/development/snapshots/0203-rolling-state-v1.json`을 읽도록 했다. 새 snapshot은 refs,
state_codes, blockers만 포함하며 기존 유효 상태와 동일함을 검증했다. CURRENT는 694 bytes다.
이후 PR에서 이미 존재하는 snapshot 또는 descriptor를 바꾸면 검사가 거부된다. 손상된
snapshot은 fail closed이며 과거 사건 파일은 변경하지 않았다. handoff는 새 저장 순서로
재생성되지만 유효 참조와 상태는 같다.

## 수치 API

- `rhombus.transport.window_diagnostics.thermal_windows`: 기존 v1 검증기는 이미 equil을
  제외하고 production 통계를 낸다. 새 도구는 production 중 처음 25%를 기본 추가 제외하고
  온도 평균·비율 및 per-atom 기울기를 계산한다. 운동온도는 호출자가 자유도를 명시해야 한다.
  NVT에서 energy trend만으로 정상 thermostat relaxation과 물리적·수치적 불안정을
  구별할 수 없으므로 어느 쪽도 확정하지 않는다.
- `multi_origin_msd`: 명시적으로 unwrapped Angstrom 좌표와 균일한 ps 시간만 받는다.
  host COM 변위를 mobile에서 빼고 여러 time origin의 MSD, log slope, 두 block slope 분산,
  host 내부 RMSD와 큰 step 증분 수를 반환한다. beta 분류와 0.5 Å 등 host 기준은
  PROVISIONAL이다. 큰 증분은 검증된 site hop이 아니며 Fickian 분류도 P3 자격이 아니다.
- `rhombus.domain.profiles`: O_ONLY/S_ONLY/HALIDE의 연구용 anion/risk 선언이다. 계열 전체에
  높은 안정성·낮은 장벽을 부여하지 않으며 학습 범위·oxidative window는 별도 검증이 필요하다.
- `rhombus.transport.static_channels.StaticChannelScreener.analyze`: 점유 mobile site 사이의
  제한 거리 periodic graph에서 cycle translation의 rank를 구한다. anion 반지름은 명시적
  입력이고 edge clearance는 17점 샘플의 근사치다. 빈 interstitial·vacancy 경로와 lattice
  relaxation을 모르므로 음성 graph를 절연체 판정이나 FALSIFIED_AT_P0_5로 사용하지 않는다.
  electrostatic/BVSE 장벽 모델은 검증되지 않아 barrier_proxy_eV는 null이다.

보존 0200 P1 구조를 새 모델 추론 없이 읽어 cutoff 3.5 Å, O 1.4 Å/S 1.84 Å라는
**잠정 입력**으로 조사했다. gamma-LiAlO2와 Li2S는 모두 occupied-site PERCOLATING_3D였고
sampled minimum edge clearance는 각각 -0.09687 Å, +0.17808 Å였다. 한 실행의 계산 시간은
각각 약 0.0126s, 0.0385s이며 설치/import 비용은 제외다. 이 결과는 두 물질의 실제 이동
장벽·전도성 또는 MD 자격의 차이를 증명하지 않는다. 고정 known controls를 원하는 방향으로
구별하도록 임계값을 조정하지 않았다.

## 출처 및 외부 장애

JATS binding fingerprint는 정규화된 process/total tuple의 identity만 나타낸다.
sigma_bulk, Ea, density의 원문 추출은 아직 없으므로 null로 표시하고
full_table_binding_complete=false다. 원문 미취득 상태에서 제공된 수치를 인증 상수로
등록하지 않았다. source_context의 전체 방법론 및 모든 표 열 검증은 미완이다.

0169/0170 CLI는 socket/URL timeout에 source-unavailable.json을 남기고 원래 예외를 다시
발생시킨다. workflow는 실패 시 해당 receipt만 보존하며 live check는 실패 상태를 유지한다.
정확한 실패 URL을 알 수 없으면 UNKNOWN으로 명시한다. 공식 대체 PDF의 동일 bytes나
고정 SHA가 검증되지 않아 fallback URL을 추가하지 않았다. Islandora 이전 설명은 독립
확인되지 않았다. 이번 Europe PMC probe도 CONNECT 403 / origin HTTP 000이었다.

미완 항목은 원문 방법론·bulk/Ea/density binding, 교정된 electrostatic barrier 및 실제
percolation 경로 장벽, 실물·모델별 수렴/불확도 검증이다. 따라서 이 작업은 엔지니어링 및
수치 진단 확장이며 원문 gate나 과학적 qualification을 완료한 마일스톤은 아니다.

## 검증

Python 3.11.17, 두 CPU threads에서 다음 명령은 **171 passed, 4 warnings**였다.

```bash
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 KAGGLE_CONFIG_DIR=/tmp/rhombus-kaggle-empty \
.venv/bin/python -m pytest -q -p no:cacheprovider \
 tests/test_additive_science_diagnostics.py tests/test_source_context_0193.py \
 tests/test_development_continuity.py tests/test_phase3_original_cross_paper_transfer_0169.py \
 tests/test_phase3_original_bulk_grain_routes_0170.py tests/test_research_context.py \
 tests/test_thermal_trace_0201.py tests/test_kaggle_automation_science.py \
 tests/test_manual_import_v2.py tests/test_owner_thermal_notebook.py tests/test_kaggle_automation.py
```

워크플로 YAML 파싱, git diff --check, 기존 worker/k202 기준 PR 연속성 및 승인 policy digest
확인도 통과했다. 원문 재수집·원격 CI·신규 MACE/MD 또는 Kaggle 실행의 증거는 아니다.
