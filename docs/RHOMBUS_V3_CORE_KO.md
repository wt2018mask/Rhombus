# Rhombus 3.0 연구 수치 코어

후속 실제 좌표 평가·결함/상안정성/MCP 통합 결과는
[RHOMBUS_V3_CALIBRATION_KO.md](RHOMBUS_V3_CALIBRATION_KO.md)에 기록했다.
아래 문서는 첫 수치 코어의 범위이며 후속 보정 성공을 의미하지 않는다.

이 변경은 재사용 가능한 수치 구현과 오프라인 테스트다. 실제 재료 보정,
디지털 자격 부여 또는 Kaggle 계산 완료가 아니다. `REMOTE_SCIENCE_NOT_EXECUTED`.
기존 0200/0201 프로토콜, 0202/0203 동결 실행 소스 및 역사적 결과를 바꾸지 않는다.
새 코드에는 새 실행 요청의 소스 결박이 필요하며 기존 동결 요청으로 실행할 수 없다.

## 정적 에너지장과 주기 퍼콜레이션

`rhombus.transport.bvse_percolation.SiteEnergyEvaluator`는 pymatgen 구조의 이동
원자를 제외하고, 음이온 Morse 우물과 양이온 screened-Coulomb/Pauli 반발을
계산한다. `anions={symbol: (R0_A, b_A, D_eV)}`와
`cations={symbol: (formal_charge, screening_A, exclusion_A)}`를 호출자가
명시해야 한다. 단위는 Å와 eV이며 반발식의 이동 이온 전하는 +1이다.
다른 전하의 이동 이온에 그대로 적용하지 않는다. 제공된 수치만으로 보정이나
적용성이 인증되지 않는다. 기본 계수를 임의로 채워 원하는 재료 순서를 만들지 않는다.

`grid()`는 기본 0.28 Å 간격, 각 축 24–40 격자를 사용한다. 최소 이미지
거리와 분석적 힘을 사용하며 다중 이미지 합이나 Ewald 모델은 아니다.
150 ms 성능 및 격자 수렴은 검증하지 않았다. 퍼콜레이션 Python 구현에는
격자 크기에 따른 추가 비용이 있다.

`percolation_thresholds(field)`는 26 이웃 주기 격자에서 에너지 순서로
union-find를 수행한다. 정수 이미지 오프셋과 한 연결 성분의 독립적인 순환
rank로 1D/2D/3D 임계값을 구한다. 이는 **해당 이산 그래프의** minimax 값이다.
대각선 연결 사이의 연속 장벽 또는 물리적 확산 장벽에 대한 보증이 아니다.
`percolating_cycles`에는 각 rank를 증명하는 풀린 분율 경로와 winding vector를
보존한다. `lattice`, `host_fractional`, `host_radii_A`를 함께 주면 이 경로의
최소 거리에서 명시적 이온 반경을 뺀 `bottleneck_radius_A`를 반환한다.
이는 격자점에서 표본화한 witness 경로의 여유도이며, 경로 사이 연속 충돌이나
최대 여유 경로를 구한 것이 아니다. 반경 미제공 시 null이다.

합성 4³ 장에서 1D/2D/3D 임계값 0/1/5 eV, winding rank, 경로 연속성,
분석적 힘과 유한차분, 주기 이동 동일성을 테스트한다. 이 숫자는 재료 결과가 아니다.
동결 COD 1008166(γ-LiAlO₂), 9009060(Li₂S)은 읽기 전용 테스트에 사용하며,
계수가 없을 때 계산을 거절하는지만 검증한다. 공개적으로 검증된 도메인별
계수·반경 및 고속 전도체 대조군 보정이 없으므로 **요청된 실제 재료 장벽/병목
비교와 `PASS_P0_5` / `FALSIFIED_HIGH_STATIC_BARRIER` 보정 게이트는 미완료**다.

## MEP/NEB

`ClimbingImageMEPSolver.solve(initial, final, evaluator, ...)`는 한 이동 이온과
고정 호스트의 Cartesian 경로를 최적화한다. `evaluator(N×3)`는 이미지별
에너지 배열과 음의 에너지 기울기인 힘 배열을 반환한다. 기본은 총 7개 이미지,
최대 200번 반복이다. steric 초기화, spring/perpendicular force 분리,
climbing image, 고정 끝점, 반복/이동량 상한을 구현한다. 임의 주기 이미지의
자동 hop 탐색, 다원자 협동 hop, 호스트 이완 또는 Buckingham 항은 구현하지 않았다.
주기 경로는 호출자가 올바르게 풀어 전달해야 한다. steric 호스트도 필요한
주기 이미지까지 명시한다.

