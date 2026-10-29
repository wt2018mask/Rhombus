# Rhombus V3 Priority 4 — 수치 반증 및 독립 평가 감사

## 결론과 범위

**SCIENTIFIC NO-GO / qualification=ABSTAIN.** 이는 후보의 물리적 불가능을
주장하는 것이 아니라, 수렴된 연속 3D percolation과 독립적인 수송
예측력이 증명되지 않았다는 뜻이다. 실행 기준 commit은 `c343e080`이며,
해당 변경을 포함한 작업 트리의 분석 코드 SHA256이 각 새 JSON에 있다.
과거 Priority 1–3 아티팩트는 수정하지 않았다. GPU/MD/MLIP 추론 및 원격
작업은 실행하지 않았다.

## 반례와 evaluator

주기적인 Gaussian 형태 장애물을 가진 analytic potential에서 대각선의
양 끝점이 낮아도 선분 중간 에너지 차이 >0.99 eV, 음의 host clearance를
재현했다 (`tests/test_priority4_numerical.py`). 이는 그래프의 voxel 정점만
검사하면 연속 edge 내부의 장벽과 충돌을 놓칠 수 있음을 반증한다.
기존 26-neighbor 값은 정의 그대로 보존하고, 기본값이 동일한 선택적
6/18-neighbor 비교를 추가했다. 세 이웃 관계에서 관측된 threshold는
포함 관계에 따른 단조성을 테스트한다.

각 구조에서 charge-scaled `SiteEnergyEvaluator`의 임의로 고정한 3점에
대해 중심 유한차분 h=1e-4 Å와 힘을 비교했다. 최대 오차는 Li2S
1.97e-6, LiAlO2 9.71e-5, LLZO 3.78e-4 eV/Å이다. 격자 벡터 하나의
평행이동 전후 에너지 최대 차이는 각각 1.78e-14, 3.91e-14, 5.91e-12 eV.
이는 3점의 절대 오차이며 경계·모든 원자 환경에 대한 보증은 아니다.
별도 단일 산소 모델에서 cutoff 전이 7 Å와 8 Å의 양옆 및 MIC 전환
15 Å를 h=1e-5 Å로 확인했다. 15 Å의 좌우 힘 부호는 바뀌므로 정확한
전환점의 미분 가능성을 주장하지 않는다. 실제 결정의 모든 cutoff
경계, 원자 자체의 평행이동 및 상대 오차는 검증하지 못했다.

## 결정 구조별 3D 그래프 및 연속 edge

원본 CIF, n=12/16, 각 원점 0과 0.5 voxel, 세 winding witness를
사용했다. 원점·해상도를 포함한 값의 범위다. 그래프 barrier는 각각의
전역 격자 minimum을 기준으로 하며, edge 차이는 개별 witness의 절대
정점 최대와 독립 재표본화 최대의 차이다. 0.025 Å와 0.05 Å 두 간격의
모든 witness 원자료는 `priority4_numerical_v2.json`에 있다.

| 구조 | 6 / 18 / 26 이웃 채널 범위 (eV) | 26 이웃 R_free 범위 (Å) | 개별 edge 누락 최대 (eV) | 상태 |
|---|---|---|---:|---|
| Li2S | 2.055–3.860 / 1.090–1.782 / 0.365–0.710 | 0.490–0.526 | 0.129 | NOT_CONVERGED |
| γ-LiAlO2 | 1.175–1.542 / 1.144–1.242 / 1.144–1.232 | 0.376–0.444 | 0.060 | NOT_CONVERGED |
| tetragonal LLZO | 3.792–8.531 / 2.336–5.628 / 0.647–2.350 | 0.247–0.346 | 1.968 | NOT_CONVERGED |

모든 결과는 voxel 예산 262,144 이하이고, graph cycle winding rank 3과
endpoint displacement를 독립 확인했다. 원점과 spacing 변화에서 채널
spread 0.03 eV 및 radius spread 0.03 Å의 사전 선언된 수치 진단 범위를
세 구조 모두 충족하지 못했다. 이 허용 범위는 물리 정확도가 아니다.
표본화된 이 실제 witness의 ionic-radius clearance는 음수가 아니었다.
음수가 없다는 것은 선분 전체나 다른 경로에 충돌이 없다는 증명이 아니다.
각 주기 경로는 3개의 독립 winding 방향이지 서로 독립인 세 후보 경로가
아니다. supercell 일치 비교, 더 높은 해상도의 수렴 및 최단 경로의
연속 검증은 수행하지 않았다. 과거 Li2S 0.599/0.734 eV는 다른 격자
설정의 voxel 결과로서 물리 수렴의 근거가 아니며, 이 값들을 수정하지 않았다.

## Priority 3 최적화의 제한된 실제 경로 재검사

n=12의 첫 3D winding witness 하나씩, 2회 L-BFGS-B 반복, vertex당
±0.05 Å, 최적화용 선분 subdivisions=2 및 독립 검증 0.025 Å를 적용했다.
최대값은 공통 voxel minimum 기준 eV이며 괄호 순서는 그래프 3D / 개별
witness 최적화 전 / 후이다: Li2S (0.710 / 0.720 / 0.720), γ-LiAlO2
(1.148 / 0.946 / 0.939), LLZO (0.647 / 2.194 / 1.969). 개별 witness는
3D 그래프 threshold를 실현하는 다른 winding cycle보다 낮을 수 있어
서로 동등한 barrier가 아니다. 세 optimizer 모두 `converged=False`,
`RESOURCE_LIMITED_NOT_CONVERGED`이다. winding endpoint는 보존되지만
별도 cycle 간 연결, homotopy, reparameterization 및 연속 전역 MEP는
보장하지 않는다. 원자료와 절대 energy는 `priority4_optimizer_v1.json`에 있다.

