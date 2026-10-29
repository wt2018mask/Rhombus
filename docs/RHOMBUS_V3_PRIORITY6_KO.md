# Priority 6 — 공통 junction 경로 및 그룹 평가

과학 판정: **SCIENTIFIC NO-GO / ABSTAIN**. 현재 기록은 후향적 평가이며 사전 등록된 독립 holdout이 아니다. `priority6_network.py`는 각 voxel minimum에서 국소 L-BFGS-B로 anchor를 얻는다. 전역 minimum은 증명하지 않았다. 각 winding cycle을 anchor에 직선 왕복 connector로 이어 같은 접점을 보장하나, connector가 host core 근처를 지날 수 있어 사전 검증된 저에너지 연결이 아니다. anchor는 모든 string에서 고정하며 winding rank와 endpoint를 확인한다. 독립 0.025 Å 선분 재검사는 3D 전역 최적 증명이 아니다.

| 구조 | 원래 segment-graph 범위 eV | 공통점 연결 string 범위 eV | 6개 중 세 string 전부 수렴 | string 표본점 대비 0.025 Å 최대 초과 eV | clearance 완전 수렴 / 6 |
|---|---:|---:|---:|---:|---:|
| li2s | 0.4931–0.7195 | 0.4949–0.7202 | 1/6 | 0.0479 | 0/6 |
| lialo2 | 1.0247–1.1745 | 1.8189–24.2881 | 4/6 | 1.3391 | 0/6 |
| llzo | 1.9714–2.9120 | 6.3739–12.5003 | 0/6 | 2.6640 | 0/6 |

직선 connector와 국소 해 탐색으로 큰 장벽이 생길 수 있으며 이는 재료의 전역 이동 장벽이 아니다. 불연속 recent-neighbor 전환에서 clearance는 미분 불능이며 1e-8 Å 이내 동률을 실패로 기록했다. 이를 제외한 경로도 200회 안에 모두 수렴하지 않아 clearance 범위를 전역 R_free로 보고하지 않는다. 별도 JSON에는 중단 사유 및 미수렴 raw 값이 있다.

## 72구조 거리 계층별 비교

AUC·ρ는 `COMPLETED=1`에 대한 값이다. 음이온 반경 비율은 원소별 owner-supplied 반경으로 모든 음이온 쌍에서 d/(r_i+r_j)의 최솟값이며 최소 절대 거리 쌍과 다를 수 있다. 양이온에는 Li를 포함하고 MIC distinct-site만 사용하며 자기 주기 이미지는 제외한다.

| 집단 | 지표 | 완주 Q1 / 중앙 / Q3 | 중단 Q1 / 중앙 / Q3 | AUC / ρ |
|---|---|---|---|---|
| all | anion_min_A | 2.991 / 3.547 / 3.642 (n=20) | 2.432 / 2.531 / 2.801 (n=51) | 0.961 / 0.718 |
| all | anion_radius_ratio | 0.948 / 0.967 / 0.988 (n=20) | 0.867 / 0.907 / 0.973 (n=51) | 0.668 / 0.261 |
| all | cation_min_A | 2.841 / 2.930 / 3.024 (n=20) | 2.482 / 2.667 / 2.900 (n=52) | 0.806 / 0.474 |
| all | volume_per_atom_A3 | 14.104 / 20.400 / 21.551 (n=20) | 11.037 / 11.642 / 12.792 (n=52) | 0.859 / 0.557 |
| O | anion_min_A | 2.863 / 2.896 / 2.952 (n=6) | 2.430 / 2.520 / 2.801 (n=47) | 0.894 / 0.432 |
| O | anion_radius_ratio | 0.969 / 0.997 / 1.025 (n=6) | 0.861 / 0.895 / 0.973 (n=47) | 0.826 / 0.358 |
| O | cation_min_A | 2.688 / 2.824 / 2.840 (n=6) | 2.501 / 2.664 / 2.895 (n=47) | 0.652 / 0.167 |
| O | volume_per_atom_A3 | 11.003 / 12.190 / 13.618 (n=6) | 11.186 / 11.669 / 12.861 (n=47) | 0.511 / 0.012 |
| OS | anion_min_A | 2.859 / 2.919 / 2.941 (n=3) | 2.420 / 2.512 / 2.785 (n=28) | 0.857 / 0.366 |
| OS | anion_radius_ratio | 0.956 / 0.968 / 0.970 (n=3) | 0.839 / 0.889 / 0.956 (n=28) | 0.762 / 0.268 |
| OS | cation_min_A | 2.705 / 2.820 / 2.832 (n=3) | 2.388 / 2.632 / 2.816 (n=28) | 0.655 / 0.159 |
| OS | volume_per_atom_A3 | 12.739 / 13.892 / 14.034 (n=3) | 11.029 / 11.642 / 12.823 (n=28) | 0.738 / 0.244 |