반환값에는 정/역 장벽, perpendicular 및 band 잔차, 최소 호스트 거리,
실행 반복 수와 이미지 좌표/에너지가 포함된다. steric 제약을 위반하면 수렴을
인정하지 않는다. 0.1/1.0 eV 합성 double-well 및 굽은 경로에서 테스트한다.
재료별 저/고장벽 판정 임계값을 보정하지 않았으므로 수렴도 `UNQUALIFIED_BARRIER`다.

`ASEMobileIonEvaluator`는 호출자가 이미 준비한 ASE calculator를 받는다.
모델 로드/다운로드/제출은 하지 않으며 `allow_evaluation=True` 없이는 거절한다.
MACE의 실제 힘 호출 수나 Kaggle 실행시간은 측정하지 않았다.

## Arrhenius와 교차 반증

`quantify_arrhenius(records, carrier_count=..., volume_A3=...)`는 T, seed,
D(m²/s), D 분산, `p2_verdict=PASS`, `regime=DIFFUSIVE_FICKIAN`을 받는다.
라벨은 호출자의 주장이다. 원 궤적의 독립적 P2/P2.5 검증을 대체하지 않는다.
중복 seed/T와 부적절한 regime을 거절하고 3개 미만 온도 또는 150 K 미만
온도 범위에서는 기권한다. 온도별 역분산 평균과 seed 산포, Nernst–Einstein
S/cm 변환, ln(σT) 회귀, Ea 불확도와 조건부 정규 95% 구간을 반환한다.
Haven 비는 요청된 **나누기** 관례이며 기본 1이다. 밀도/Haven 상대 오차는
공통 오차로 외삽 구간에 더한다. D 분산의 bootstrap 자체는 호출자 책임이다.
비선형성 플래그는 적합 불량 진단이며 상전이 인증이 아니다. 장거리 외삽의
모델 오차나 모든 불확실성을 포함하는 구간으로 해석하지 않는다.
0.25 eV 합성 데이터의 복원과 단위를 검사하며, 진단 임계값 만족과
`QUALIFIED_SUPERIONIC` 승격을 구분한다. `p3_verdict=INDETERMINATE`, 자격용
`conductivity_S_cm=null`을 유지한다.

`compare_evaluators()`는 5% 부피, 0.20 eV 장벽 차이와 호스트 RMSD 기반
melting artifact를 점검한다. 임계값은 PROVISIONAL이며 서로 다른 모델 이름이
독립 학습 계보의 증거가 아니다. 실제 두 MLIP 실행은 수행하지 않았다.

## 통합 실행과 CI

`RhombusDiscoveryFunnel`은 G/P0 → P0.5 → P1 → P1.5 → P2 → P2.5 → P3 → X
순서의 명시적인 호스트 adapter를 받는다. 각 adapter는 CONTINUE/REJECT/ABSTAIN을
반환한다. 누락된 단계와 기권은 중단하고, P2 이전 기각은 후속 adapter를 호출하지
않고 `compute_saved_stages=["P2_MD", "P3_ARRHENIUS"]`를 기록한다. 이는 실행을
생략한 단계이지 측정된 CPU 시간 절감량이 아니다. JSON dossier를 SHA256으로
결박한다. 실제 과학 단계별 adapter 자동 배선과 최종 자격 인증은 미완료이며,
모든 adapter가 CONTINUE여도 `qualification=ABSTAIN`, `scientific_GO=false`다.
O_ONLY/S_ONLY/HALIDE 합성 입력의 제어 흐름 테스트를 재료 자격 검증으로 부르지 않는다.
어떤 경로도 Kaggle 작업을 예약하지 않는다.

0169/0170 PR CI는 `--allow-source-timeout`으로 실행한다. 실제 timeout 예외만
결정적 offline pytest를 별도 프로세스로 실행한 뒤 `offline_regression_status=VERIFIED`
영수증을 저장하고 exit 0 한다. `live_network_status=EXTERNAL_HOST_UNREACHABLE_TIMEOUT`,
`sha256=null`, 원문 미인증과 scientific_GO=false는 유지한다. HTTP/TLS/해시/
파서 오류와 오프라인 테스트 실패는 성공 처리하지 않는다. manual workflow는
`--require-live-network`로 실행하여 timeout도 실패한다. PR 초록 상태는 원문
인증 또는 기존 0193 통합 게이트 해결을 의미하지 않는다.

검증 명령:

```sh
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 .venv/bin/python -m pytest -q -p no:cacheprovider tests/test_rhombus_v3_funnel.py
.venv/bin/python scripts/development/continuity.py check
.venv/bin/python scripts/development/continuity.py check-pr --base-ref worker/k202 --pr-number 375
git diff --check
```

다음 과학 작업은 임의 계수 조정이 아니라 출처가 검증된 파라미터/반경 확보,
고정 대조군 및 격자/경로 수렴 보정이다. 그 전에는 실제 재료의 장벽 비교,
고전도성 자격, 독립 모델 일치 또는 신규 발견을 주장하지 않는다.