## 그룹 통계와 누출

완료 기록 34개는 relaxed hash 24개, reduced formula 16개, 기록된 parent
12개를 공유한다. 0.8 Å 임계값과 모든 비교는 사후 탐색이고, crash 제외
선택 편향이 있다. 다음 값은 동일 step의 formula 평균이며 ρ/AUC이다.

| steps / 양성·음성 | saddle | +0.30 eV | +0.50 eV | cohort-relative |
|---|---|---|---|---|
| 1000 / 4·8 | .627/.969 | .571/.969 | .566/.969 | .789/.969 |
| 3000 / 3·1 | .200/1.000 | .600/.667 | .200/1.000 | −.632/.000 |
| 8000 / 3·5 | .802/.800 | .596/.633 | .756/.800 | .651/.667 |

formula cluster 1000회 bootstrap, 동일 resample의 paired 비교 및 1000회
label permutation의 ρ negative control을 새 JSON에 수록한다. 단일 클래스
resample의 AUC는 null/undefined이며 유효 횟수도 기록한다. 3000-step은
음성 단 하나로 통계가 매우 불안정하다. cohort-relative score는 평가
cohort 자체의 순위를 사용하여 누출된다. 해시·formula·parent 간 중복을
분리한 독립 holdout은 현재 확보되지 않았으며, 학습 없는 고정 점수의
LOFO는 독립 모델 평가가 아니다. `INDEPENDENT_VALIDATION_NOT_AVAILABLE`.
√step으로 나눈 평균 변위도 diffusion coefficient나 conductivity가 아니다.

## 동일 구조·seed 혼합 MD 기록

네 쌍의 P1/P2 입력 hash와 seed가 같지만 RNG state, 초기 속도, force 및
neighbor-list 세부 설정은 증명되지 않는다. 첫 공통 frame은 equilibration
이후 production step 10이다. 검증된 logical trajectory hash와 별도 frame
바이트 hash를 저장했으며, MIC 후 평균 병진만 제거했다(회전 정렬 없음).

| ID | 원시 RMS / 최대 Å | MIC·병진 정렬 RMS / 최대 Å | 비교 제한 |
|---|---|---|---|
| f0db48 | .106 / .178 | .101 / .150 | 프로토콜 및 런타임 차이 |
| a08649 | .259 / .592 | .258 / .587 | 프로토콜 및 런타임 차이 |
| 518ff3 | .162 / .407 | .160 / .388 | 프로토콜 및 런타임 차이 |
| 59d9d3 | 미확보 | 미확보 | 완료 trajectory 미보존, CPU/GPU 차이 |

정렬 방법도 진단적이며 주기 경계에서 평균 병진의 최적성을 보증하지
않는다. 하나의 동일 구조·seed에서 완주와 중단이 함께 나타났다는 것은
시간적 실패의 원인을 입증하지 않는다. 폭발 중단은 낮은 확산으로
취급하지 않는다. 후속 matched CPU replay는 동일 모델 hash·환경·초기
좌표/속도·RNG를 고정하고 timestep, P1 force tolerance, 근거리 force를
각각 한 번에 하나씩 바꾸어 같은 물리 시간과 raw trace를 비교해야 한다.
이번 임무에서는 제출 및 추론을 금지했으므로 replay는 수행하지 않았다.

## 재현 및 잔여 제한

`OPENBLAS_NUM_THREADS=1 python scripts/diagnostics/priority4_numerical.py --output <new-file>`,
`.../priority4_optimizer.py --output <new-file>`,
`.../priority4_evidence.py --stats <new-file> --md <new-file>`로 생성한다.
출력 덮어쓰기는 거부한다. 최초 base SHA, source/file hashes, 경로·조건,
bootstrap seed와 미수행 사유는 결과에 기록한다. CI가 실행한 전체
테스트 상태는 커밋 보고에서 별도 기술한다. 경계 검증, 더 높은 격자,
원본/supercell 동등 비교, 다중 연결 witness의 동시 최적화, 독립 holdout,
동일 초기 상태의 안전한 remote replay가 다음 결정에 필요한 작업이다.

동일 step별 `saddle` 점수의 구조 hash / formula / parent 단위 집계는
각각 다음과 같다(ρ/AUC): 1000 step, n=19/12/10에서 .721/.914,
.627/.969, .571/.958; 3000 step, n=5/4/4에서 .000/1.000, .200/1.000,
.200/1.000; 8000 step, n=8/8/8에서 .802/.800, .802/.800, .802/.800.
이들은 각각 사후 그룹 평균이며 fold 평가 또는 독립 holdout이 아니다.
`priority4_grouped_v3.json`과 `priority4_md_v3.json`이 최종 증거다.

독립 두 번째 CPU 실행에서 경과 시간을 제외한 수치 감사 JSON 전체가
정확히 일치했다. 주기적 analytic 반례는 별도의
`priority4_counterexample_v1.json`과 `priority4_counterexample.py --output
<new-file>`로 재현할 수 있다. 반례는 특정 edge의 누락 장애물을 입증하며,
다른 연속 경로가 존재하지 않는다는 전역 불가능성 증명은 아니다.
그룹 통계 및 MD 감사 CLI도 별도 출력 경로에서 재실행했으며 두 JSON
모두 최초 산출물과 정확히 일치했다.