## 그룹별 제외 후 임계값 평가

0.8 Å label은 과거에 사후 선택되었다. 각 fold에서 고정 saddle 점수의 threshold만 training-fold Youden J로 선택하고 held-out run에 적용했다. AUC/ρ는 학습하지 않은 고정 점수의 순위이므로 parent와 formula별 fold가 같다고 독립 학습 성과가 입증되는 것은 아니다. 1000-step은 10 parents와 12 formulas뿐이며 전체 기록은 parent 12, formula 16이다. 반복 run 및 한 parent에 여러 formula가 존재하며 formula holdout 16개 중 8개에서 parent가 train과 test에 공유된다. Parent holdout의 formula 중복은 관찰되지 않았으나 모두 같은 후향적 출처다.

| 조건 | folds / runs | AUC [parent bootstrap 95%] | ρ [parent bootstrap 95%] | threshold accuracy [parent bootstrap 95%] |
|---|---|---|---|---|
| 1000_formula | 12 / 20 | 0.900 [0.715, 1.000] | 0.603 [0.342, 0.768] | 0.800 [0.611, 0.947] |
| 1000_parent_id | 10 / 20 | 0.900 [0.692, 1.000] | 0.603 [0.316, 0.766] | 0.800 [0.625, 0.950] |
| all_formula | 16 / 34 | 0.879 [0.635, 0.999] | 0.641 [0.227, 0.853] | 0.794 [0.618, 0.967] |
| all_parent_id | 12 / 34 | 0.879 [0.656, 0.999] | 0.641 [0.256, 0.854] | 0.794 [0.618, 0.966] |

1000회 bootstrap은 이미 계산된 held-out 예측을 parent 단위로 재표본화하며 threshold를 bootstrap마다 다시 학습하지 않는다. CI는 조건부 탐색 불확실성이며 독립 검증 CI가 아니다. 반복 실행·시간 길이 혼합·완주 선택 편향이 남는다. `INDEPENDENT_VALIDATION_NOT_AVAILABLE`.

## 재현과 실행 범위

`scripts/diagnostics/priority6_network.py --graph <priority5 graph> --output <new-file>`, `priority6_clearance.py --network <network json> --output <new-file>`, `priority6_statistics.py --output <new-file>`을 이용한다. 모든 신규 출력은 기존 파일을 덮어쓰지 않으며 input/code SHA256과 실패 이유를 보존한다. 후속 연구에는 graph의 low-energy spanning forest로 junction을 검증하고, 분기점/경로 전체를 공동 최적화하며, clearance의 비미분 지점에 적합한 minimax 방법과 독립 parent-family holdout을 별도 등록해야 한다.

원래 graph barrier는 각 격자의 voxel minimum을 기준으로 하지만, 공통점
string barrier는 해당 격자에서 찾은 local anchor energy를 기준으로 한다.
따라서 두 범위에는 기준점 차이가 포함되며 직접적인 수렴 증명이 아니다.
anchor absolute energy와 local optimizer 상태는 모든 network JSON에 보존한다.
독립 재실행한 통계 JSON은 첫 산출물과 정확히 일치했고 36개 network·
clearance 결과의 입력 hash, 18개 network의 공통 endpoint 및 winding을
별도 검증했다.
