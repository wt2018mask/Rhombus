# Stage R1 — 수학적 반증·경로 정거성 진단

과학 판정은 **SCIENTIFIC NO-GO / ABSTAIN**이다. 아래 수치들은 모델의
전도성 검증이 아니며 global minimum과 saddle lower bound가 없어
`UNCERTIFIED_MISSING_GLOBAL_MIN_AND_SADDLE_LOWER_BOUNDS`다. 과거
Priority 7 JSON은 수정하지 않았다.

## 해석 예제와 실제 알고리즘

M0-A1은 실제 segment graph 및 단일 witness의 joint optimizer를 사용한다.
M0-A2는 실제 segment graph, softmin string 및 원래 clearance의
1-Lipschitz witness 하한을 사용한다. string 하나의 결과는 3D 최적성
증명이 아니다. 그래프 에너지 오차는 voxel minimum 기준이고 괄호는
절대 saddle과 정확한 1 eV 기준 차이다. SC 하한 차이는 한 witness의
하한에서 전역 참조 1.628427 Å를 뺀 값이다.

| N³ | voxel 원점 | cosine barrier 오차 eV (절대 saddle 오차) | SC graph clearance 오차 Å | SC 단일 witness 1-Lip 하한 차이 Å |
|---:|---|---:|---:|---:|
| 16 | 정렬 | 0 (0) | 0 | −0.012500 |
| 16 | (0.13,0.29,0.41) | −0.007450 (+0.001545) | −0.123465 | −0.081531 |
| 20 | 정렬 | 0 (0) | 0 | −0.012500 |
| 20 | 이동 | −0.005032 (+0.000728) | −0.098818 | −0.067915 |
| 24 | 정렬 | 0 (0) | 0 | −0.011905 |
| 24 | 이동 | −0.003496 (+0.000506) | −0.082374 | −0.059611 |

BCC의 세 거리는 각각 2.1213203436 Å, 정확 local clearance는
0.9213203436 Å이다. 3-neighbor 평균 gradient는
(0.0785674201, 0.0785674201, 0), norm=1/9이며 접선 (−1,1,0) 방향
투영은 0이다. finite-image β=30의 gradient는 (0.0785674201,
0.0785674201, 약 0), 독립 중심차분은 (0.0785674211, 0.0785674211, 0)이다.
finite-image softmin 0.884699934 Å는 추가 이미지와 tie 엔트로피를 포함한다.
BCC tetrahedral vertex의 1.036067977 Å는 별도 단위 테스트로 확인했다.
이 검사는 LOCAL_VORONOI_TIE_DIAGNOSTIC이며 BCC 전역 위상 증명이 아니다.

## 실제 결정: joint 전후

| 구조 | 이전 최대 선분 범위 Å | R1 최대 선분 범위 Å | R1 최대 수직 힘 범위 eV/Å | 종료 | 0.025 Å 최대 초과 eV | R1 anchor 상대 sampled barrier eV |
|---|---|---|---|---|---:|---|
| Li2S | 0.221–0.247 | 0.098–0.100 | 0.563–1.130 | 6회 보간 후 polish 예산 없음 | 0.000665 | 0.720114–0.720123 |
| γ-LiAlO2 | 0.123–0.207 | 0.097–0.207 | 0.532–1.283 | 5회 예산 없음, 1회 반복 소진 | 0.016028 | 1.419977–1.420366 |
| tetragonal LLZO | 0.261–0.271 | 0.098–0.100 | 3.314–6.595 | 6회 보간 후 polish 예산 없음 | 0 | 1.382511–1.688754 |

R1 출력은 최종 수직 힘, 최대 에너지 bead의 수직 힘(끝점이면 null),
정규화 objective의 junction gradient, 제약 투영 잔차, 공통점 간격,
winding rank 및 종료 이유를 보존한다. polish 예산이 없을 때 마지막
보간점을 버리지 않고 그대로 저장한다. 잔차 평가에는 이동 상한 1e-14 Å의
진단 호출을 사용하므로 유한 정밀도에서 완전한 무이동 해석과 구분해야
한다. 모든 사례는 FEASIBLE_WITNESS_NON_STATIONARY, 숫자 수렴 0/6이다.

Li2S 첫 경로의 uniform 40→80 bead raw smoothmax는 −2.571569→−2.534663 eV,
정규화 값은 −2.756013→−2.753764 eV이며 nonuniform 80 bead 값은
−2.758683 eV였다. 정규화는 고정 N에서 상수만 빼므로 gradient를 바꾸지
않고, 재표본화 불변도 보장하지 않는다. arc-length midpoint quadrature는
진단으로만 평가했으며 최적화에 사용하지 않았으므로 이동하는 가중치의
미분을 생략한 최적화가 아니다.

## 실제 결정: 이미지 완비성과 clearance

| 구조 | 완비성 | 비평활 0.025 Å network 최솟값 범위 Å | 개별 witness 1-Lip 하한 범위 Å | β=60 finite-image bias 범위 Å | 수직 gradient norm 범위 |
|---|---:|---:|---:|---:|---:|
| Li2S | 6/6 | 0.487511–0.490281 | 0.475523–0.478846 | 0.012924–0.018310 | 0.037267–0.658106 |
| γ-LiAlO2 | 6/6 | 0.465174–0.465191 | 0.452729–0.454116 | 0.015754–0.015773 | 0.045053–0.343264 |
| tetragonal LLZO | 6/6 | 0.332263–0.391631 | 0.320195–0.392431 | 0.010867–0.017926 | 0.046206–0.750514 |

각 하한은 개별 witness의 최솟값 범위이며 같은 행의 세 방향 network
최솟값 범위와 개별 원소를 일대일 비교할 수 없다. 1-Lipschitz 하한은
host 중심에서도 성립하며 float64 오차를 포함한 단일 경로 하한이지 전역
최적 clearance의 증명이 아니다. reciprocal plane height, wrapped query와
host fractional 좌표를 이용해 모든 생략 이미지에 대한 보수적 하한을
계산한다. 정확 최근접 표면 완비성은 finite-image softmin 무한 꼬리
완비성과 다르다. 비직교·skew 셀은 넓은 명시적 이미지 집합으로 검증했다.

## 재현

`priority7_analytical_m0.py --output <new-file>` 및 `priority7_joint.py`,
`priority7_clearance.py`로 각 입력 network에서 새 결과를 만든다.
`priority7_summary.py --joint-suffix _joint_r1_v4.json --clearance-suffix
_clearance_r1_v3.json --output <new-file>`은 측정된 topology, 선분,
재표본화 및 정거성 기준을 사용한다. code/input/output digest는
`priority7_r1_manifest_v1.json`에 보존한다. 생성 시간 외의 재실행 차이,
최종 미수렴 및 resource 제한은 결과에 그대로 남긴다.
