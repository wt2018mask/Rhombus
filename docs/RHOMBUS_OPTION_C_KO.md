# Option C — 한정 수치 정정과 같은 경로 물리 참조 감사

**SCIENTIFIC NO-GO / ABSTAIN.** 수치 동작의 개선과 물리 Hamiltonian의
적용성 검증을 구분한다. 가중치가 없는 상태에서 MACE 값을 생성하지 않았다.

## 감사 지적의 확인과 정정

- D-1: R1 표의 graph clearance와 하한은 서로 다른 경로였다. 같은 경로의
  대수적 부등식 위반은 아니었지만 비교가 혼동을 일으켰다. 새 결과에는
  좌표 SHA256, 최적화 후 sampled clearance와 그 경로 하한을 함께 저장한다.
- D-2: smoothmax는 낮은 에너지 bead의 gradient를 작게 만들므로 unweighted
  MEP 잔차와 목적함수가 다르다. 그러나 이것만으로 모든 비수렴이 필연적이라는
  주장은 증명되지 않았다. 현재 코드에는 감사 문서가 전제한 spring 항도 없다.
- D-3: 1e-14 Å 호출을 제거하고 refinement 최대 15회, 최종 고정 bead string
  polish 최대 15회를 각 경로에 배정했다. 이는 iteration 예산이지 엄밀한 총
  force-evaluation 또는 wall-time 상한은 아니다. junction은 polish 중 고정된다.
- D-4: BCC 세 gradient의 0 가중합은 (1/4,3/8,3/8)이다. 문서의 (1/5,2/5,2/5)
  가중합 norm은 1/15로 0이 아니다. 접선 정거성과 수직 정거성은 계속 구분한다.

## 동일 witness SC 비교

값의 단위는 Å. 원래 graph와 최적화 후 경로를 명시적으로 구분했다.

| N³ / 원점 | 원래 graph | 최적화 후 sampled clearance | 같은 경로 1-Lipschitz 하한 |
|---|---:|---:|---:|
| 16 / 정렬 | 1.628427 | 1.628427 | 1.615927 |
| 16 / 이동 | 1.504962 | 1.558273 | 1.546896 |
| 20 / 정렬 | 1.628427 | 1.628427 | 1.615927 |
| 20 / 이동 | 1.529609 | 1.571636 | 1.560512 |
| 24 / 정렬 | 1.628427 | 1.628427 | 1.616522 |
| 24 / 이동 | 1.546053 | 1.580733 | 1.568816 |

모든 새 행에서 하한 ≤ 같은 경로 sampled clearance를 확인했다.
이것이 SC global minimax 수렴을 입증하지 않는다.

## 한 차례 한정된 실제 경로 polish

n=16, 원점0, 이전과 같은 세 결정 경로만 재실행했다. 추가 18개 sweep을
시작하지 않았다. smoothmax refinement 후 모든 내부 bead에 unweighted
perpendicular force를 적용하고 arc-length 재배치, step 상한0.05 Å를 쓴다.

| 구조 | 이전 최대 수직힘 eV/Å | 수정 후 최대 수직힘 eV/Å | 분류 |
|---|---:|---:|---|
| Li2S | 1.129887 | 0.327062 | FEASIBLE_WITNESS_NON_STATIONARY |
| γ-LiAlO2 | 1.282783 | 0.599442 | FEASIBLE_WITNESS_NON_STATIONARY |
| tetragonal LLZO | 5.879185 | 0.668069 | FEASIBLE_WITNESS_NON_STATIONARY |

0.05 eV/Å 기준은 충족하지 않았다. 고정 junction polish가 전체 junction
재최적화의 해법이라고 주장하지 않는다. 실제 경로의 최종 좌표·0.025 Å
재검사·잔차 및 원래 MEP/전역 기준의 한계를 새 JSON에 보존했다.

## M0-C 물리 참조: NOT_EXECUTED

검증된 public MACE weights를 현재 로컬 경로에서 찾지 못했다. 기존 P1
완화 에너지는 한 구조의 에너지이고 P2 trajectory는 이동 경로의 독립
single-point 에너지 프로파일이 아니므로 이를 참조 barrier로 재사용하지 않았다.
`priority7_option_c_reference.py`는 세 결정의 보존 witness에서 시작점,
정적 peak 표본, 끝점을 골라 **실제 전체 원자 구조**를 보존하는 입력을
만든다. 가장 가까운 Li 하나를 움직이고 spectator Li는 유지하며, 근접
원자쌍을 기록한다. 이는 host-only static과 full-structure MACE가 서로
다른 근사를 가진다는 점을 포함하는 모델 비교이고 DFT ground truth가 아니다.

O/S/Se를 포함하는 코호트 표본은 P1 provenance를 기록했으나 같은 migration
witness가 보존돼 있지 않아 NO_RETAINED_CONTINUOUS_WITNESS로 처리했다.
미실행 기록 6건이며 새 물리 barrier 차이는 없다. 계산 결과를 꾸미지 않았다.

가중치가 안전한 로컬 위치에 준비되면
`python scripts/diagnostics/priority7_option_c_reference.py --model <local-model>
--output <new-result>`를 이용한다. SHA256
`75428afe3a1d7d8062e19bcaabd5c433623cabf308242ec9fb493e38604fb638`
검증 뒤 CPU/float64/1-thread, MD 없이 표본만 평가한다. 60초 검사는 호출
사이에서만 하므로 단일 inference의 strict timeout을 보증하지 않는다.
전체 path의 barrier나 relaxed NEB와 혼동하지 않는다. credentials나 모델
가중치를 채팅·소스에 넣지 않는다.

## 근거와 보존

R1의 uncommitted 코드가 Option C 변경으로 사라지지 않도록 원래 manifest와
SHA256이 정확히 일치하는 소스를 `docs/source_snapshots/stage_r1/`에 보존했다.
R1 JSON을 수정하지 않았다. 신규 결과는 `optionc_analytical_v2.json`,
`optionc_{li2s,lialo2,llzo}_polish_v2.json`,
`priority7_optionc_reference_v1.json`이다. 독립 물리 참조가 확보되기 전에는
새 재료 성능 또는 conductivity GO를 선언하지 않는다.
