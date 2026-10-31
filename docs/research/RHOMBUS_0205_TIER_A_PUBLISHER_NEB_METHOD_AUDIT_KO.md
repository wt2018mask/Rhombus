# RHOMBUS 0205 — LiTraj 원저자 NEB 구현 의미 감사 (비실행)

2026-10-31 · 연구 목표: 동일한 계산 예산에서 선택적 Li hop 판단의 오판 위험과 coverage 검증

## 검증 출처와 신뢰 경계

- 제1저자 논문: Dembitskiy et al. (2025), *Benchmarking machine learning models for predicting lithium ion migration*, npj Computational Materials 11, 131. DOI 10.1038/s41524-025-01571-z.
- 제1자 코드: `AIRI-Institute/LiTraj`, `notebooks/nebDFT2k_benchmark_MACE_MP_small.ipynb`, 관찰된 Git HEAD `c3ca5c2afbc13ffc823306f546dcee24486ade2a`, Git blob `685f9628ccbe55daf2c717f791ab716e0a2806e7` (2026-10-31 조회). *Git blob은 공개 코드 파일의 버전 식별자이지, 실제 계산 또는 게시자 서명 영수증이 아님.*
- 논문은 구조 이완의 목표 힘을 0.1 eV/Å이라고 기술한다. 저자 MACE small 노트북은 `mace_mp(model="small", ..., default_dtype="float64")`를 명시한다.
- 공식 MACE 별칭 구현은 `small`을 `2023-12-10-mace-128-L0_energy_epoch-249.model`로 매핑한다. 논문 본문의 ‘2023.12.03’ 버전 표기와 별칭의 실제 파일명 날짜가 완전히 일치하지 않는다. **이것만으로 논문 계산에 어떤 가중치가 사용됐는지 단정할 수 없으며, 정확한 원저자 실행 환경과 checkpoint 파일 검증이 필요하다.**

## 확인된 원저자 노트북 코드 의미

저자 노트북의 `optimize` 함수 기본값: `n_steps=100`, `fmax=0.1`.

| 단계 | 저자 노트북에 실제 적힌 호출 | 반드시 유의할 내용 |
|---|---|---|
| 출발점 이완 | `qn_source.run()` | `fmax`, `steps`를 명시하지 않음. ASE 설치 버전의 기본값에 의존 |
| 도착점 이완 | `qn_target.run(fmax=fmax, steps=n_steps)` | 명시적으로 전달. 기본 인수로는 0.1 eV/Å, 100 단계 |
| CI-NEB | `NEB(..., k=5.0, climb=True, method='improvedtangent', parallel=False)` | 노트북 내 명시된 스프링·경로 방식 |
| NEB 최적화 | `qn.run(steps=n_steps)` | 100 단계는 명시하지만 `fmax`는 생략. ASE 기본값에 의존 |
| 사후 선택 | 출발점·도착점·NEB의 최대 힘이 `fmax` 미만일 때만 결과 기록 | 사후 최대 힘 검사와 최적화기 자체 종료 조건은 다른 개념 |

이 차이는 `fmax=0.1`을 세 최적화기에 모두 명시하는 **Rhombus 통제된 대칭 비교 후보와 원저자 노트북 코드가 문자 그대로 동일하지 않음**을 의미한다. 어떤 방법이 더 과학적인지는 참고 기준과 실험 목적에 따라 판단해야 하며, 소급해서 ‘논문의 정확한 실행 재현’으로 승격시키면 안 된다.

## 개발 산출물

1. `rhombus/benchmark/tier_a_publisher_method_audit.py`: 로컬 `.ipynb`를 JSON/AST로 정적 검사. *어떠한 셀도 실행하지 않고*, output/DFT target/trajectory 파일을 열지 않음. 실제 함수 호출의 키워드 누락을 명시적으로 기록하고, 소스 기본값을 임의 추론하지 않음. 코드·입력 크기 제한과 파일 변경 감지 적용.
2. `scripts/benchmark/audit_tier_a_publisher_method_0205.py`: 로컬 공용 노트북을 전달받아 비실행 감사 JSON 생성. 기존 출력 덮어쓰기 거부. 선택적으로 기존 비용 계약과 비교하되 실행 권한 미발급.
3. `tests/test_tier_a_publisher_method_audit_0205.py`, `tests/test_tier_a_publisher_method_cli_0205.py`: 악성 코드 미실행, target output 미열람, 소스 변경 감지, 보호된 출력, 대칭 NEB와 비동등성 검증.

## 실제 검증 상태 및 의사결정

- 이번 검사는 **원저자 공개 노트북의 소스 표현과 의미를 식별하기 위한 것**. 코드에서 실제 DFT/NEB 수치가 산출됐다는 증거 아님.
- 저자 노트북 소스의 핵심 호출과 기존 Rhombus 설정의 차이를 확인했으나, 최적화기에 사용됐던 정확한 ASE 버전 및 각 단계의 런타임 기본값은 이 작업에서 독립 검증하지 않음.
- 다음 별도 owner 선택 필요: (A) 원저자 노트북 구현 자체의 환경까지 고정하는 재현 연구, (B) 세 단계의 종료 기준을 명시적으로 통일하는 선행등록 대칭 비교. 최종 Tier A 동일 비용·선택적 위험 실증은 (B)를 권장하지만, (A)와 같은 결과를 주장하지 않음.
- **NEB 힘 허용차, 모델 버전 및 모든 호출·시간·메모리 예산을 사용자 승인으로 동결하기 전에는 계산을 허가하지 않음.**
- 모든 과학 상태: `TIER_A_PROTOCOL_DRAFT_READY`; `BENCHMARK_NOT_FROZEN`; `TIER_B_NOT_FROZEN`; `SCIENTIFIC_NO_GO_ABSTAIN`.
